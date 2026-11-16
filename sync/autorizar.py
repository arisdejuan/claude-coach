"""Autorización ÚNICA de Oura o Strava para un atleta. Se ejecuta una vez en tu ordenador.

Uso:  python3 sync/autorizar.py oura      (o strava)

Te pedirá (las escribes tú; no se guardan en ningún archivo):
  - URL de Supabase y la clave service_role
  - Client ID y Client Secret de la app de Oura/Strava
  - Tu email de acceso al dashboard
Abre el navegador, apruebas el acceso y guarda el permiso en Supabase.
A partir de ahí, GitHub sincroniza solo, para siempre.
"""
import getpass
import http.server
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser

sys.path.insert(0, os.path.dirname(__file__))

PUERTO = 8080
REDIRECT = f"http://localhost:{PUERTO}/callback"

SERVICIOS = {
    "oura": {
        "auth": "https://cloud.ouraring.com/oauth/authorize",
        "token": "https://api.ouraring.com/oauth/token",
        "scope": "personal daily heartrate workout session",
    },
    "strava": {
        "auth": "https://www.strava.com/oauth/authorize",
        "token": "https://www.strava.com/oauth/token",
        "scope": "read,activity:read_all",
    },
}


def pedir(var, texto, secreto=False):
    v = os.environ.get(var)
    if v:
        return v
    v = (getpass.getpass if secreto else input)(f"{texto}: ").strip()
    os.environ[var] = v
    return v


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in SERVICIOS:
        print("Uso: python3 sync/autorizar.py oura|strava")
        sys.exit(1)
    nombre = sys.argv[1]
    s = SERVICIOS[nombre]
    pedir("SUPABASE_URL", "URL de Supabase (https://xxxx.supabase.co)")
    pedir("SUPABASE_SERVICE_KEY", "Clave service_role de Supabase (no se verá al escribir)", True)
    cid = pedir(f"{nombre.upper()}_CLIENT_ID", f"Client ID de {nombre}")
    csec = pedir(f"{nombre.upper()}_CLIENT_SECRET", f"Client Secret de {nombre} (no se verá)", True)
    email = input("Tu email de acceso al dashboard: ").strip().lower()

    import comun  # después de tener las variables
    comun.URL = os.environ["SUPABASE_URL"].rstrip("/")
    comun.KEY = os.environ["SUPABASE_SERVICE_KEY"]

    r = comun.peticion("GET", f"{comun.URL}/auth/v1/admin/users?per_page=200", headers=comun._cab())
    r.raise_for_status()
    usuario = next((u for u in r.json().get("users", []) if (u.get("email") or "").lower() == email), None)
    if not usuario:
        print(f"No encuentro el usuario {email} en Supabase. Créalo primero (Authentication → Users).")
        sys.exit(1)

    estado = secrets.token_urlsafe(16)
    resultado = {}

    class Manejador(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == estado and "code" in q:
                resultado["code"] = q["code"][0]
                msg = "Listo. Ya puedes cerrar esta ventana y volver al terminal."
            else:
                resultado["error"] = q.get("error", ["respuesta inesperada"])[0]
                msg = "Algo ha fallado. Vuelve al terminal."
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<h2 style='font-family:sans-serif'>{msg}</h2>".encode())

        def log_message(self, *a):
            pass

    servidor = http.server.HTTPServer(("localhost", PUERTO), Manejador)
    hilo = threading.Thread(target=servidor.handle_request)
    hilo.start()

    params = {"client_id": cid, "redirect_uri": REDIRECT, "response_type": "code",
              "scope": s["scope"], "state": estado}
    if nombre == "strava":
        params["approval_prompt"] = "auto"
    url = s["auth"] + "?" + urllib.parse.urlencode(params)
    print("\nSe abre el navegador para que apruebes el acceso. Si no se abre, copia esta dirección:\n" + url + "\n")
    webbrowser.open(url)
    hilo.join(timeout=300)
    servidor.server_close()

    if "code" not in resultado:
        print("No se recibió la aprobación:", resultado.get("error", "tiempo agotado"))
        sys.exit(1)

    r = comun.peticion("POST", s["token"], data={
        "grant_type": "authorization_code", "code": resultado["code"],
        "client_id": cid, "client_secret": csec, "redirect_uri": REDIRECT,
    })
    if r.status_code != 200:
        print("Error al obtener el permiso:", r.status_code, r.text[:300])
        sys.exit(1)
    t = r.json()
    comun.guardar_conexion(usuario["id"], nombre, t["refresh_token"], t.get("access_token"))
    print(f"\n✅ {nombre.capitalize()} conectado para {email}. GitHub lo sincronizará solo a partir de ahora.")


if __name__ == "__main__":
    main()
