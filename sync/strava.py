"""Trae de Strava las actividades recientes (vatios, pulso, duración) a Supabase.

Variables: SUPABASE_URL, SUPABASE_SERVICE_KEY, STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET
Calcula una "carga" por actividad (tipo TSS) para estimar forma y fatiga.
En las salidas en bici guarda además el detalle (raw.detalle): vueltas/intervalos con vatios y pulso,
bloques de trabajo y desacople aeróbico (deriva del pulso frente a los vatios, Pa:HR).
"""
import os
import time
from datetime import datetime, timezone

from comun import comprobar_entorno, conexiones, guardar, guardar_conexion, leer, peticion, perfil

DIAS = 45
MAX_DETALLES = 15     # detalles nuevos por ejecución (2 peticiones cada uno; Strava permite 100 cada 15 min)


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


def _media(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def desacople(t, w, fc, mov):
    """Pa:HR: eficiencia (vatios/pulso) de la 1.ª mitad frente a la 2.ª, sin los 10 primeros minutos.
    Positivo = el pulso sube para los mismos vatios. < 5 % buena base aeróbica."""
    if not (w and fc) or len(t) < 1200:
        return None
    pares = [(w[i], fc[i]) for i in range(len(t)) if t[i] >= 600 and (mov is None or mov[i]) and fc[i]]
    if len(pares) < 1200:
        return None
    m = len(pares) // 2
    def ef(xs):
        hr = _media([b for _, b in xs])
        return _media([a for a, _ in xs]) / hr if hr else None
    e1, e2 = ef(pares[:m]), ef(pares[m:])
    return round((e1 - e2) / e1 * 100, 1) if e1 and e2 else None


def bloques(vueltas, ftp):
    """Agrupa las vueltas de trabajo (≥ 88 % FTP, ≥ 20 s) en bloques; las pausas cortas (≤ 60 s) no cortan el bloque."""
    out, act, pausa = [], None, 0
    for v in vueltas:
        trabajo = v["w"] is not None and v["s"] >= 20 and v["w"] >= 0.88 * ftp
        if trabajo:
            if act is None:
                act = {"reps": 0, "s": 0, "ws": 0, "fcs": 0, "fc_s": 0, "fc_fin": None, "fc_ini": v["fc"]}
                out.append(act)
            act["reps"] += 1
            act["s"] += v["s"]
            act["ws"] += v["w"] * v["s"]
            if v["fc"]:
                act["fcs"] += v["fc"] * v["s"]
                act["fc_s"] += v["s"]
                act["fc_fin"] = v["fcmax"] or v["fc"]
            pausa = 0
        elif act is not None:
            pausa += v["s"]
            if pausa > 60:
                act, pausa = None, 0
    return [{"reps": b["reps"], "s": b["s"], "w": round(b["ws"] / b["s"]),
             "fc": round(b["fcs"] / b["fc_s"]) if b["fc_s"] else None,
             "fc_ini": round(b["fc_ini"]) if b["fc_ini"] else None,
             "fc_fin": round(b["fc_fin"]) if b["fc_fin"] else None} for b in out]


def detalle(token, act_id, ftp):
    h = {"Authorization": f"Bearer {token}"}
    r = peticion("GET", f"https://www.strava.com/api/v3/activities/{act_id}/laps", headers=h)
    r.raise_for_status()
    vueltas = [{"s": v.get("moving_time") or v.get("elapsed_time") or 0,
                "w": round(v["average_watts"]) if v.get("average_watts") else None,
                "fc": round(v["average_heartrate"]) if v.get("average_heartrate") else None,
                "fcmax": round(v["max_heartrate"]) if v.get("max_heartrate") else None,
                "cad": round(v["average_cadence"]) if v.get("average_cadence") else None}
               for v in r.json() if (v.get("moving_time") or v.get("elapsed_time") or 0) >= 5]
    r = peticion("GET", f"https://www.strava.com/api/v3/activities/{act_id}/streams", headers=h,
                 params={"keys": "time,watts,heartrate,moving", "key_by_type": "true"})
    st = r.json() if r.status_code == 200 else {}
    g = lambda k: (st.get(k) or {}).get("data")
    t, w, fc, mov = g("time") or [], g("watts"), g("heartrate"), g("moving")
    if w and len(w) != len(t): w = None
    if fc and len(fc) != len(t): fc = None
    if mov and len(mov) != len(t): mov = None
    d = {"v": 1, "vueltas": vueltas[:120], "bloques": bloques(vueltas, ftp), "con_pulso": bool(fc),
         "con_vatios": bool(w), "desacople": desacople(t, w, fc, mov)}
    if w and fc:
        n = len(t) // 2
        d["fc_mitades"] = [round(_media(fc[:n]) or 0), round(_media(fc[n:]) or 0)]
        d["w_mitades"] = [round(_media(w[:n]) or 0), round(_media(w[n:]) or 0)]
    return d


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
    # Detalle por intervalos de las salidas en bici (se calcula una vez y se conserva)
    previas = {x["id"]: (x.get("raw") or {}).get("detalle") for x in leer(
        "actividades", f"user_id=eq.{c['user_id']}&fecha=gte.{datetime.fromtimestamp(despues, timezone.utc).date()}&select=id,raw")}
    nuevos = 0
    for f in sorted(filas, key=lambda x: x["fecha"], reverse=True):
        if previas.get(f["id"]):
            f["raw"]["detalle"] = previas[f["id"]]
        elif "Ride" in (f["tipo"] or "") and nuevos < MAX_DETALLES:
            try:
                f["raw"]["detalle"] = detalle(token, f["id"], ftp)
                nuevos += 1
            except Exception as e:
                print(f"  detalle {f['id']} no disponible: {e}")
    guardar("actividades", filas, "user_id,id")
    print(f"  detalle por intervalos: {nuevos} salidas nuevas")
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
