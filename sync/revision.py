"""Revisión semanal del coach (la usa una tarea programada de Claude en la nube cada domingo).

Variables: SUPABASE_URL, SUPABASE_SERVICE_KEY, COACH_EMAIL

  python sync/revision.py datos              → imprime en JSON lo necesario para revisar la semana
  python sync/revision.py guardar nota.json  → guarda la nota del coach (y ajustes) para que salga en la web
  python sync/revision.py parte parte.json   → guarda el parte diario de la mañana (y reordena lo que queda de semana)
  python sync/revision.py contexto           → imprime el contexto del atleta (lesiones, objetivos, preferencias…)
  python sync/revision.py contexto_guardar archivo.md → reemplaza ese contexto (solo si el atleta lo pide)
  python sync/revision.py ausencia list
  python sync/revision.py ausencia add DESDE HASTA TIPO "nota"   (TIPO: gym, nada, vacas, esqui, enfermo)
  python sync/revision.py ausencia del DESDE
  python sync/revision.py bitacora [N]       → últimas N entradas de la bitácora del coach (qué se cambió y por qué)
  python sync/revision.py bitacora add "texto" [origen]   → apunta una entrada (origen: móvil, revisión, ordenador…)

Formato de nota.json:
{
  "texto": "Resumen y consejos (párrafos separados por línea en blanco)",
  "ajustes": ["Ajuste 1", "Ajuste 2"],                 # opcional, lista corta
  "objetivoSemana": "Objetivo de la semana que empieza", # opcional
  "objetivoMes": "…",                                   # opcional
  "semana_siguiente": {"dias": [["fa","z2"],["s1"],["pil"],["fb"],["s2"],["larga"],["com"]]}  # opcional
}
Formato de parte.json (parte diario, ver PARTE.md):
{
  "texto": "Parte de hoy (2-3 párrafos cortos)",
  "cambios": ["Salida larga movida al domingo: el sábado hiciste fuerza por la lluvia"],   # opcional
  "semana_actual": {"dias": [[...7 listas...]], "comodin": "bici|gym|descanso"}            # opcional
}
Los días ya pasados de semana_actual no se tocan (se conservan como estaban).

Ids válidos de sesión: fa, fb (fuerza), s1, s2 (rodillo series), z2 (rodillo Z2 opcional),
pil (pilates), larga (salida larga), com (comodín).
"""
import datetime as dt
import json
import os
import sys

from comun import actualizar, ahora, comprobar_entorno, guardar, leer, usuario_por_email

IDS = {"fa", "fb", "s1", "s2", "z2", "pil", "larga", "com"}
TIPOS_AUS = {"gym": "Viaje con gimnasio", "nada": "Viaje sin gimnasio", "vacas": "Vacaciones / descanso",
             "esqui": "Esquí", "enfermo": "Enfermo"}


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
                "distancia_m,desnivel_m,potencia_media,potencia_norm,fc_media,fc_max,carga,raw&order=fecha")
    out = {
        "hoy": hoy.isoformat(),
        "lunes_esta_semana": L.isoformat(),
        "lunes_semana_siguiente": (L + dt.timedelta(days=7)).isoformat(),
        "nota": "Semanas: si no hay fila, se usa la semana tipo (fa,s1,pil,fb,s2,larga,com con z2 el día de fa). "
                "registros: feedback (rpe, cumpl, com), checkin (piernas y tobillo/rodilla de 1 a 5: 1 = molestan/cargadas, 5 = perfectos), pesos reales, rpeEj, sets. "
                "actividades: carga = TSS estimado; raw.detalle (salidas en bici) = vueltas [{s segundos, w vatios, fc pulso medio, "
                "fcmax}], bloques de trabajo (≥88 % FTP) [{reps, s, w, fc, fc_ini, fc_fin}], desacople % (Pa:HR, deriva del pulso "
                "frente a vatios entre 1.ª y 2.ª mitad; <5 % buena base) y con_pulso. "
                "semana_actual_dias = lo que hay previsto cada día de esta semana (lunes → domingo). atleta.perfil.contexto = quién es y sus lesiones/objetivos (léelo SIEMPRE). "
                "atleta.perfil.ausencias = viajes/vacaciones [{tipo,desde,hasta,nota}]: esos días la web ya adapta las sesiones "
                "y una semana con 3+ días fuera cuenta como descarga (el ciclo 3+1 se reinicia). "
                "atleta.perfil.bitacora = historial de cambios y su porqué (web, móvil, revisiones): léelo antes de decidir.",
        "atleta": atleta[0] if atleta else {},
        "semanas": leer("semanas", f"user_id=eq.{uid}&semana=gte.{(L - dt.timedelta(days=21)).isoformat()}&select=semana,datos&order=semana"),
        "registros": leer("registros", f"user_id=eq.{uid}&fecha=gte.{desde}&select=fecha,datos&order=fecha"),
        "oura": leer("oura_diario", f"user_id=eq.{uid}&fecha=gte.{desde}&select=fecha,readiness,sueno_score,sueno_horas,vfc,fc_reposo,temperatura&order=fecha"),
        "actividades": acts,
        "semana_actual_dias": dias_semana(uid, L)[0],
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
    ss = n.get("semana_siguiente")
    apuntar(perfil, f"Nota del coach para la semana del {sig}" + (" y semana reordenada" if ss and ss.get("dias") else "")
            + (": " + "; ".join(str(a) for a in n.get("ajustes", [])[:4]) if n.get("ajustes") else ""))
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


DEF_DIAS = [["fa", "z2"], ["s1"], ["pil"], ["fb"], ["s2"], ["larga"], ["com"]]


def dias_semana(uid, L):
    """Días de la semana del lunes L (7 listas de ids) y los datos guardados de esa semana."""
    previa = leer("semanas", f"user_id=eq.{uid}&semana=eq.{L.isoformat()}&select=datos")
    d = (previa[0]["datos"] if previa else {}) or {}
    if d.get("dias"):
        return d["dias"], d
    orden = d.get("orden") or [x[0] for x in DEF_DIAS]
    seg = d.get("segunda") or [("z2" if i == orden.index("fa") else None) if "fa" in orden else None for i in range(7)]
    return [[x for x in (orden[i], seg[i]) if x] for i in range(7)], d


def guardar_parte(ruta):
    uid = usuario()
    n = json.load(open(ruta, encoding="utf-8"))
    if not (n.get("texto") or "").strip():
        raise SystemExit("El parte necesita 'texto'")
    hoy = dt.date.today()
    L = lunes(hoy)
    p = perfil_de(uid)
    cambios = [str(a) for a in n.get("cambios", [])][:6]
    sa = n.get("semana_actual")
    if sa and sa.get("dias"):
        dias = sa["dias"]
        if len(dias) != 7 or any(i not in IDS for d in dias for i in d):
            raise SystemExit(f"semana_actual.dias no válida: {dias}")
        antes, d = dias_semana(uid, L)
        k = hoy.weekday()
        dias = antes[:k] + dias[k:]          # lo ya pasado no se toca
        d.update({"dias": dias, "comodin": sa.get("comodin") or d.get("comodin") or "bici"})
        d.pop("orden", None); d.pop("segunda", None)
        guardar("semanas", [{"user_id": uid, "semana": L.isoformat(), "datos": d, "actualizado": ahora()}], "user_id,semana")
        print("Semana", L, "reorganizada:", dias)
    p["parte"] = {"fecha": hoy.isoformat(), "texto": n["texto"].strip(), "cambios": cambios}
    apuntar(p, "Parte del día" + (": " + "; ".join(cambios) if cambios else " (sin cambios)"), "parte")
    actualizar("atletas", f"user_id=eq.{uid}", {"perfil": p})
    print("Parte guardado para", hoy)


def apuntar(p, texto, origen="Claude"):
    """Añade una línea a la bitácora del coach (se guardan las 150 últimas)."""
    b = p.get("bitacora") or []
    b.append({"fecha": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), "origen": origen, "texto": texto.strip()})
    p["bitacora"] = b[-150:]


def bitacora(args):
    uid = usuario()
    p = perfil_de(uid)
    if args and args[0] == "add" and len(args) >= 2:
        apuntar(p, args[1], args[2] if len(args) > 2 else "Claude")
        actualizar("atletas", f"user_id=eq.{uid}", {"perfil": p})
        print("Apuntado en la bitácora")
        return
    n = int(args[0]) if args and args[0].isdigit() else 20
    for e in (p.get("bitacora") or [])[-n:]:
        print(f"{e['fecha'][:16].replace('T', ' ')} · {e.get('origen', '')} · {e['texto']}")
    if not p.get("bitacora"):
        print("(bitácora vacía)")


def perfil_de(uid):
    return (leer("atletas", f"user_id=eq.{uid}&select=perfil")[0]["perfil"]) or {}


def contexto(args):
    uid = usuario()
    p = perfil_de(uid)
    if args and args[0] == "guardar":
        texto = open(args[1], encoding="utf-8").read().strip()
        if len(texto) < 50:
            raise SystemExit("Contexto demasiado corto")
        p["contexto"] = texto
        apuntar(p, "Contexto del atleta actualizado")
        actualizar("atletas", f"user_id=eq.{uid}", {"perfil": p})
        print("Contexto guardado (", len(texto), "caracteres )")
    else:
        print(p.get("contexto") or "(sin contexto guardado)")


def ausencia(args):
    uid = usuario()
    p = perfil_de(uid)
    lista = p.get("ausencias") or []
    if not args or args[0] == "list":
        for a in sorted(lista, key=lambda x: x["desde"]):
            print(f"{a['desde']} → {a['hasta']} · {TIPOS_AUS.get(a['tipo'], a['tipo'])} · {a.get('nota', '')}")
        if not lista:
            print("(ninguna)")
        return
    if args[0] == "add" and len(args) >= 4:
        desde, hasta, tipo = args[1], args[2], args[3]
        dt.date.fromisoformat(desde), dt.date.fromisoformat(hasta)
        if tipo not in TIPOS_AUS or hasta < desde:
            raise SystemExit(f"Revisa tipo ({', '.join(TIPOS_AUS)}) y fechas")
        lista.append({"tipo": tipo, "desde": desde, "hasta": hasta, "nota": " ".join(args[4:])})
    elif args[0] == "del" and len(args) >= 2:
        antes = len(lista)
        lista = [a for a in lista if a["desde"] != args[1]]
        if len(lista) == antes:
            raise SystemExit("No hay ninguna ausencia que empiece ese día")
    else:
        raise SystemExit(__doc__)
    p["ausencias"] = lista
    apuntar(p, f"Ausencia {'añadida' if args[0] == 'add' else 'quitada'}: " + (
        f"{TIPOS_AUS[args[3]]} del {args[1]} al {args[2]} {' '.join(args[4:])}".strip() if args[0] == "add" else f"la que empezaba el {args[1]}"))
    actualizar("atletas", f"user_id=eq.{uid}", {"perfil": p})
    print("Ausencias guardadas:", len(lista))


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "datos":
        datos()
    elif len(sys.argv) >= 3 and sys.argv[1] == "parte":
        guardar_parte(sys.argv[2])
    elif len(sys.argv) >= 3 and sys.argv[1] == "guardar":
        guardar_nota(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == "contexto":
        contexto([])
    elif len(sys.argv) >= 3 and sys.argv[1] == "contexto_guardar":
        contexto(["guardar", sys.argv[2]])
    elif len(sys.argv) >= 2 and sys.argv[1] == "bitacora":
        bitacora(sys.argv[2:])
    elif len(sys.argv) >= 2 and sys.argv[1] == "ausencia":
        ausencia(sys.argv[2:])
    else:
        print(__doc__)
