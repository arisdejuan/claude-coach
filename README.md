# Claude Coach

Sistema de entrenamiento conjunto de **fuerza + bici** que se adapta a cómo llegas cada día.

- **Dashboard web** (móvil/iPad): semana, sesión del día con pesos, series de aproximación,
  feedback (peso real, RPE) y un semáforo que reajusta la sesión.
- **Aprende**: el peso de la próxima sesión sale de lo que hiciste y del RPE que apuntaste.
- **Oura y Strava automáticos**: GitHub Actions los sincroniza varias veces al día.
- **Coste cero**: GitHub Pages + GitHub Actions + Supabase (plan gratis).
- **Multi-atleta**: cada persona tiene su login y solo ve sus datos.

## Piezas

| Carpeta | Qué es |
|---|---|
| `docs/` | La web (GitHub Pages). `config.js` lleva la URL y la clave pública de Supabase. |
| `supabase/schema.sql` | Tablas y reglas de seguridad. |
| `sync/` | Scripts de Oura y Strava (`autorizar.py` se usa una sola vez por atleta). |
| `.github/workflows/sync.yml` | Sincronización automática. |

## Secretos de GitHub (Settings → Secrets and variables → Actions)

`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `OURA_CLIENT_ID`, `OURA_CLIENT_SECRET`,
`STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`.

## Añadir un atleta

1. Supabase → Authentication → Users → *Add user* (email + contraseña).
2. Crear su fila en `atletas` con su perfil (FTP, RMs, reto…).
3. `python3 sync/autorizar.py oura` y `python3 sync/autorizar.py strava` con su email.
