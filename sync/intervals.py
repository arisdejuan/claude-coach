"""Manda los entrenos de bici planificados a intervals.icu, que los pasa a Garmin (Edge).

Variables: SUPABASE_URL, SUPABASE_SERVICE_KEY, INTERVALS_API_KEY, COACH_EMAIL
La web guarda en la tabla "planificados" la bici de hoy y los próximos 7 días (ya ajustada
por el semáforo). Aquí se crean/actualizan/borran los eventos en el calendario de intervals.icu.
Cada evento lleva external_id "coach-AAAA-MM-DD" para reconocer los nuestros.
"""
import datetime as dt
import os
import re

from comun import actualizar, ahora, comprobar_entorno, leer, peticion, usuario_por_email

API = "https://intervals.icu/api/v1/athlete/0"


def auth():
    return ("API_KEY", os.environ["INTERVALS_API_KEY"])


def pct(w, ftp):
    return round(w / ftp * 100)


def limpio(nombre):
    # Sin números ni símbolos que el lector de intervals.icu pueda confundir con duraciones o vatios
    return re.sub(r"\s+", " ", re.sub(r"[\d%+×]", "", nombre or "")).strip(" ·-") or "Bloque"


def texto_entreno(pasos, ftp, nota):
    """Formato de texto de intervals.icu: '- Nombre 12m 90-93%' y bloques '3x'."""
    lineas = []
    if nota:
        lineas += [nota, ""]
    for p in pasos:
        lo, hi = pct(p["lo"], ftp), pct(p["hi"], ftp)
        rango = f"{lo}%" if lo == hi else f"{lo}-{hi}%"
        nombre = limpio(p.get("n"))
        if p.get("reps", 1) > 1:
            lineas += ["", f"{p['reps']}x", f"- {nombre} {p['min']}m {rango}"]
            if p.get("rec"):
                lineas.append(f"- Recupera {p['rec']}m {pct(p['recW'], ftp)}%")
            lineas.append("")
        else:
            lineas.append(f"- {nombre} {p['min']}m {rango}")
    return "\n".join(lineas).strip() + "\n"


def main():
    comprobar_entorno("INTERVALS_API_KEY", "COACH_EMAIL")
    u = usuario_por_email(os.environ["COACH_EMAIL"])
    if not u:
        raise SystemExit("No encuentro el usuario de COACH_EMAIL en Supabase")
    hoy = dt.date.today()
    hasta = hoy + dt.timedelta(days=9)
    filas = leer("planificados",
                 f"user_id=eq.{u['id']}&fecha=gte.{hoy.isoformat()}&enviado=is.null&select=*&order=fecha")
    if not filas:
        print("Intervals: nada pendiente")
        return

    r = peticion("GET", f"{API}/events", auth=auth(),
                 params={"oldest": hoy.isoformat(), "newest": hasta.isoformat()})
    r.raise_for_status()
    nuestros = {e.get("external_id"): e for e in r.json() if (e.get("external_id") or "").startswith("coach-")}

    for f in filas:
        ext = f"coach-{f['fecha']}"
        existente = nuestros.get(ext)
        if not f.get("sesion"):
            if existente:
                peticion("DELETE", f"{API}/events/{existente['id']}", auth=auth()).raise_for_status()
                print(f"Intervals 🗑  {f['fecha']}: ya no hay bici, borrado")
        else:
            evento = {
                "category": "WORKOUT",
                "type": "VirtualRide" if f["sesion"] in ("s1", "s2") else "Ride",
                "start_date_local": f"{f['fecha']}T00:00:00",
                "name": f["titulo"],
                "description": texto_entreno(f["pasos"], f.get("ftp") or 350, f.get("descripcion")),
                "external_id": ext,
            }
            if f.get("dur_min"):
                evento["moving_time"] = int(f["dur_min"]) * 60
            if existente:
                resp = peticion("PUT", f"{API}/events/{existente['id']}", auth=auth(), json=evento)
            else:
                resp = peticion("POST", f"{API}/events", auth=auth(), json=evento)
            if resp.status_code >= 300:
                print(f"Intervals ✗ {f['fecha']}: {resp.status_code} {resp.text[:300]}")
                continue
            print(f"Intervals ✓ {f['fecha']}: {f['titulo']}")
        actualizar("planificados", f"user_id=eq.{u['id']}&fecha=eq.{f['fecha']}", {"enviado": ahora()})


if __name__ == "__main__":
    main()
