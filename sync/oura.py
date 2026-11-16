"""Trae de Oura los últimos días (recuperación, sueño, VFC, pulso en reposo) a Supabase.

Variables: SUPABASE_URL, SUPABASE_SERVICE_KEY, OURA_CLIENT_ID, OURA_CLIENT_SECRET
Se ejecuta en GitHub Actions varias veces al día. Funciona para todos los atletas conectados.
"""
import datetime as dt
import os
from datetime import datetime, timedelta, timezone

from comun import ahora, comprobar_entorno, conexiones, guardar, guardar_conexion, peticion

API = "https://api.ouraring.com"
DIAS = 10


def refrescar(c):
    """Oura cambia el refresh token en cada uso: guardamos siempre el nuevo."""
    r = peticion("POST", f"{API}/oauth/token", data={
        "grant_type": "refresh_token",
        "refresh_token": c["refresh_token"],
        "client_id": os.environ["OURA_CLIENT_ID"],
        "client_secret": os.environ["OURA_CLIENT_SECRET"],
    })
    if r.status_code != 200:
        raise RuntimeError(f"Oura no renovó el permiso ({r.status_code}): {r.text[:200]}. "
                           "Vuelve a autorizar con sync/autorizar.py oura")
    t = r.json()
    expira = (datetime.now(timezone.utc) + timedelta(seconds=t.get("expires_in", 86400))).isoformat()
    guardar_conexion(c["user_id"], "oura", t.get("refresh_token") or c["refresh_token"], t["access_token"], expira)
    return t["access_token"]


def coleccion(token, nombre, inicio, fin):
    datos, siguiente = [], None
    while True:
        params = {"start_date": inicio, "end_date": fin}
        if siguiente:
            params["next_token"] = siguiente
        r = peticion("GET", f"{API}/v2/usercollection/{nombre}",
                     headers={"Authorization": f"Bearer {token}"}, params=params)
        r.raise_for_status()
        j = r.json()
        datos += j.get("data", [])
        siguiente = j.get("next_token")
        if not siguiente:
            return datos


def sincronizar(c):
    token = refrescar(c)
    hoy = dt.date.today()
    inicio = (hoy - dt.timedelta(days=DIAS)).isoformat()
    fin = (hoy + dt.timedelta(days=1)).isoformat()

    dias = {}
    def dia(f):
        return dias.setdefault(f, {"user_id": c["user_id"], "fecha": f, "raw": {}})

    for x in coleccion(token, "daily_readiness", inicio, fin):
        d = dia(x["day"])
        d["readiness"] = x.get("score")
        d["temperatura"] = x.get("temperature_deviation")
        d["raw"]["readiness"] = x.get("contributors")
    for x in coleccion(token, "daily_sleep", inicio, fin):
        d = dia(x["day"])
        d["sueno_score"] = x.get("score")
    # Periodos de sueño: nos quedamos con el sueño principal de cada noche
    for x in coleccion(token, "sleep", inicio, fin):
        if x.get("type") not in ("long_sleep", None):
            continue
        d = dia(x["day"])
        if x.get("total_sleep_duration"):
            d["sueno_horas"] = round(x["total_sleep_duration"] / 3600, 2)
        d["vfc"] = x.get("average_hrv")
        d["fc_reposo"] = x.get("lowest_heart_rate")

    filas = []
    for d in dias.values():
        fila = {"user_id": d["user_id"], "fecha": d["fecha"], "raw": d["raw"], "actualizado": ahora()}
        for k in ("readiness", "sueno_score", "sueno_horas", "vfc", "fc_reposo", "temperatura"):
            fila[k] = d.get(k)
        filas.append(fila)
    guardar("oura_diario", filas, "user_id,fecha")
    return len(filas)


def main():
    comprobar_entorno("OURA_CLIENT_ID", "OURA_CLIENT_SECRET")
    errores = 0
    for c in conexiones("oura"):
        try:
            n = sincronizar(c)
            print(f"Oura ✓ atleta {c['user_id'][:8]}…: {n} días")
        except Exception as e:  # un atleta con problemas no frena a los demás
            errores += 1
            print(f"Oura ✗ atleta {c['user_id'][:8]}…: {e}")
    if errores:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
