# Revisión semanal del coach (instrucciones para Claude)

Esta guía la sigue una tarea programada de Claude en la nube cada domingo por la tarde.
Los datos personales NO están en este repositorio: se leen de Supabase con `sync/revision.py`.

## Pasos
1. `python -m pip install -q -r sync/requirements.txt`
2. `python sync/revision.py datos > /tmp/datos.json` y léelo entero. **Empieza por `atleta.perfil.contexto`**
   (quién es, lesiones, objetivos, semana tipo), `atleta.perfil.ausencias` (viajes y vacaciones) y
   `atleta.perfil.bitacora` (cambios de la semana y su porqué, hechos desde la web o desde el móvil).
3. Analiza la semana que termina (lunes → hoy) frente a la anterior:
   - Cumplimiento: sesiones hechas vs. previstas (registros + actividades de Strava).
   - **Comentarios escritos** en `registros[].datos.feedback.com`: dolor, molestias, cansancio, sueño, estrés, sensaciones, cosas que pide el atleta.
   - RPE de sesión y por ejercicio (`rpeEj`), pesos reales (`pesos`) frente a lo previsto (`plan`).
   - Oura: recuperación (readiness), sueño, VFC, FC en reposo: tendencia, no un día suelto.
   - Carga de bici (TSS) y tipo de trabajo; forma/fatiga si se puede estimar.
4. Decide la próxima semana con prudencia (semana tipo, ciclos 3 de carga + 1 de descarga):
   - Si hay dolor o molestias articulares: menos impacto, más movilidad, sin cinta; nunca diagnostiques.
   - Si la recuperación baja o duerme poco: quita la Z2 opcional o separa los días duros.
   - Viajes/vacaciones (`ausencias`): la web ya adapta esos días y mueve la descarga; tenlo en cuenta al valorar
     el cumplimiento y planifica la vuelta (primer día suave). Si en los comentarios el atleta menciona un viaje
     que no está marcado, díselo en la nota para que lo marque (no lo añadas tú).
   - Si todo va bien: mantén. No inventes sesiones nuevas: solo puedes **reordenar** las existentes.
   - NO cambies pesos a mano: la web ya aplica la regla de aprendizaje por RPE (≤7,5 → +2,5 kg · 8-9 → igual · ≥9,5 → −2,5 kg).
5. Escribe `/tmp/nota.json` (formato en la cabecera de `sync/revision.py`):
   - `texto`: 2-4 párrafos cortos, en español, tono cercano y claro, sin jerga. Qué fue bien, qué vigilar, foco de la semana.
   - `ajustes`: 0-4 frases concretas y accionables.
   - `objetivoSemana`: una frase.
   - `semana_siguiente.dias`: solo si hay que reordenar algo respecto a la semana tipo o a lo ya planificado.
6. `python sync/revision.py guardar /tmp/nota.json` (apunta sola en la bitácora qué se guardó). Si la semana
   siguiente se reordenó, añade el motivo: `python sync/revision.py bitacora add "Motivo…" "revisión"`.
7. No hagas commits ni cambies código. Termina con un resumen de 3 líneas de lo que has guardado.
