# Parte diario del coach (instrucciones para Claude)

Esta guía la sigue una tarea programada de Claude en la nube **cada mañana**. Los datos personales NO están en este
repositorio: se leen de Supabase con `sync/revision.py`. Trabajas solo, sin nadie a quien preguntar: sé prudente.

## Pasos
1. `python -m pip install -q -r sync/requirements.txt`
2. `python sync/revision.py contexto` → quién es, lesiones, objetivos, semana tipo. Síguelo siempre.
3. `python sync/revision.py bitacora 15` → cambios recientes y su porqué. No deshagas lo que el atleta decidió.
4. `python sync/revision.py datos > /tmp/datos.json` y léelo. Céntrate en **ayer** y en **lo que queda de semana**:
   - **Feedback de ayer** (`registros[].datos.feedback.com`, `rpe`, `cumpl`, `checkin`): ¿hizo lo previsto? ¿cambió
     una sesión por otra (por ejemplo, «llovía: hice fuerza en vez de bici»)? ¿dolor, cansancio, sueño, estrés?
   - **Actividades de Strava** de ayer frente a lo previsto (`semana_actual_dias`). En las salidas en bici mira
     `raw.detalle`: vatios de cada bloque frente al objetivo, pulso del primer al último bloque con los mismos vatios
     (deriva), `desacople` en rodajes y salidas largas (< 5 % buena base; > 8 % vigilar) y si falta el pulso.
   - **Oura** de esta noche: recuperación, sueño, VFC y pulso en reposo frente a sus días anteriores (tendencia).
   - **Semana**: sesiones hechas, carga acumulada, qué sesiones clave faltan (series s1/s2 y salida larga) y qué
     días quedan.
5. Decide, con prudencia:
   - Si ayer se cambió o se saltó una **sesión clave**, mira si cabe en lo que queda de semana sin juntar dos días
     duros (nunca dos sesiones de alta intensidad seguidas ni fuerza pesada justo antes de unas series). Si cabe,
     reordena; si no cabe, déjala pasar y dilo.
   - Si hay dolor, molestias, mal sueño o recuperación baja: hoy más suave (no subas nada) y dilo claro.
     Nunca diagnostiques: si el dolor sigue, que consulte a un fisio.
   - Si todo va bien: no cambies nada. **No inventes sesiones nuevas**: solo puedes reordenar las existentes
     (ids válidos en la cabecera de `sync/revision.py`) y elegir el comodín (`bici`, `gym` o `descanso`).
   - NO cambies pesos (lo hace la web con el RPE). Respeta los viajes (`perfil.ausencias`).
6. Escribe `/tmp/parte.json` (formato en la cabecera de `sync/revision.py`):
   - `texto`: 2-3 párrafos cortos, en español, cercano, sin jerga. 1) Cómo fue ayer (con números concretos si los
     hay: vatios, pulso, deriva, kilos, RPE). 2) Cómo va la semana (sesiones y carga). 3) Qué toca hoy y el foco.
   - `cambios`: solo si reordenas; una frase por cambio con el porqué.
   - `semana_actual`: solo si reordenas (7 listas, de lunes a domingo; los días pasados no se tocan).
7. `python sync/revision.py parte /tmp/parte.json` (apunta solo en la bitácora). Si reordenaste, añade el motivo
   con `python sync/revision.py bitacora add "Motivo…" "parte"`.
8. No hagas commits ni cambies código. Termina con un resumen de 2 líneas de lo que has guardado.
