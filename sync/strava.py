"""Trae de Strava las actividades recientes (vatios, pulso, duración) a Supabase.

Variables: SUPABASE_URL, SUPABASE_SERVICE_KEY, STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET
Calcula una "carga" por actividad (tipo TSS) para estimar forma y fatiga.
"""
import os
import time
from datetime import datetime, timezone

from comun import comprobar_entorno, conexiones, guardar, guardar_conexion, peticion, perfil

DIAS = 45


def refrescar(c):
    r = peticion("POST", "https://www.strava.com/oauth/token", data={
        "grant_type": "refresh_token",
        "refresh_token": c["refresh_token"],
        "client_id": os.environ["STRAVA_CLIENT_ID"],
        "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
    })
    if r.status_code != 200:
        raise RuntimeError(f"Strava no renovó el permiso ({r.status_code}): {r.text[:200]}. "
                           "Vuelve a autorizar con sync/autorizar.py strava")
    t = r.json()
    expira = datetime.fromtimestamp(t["expires_at"], timezone.utc).isoformat()
    guardar_conexion(c["user_id"], "strava", t["refresh_token"], t["access_token"], expira)
    return t["access_token"]


def carga(a, ftp, fc_umbral):
    """Carga de la sesión. Con vatios: TSS. Sin vatios: estimación por pulso."""
    seg = a.get("moving_time") or 0
    np_ = a.get("weighted_average_watts") or (a.get("average_watts") if a.get("device_watts") else None)
    if np_ and ftp:
        if_ = np_ / ftp
        return round(seg * np_ * if_ / (ftp * 3600) * 100, 1)
    fc = a.get("average_heartrate")
    if fc and fc_umbral:
        return round(seg / 3600 * 100 * (fc / fc_umbral) ** 2, 1)
    # Fuerza u otras sin datos: estimación suave por tiempo
    return round(seg / 3600 * 35, 1)


def sincronizar(c):
    token = refrescar(c)
    p = perfil(c["user_id"])
    ftp = p.get("ftp") or 350
    fc_umbral = p.get("fc_umbral") or 170
    despues = int(time.time()) - DIAS * 86400
    filas, pagina = [], 1
    while True:
        r = peticion("GET", "https://www.strava.com/api/v3/athlete/activities",
                     headers={"Authorization": f"Bearer {token}"},
                     params={"after": despues, "per_page": 100, "page": pagina})
        r.raise_for_status()
        lote = r.json()
        for a in lote:
            filas.append({
                "user_id": c["user_id"], "id": a["id"], "fuente": "strava",
                "fecha": a["start_date"], "tipo": a.get("sport_type") or a.get("type"),
                "nombre": a.get("name"), "duracion_s": a.get("moving_time"),
                "distancia_m": a.get("distance"), "desnivel_m": a.get("total_elevation_gain"),
                "potencia_media": a.get("average_watts"), "potencia_norm": a.get("weighted_average_watts"),
                "fc_media": a.get("average_heartrate"), "fc_max": a.get("max_heartrate"),
                "kj": a.get("kilojoules"), "carga": carga(a, ftp, fc_umbral),
                "raw": {k: a.get(k) for k in ("trainer", "device_watts", "average_cadence", "suffer_score", "start_date_local")},
            })
        if len(lote) < 100:
            break
        pagina += 1
    guardar("actividades", filas, "user_id,id")
    return len(filas)


def main():
    comprobar_entorno("STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET")
    errores = 0
    for c in conexiones("strava"):
        try:
            n = sincronizar(c)
            print(f"Strava ✓ atleta {c['user_id'][:8]}…: {n} actividades")
        except Exception as e:
            errores += 1
            print(f"Strava ✗ atleta {c['user_id'][:8]}…: {e}")
    if errores:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
