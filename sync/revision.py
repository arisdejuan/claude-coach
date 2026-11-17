"""Revisión semanal del coach (la usa una tarea programada de Claude en la nube cada domingo).

Variables: SUPABASE_URL, SUPABASE_SERVICE_KEY, COACH_EMAIL

  python sync/revision.py datos              → imprime en JSON lo necesario para revisar la semana
  python sync/revision.py guardar nota.json  → guarda la nota del coach (y ajustes) para que salga en la web

Formato de nota.json:
{
  "texto": "Resumen y consejos (párrafos separados por línea en blanco)",
  "ajustes": ["Ajuste 1", "Ajuste 2"],                 # opcional, lista corta
  "objetivoSemana": "Objetivo de la semana que empieza", # opcional
  "objetivoMes": "…",                                   # opcional
  "semana_siguiente": {"dias": [["fa","z2"],["s1"],["pil"],["fb"],["s2"],["larga"],["com"]]}  # opcional
}
Ids válidos de sesión: fa, fb (fuerza), s1, s2 (rodillo series), z2 (rodillo Z2 opcional),
pil (pilates), larga (salida larga), com (comodín).
"""
import datetime as dt
import json
import os
import sys

from comun import actualizar, ahora, comprobar_entorno, guardar, leer, usuario_por_email

IDS = {"fa", "fb", "s1", "s2", "z2", "pil", "larga", "com"}


def lunes(d):
    return d - dt.timedelta(days=d.weekday())


def usuario():
    comprobar_entorno("COACH_EMAIL")
    u = usuario_por_email(os.environ["COACH_EMAIL"])
    if not u:
        raise SystemExit("No encuentro el usuario de COACH_EMAIL")
    return u["id"]


def datos():
    uid = usuario()
    hoy = dt.date.today()
    L = lunes(hoy)
    desde = (hoy - dt.timedelta(days=28)).isoformat()
    atleta = leer("atletas", f"user_id=eq.{uid}&select=nombre,perfil")
    acts = leer("actividades", f"user_id=eq.{uid}&fecha=gte.{desde}&select=fecha,tipo,nombre,duracion_s,"
                "distancia_m,desnivel_m,potencia_media,potencia_norm,fc_media,fc_max,carga&order=fecha")
    out = {
        "hoy": hoy.isoformat(),
        "lunes_esta_semana": L.isoformat(),
        "lunes_semana_siguiente": (L + dt.timedelta(days=7)).isoformat(),
        "nota": "Semanas: si no hay fila, se usa la semana tipo (fa,s1,pil,fb,s2,larga,com con z2 el día de fa). "
                "registros: feedback (rpe, cumpl, com), checkin (piernas y tobillo/rodilla de 1 a 5: 1 = molestan/cargadas, 5 = perfectos), pesos reales, rpeEj, sets. "
                "actividades: carga = TSS estimado.",
        "atleta": atleta[0] if atleta else {},
        "semanas": leer("semanas", f"user_id=eq.{uid}&semana=gte.{(L - dt.timedelta(days=21)).isoformat()}&select=semana,datos&order=semana"),
        "registros": leer("registros", f"user_id=eq.{uid}&fecha=gte.{desde}&select=fecha,datos&order=fecha"),
        "oura": leer("oura_diario", f"user_id=eq.{uid}&fecha=gte.{desde}&select=fecha,readiness,sueno_score,sueno_horas,vfc,fc_reposo,temperatura&order=fecha"),
        "actividades": acts,
        "planificados": leer("planificados", f"user_id=eq.{uid}&fecha=gte.{hoy.isoformat()}&select=fecha,titulo,dur_min,extra&order=fecha"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))


def guardar_nota(ruta):
    uid = usuario()
    n = json.load(open(ruta, encoding="utf-8"))
    if not (n.get("texto") or "").strip():
        raise SystemExit("La nota necesita 'texto'")
    hoy = dt.date.today()
    sig = lunes(hoy) + dt.timedelta(days=7) if hoy.weekday() >= 5 else lunes(hoy)
    perfil = (leer("atletas", f"user_id=eq.{uid}&select=perfil")[0]["perfil"]) or {}
    perfil["notaCoach"] = {"fecha": hoy.isoformat(), "semana": sig.isoformat(),
                           "texto": n["texto"].strip(), "ajustes": [str(a) for a in n.get("ajustes", [])][:8]}
    for k in ("objetivoSemana", "objetivoMes"):
        if n.get(k):
            perfil[k] = str(n[k])
    actualizar("atletas", f"user_id=eq.{uid}", {"perfil": perfil})
    print("Nota guardada para la semana del", sig)

    ss = n.get("semana_siguiente")
    if ss and ss.get("dias"):
        dias = ss["dias"]
        if len(dias) != 7 or any(i not in IDS for d in dias for i in d):
            raise SystemExit(f"semana_siguiente.dias no válida: {dias}")
        previa = leer("semanas", f"user_id=eq.{uid}&semana=eq.{sig.isoformat()}&select=datos")
        d = (previa[0]["datos"] if previa else {}) or {}
        d.update({"dias": dias, "comodin": ss.get("comodin") or d.get("comodin") or "bici"})
        guardar("semanas", [{"user_id": uid, "semana": sig.isoformat(), "datos": d, "actualizado": ahora()}], "user_id,semana")
        print("Semana", sig, "reorganizada:", dias)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "datos":
        datos()
    elif len(sys.argv) >= 3 and sys.argv[1] == "guardar":
        guardar_nota(sys.argv[2])
    else:
        print(__doc__)
