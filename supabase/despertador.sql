-- Claude Coach · despertador (Supabase → GitHub Actions)
-- El cron de GitHub a veces no se ejecuta. Supabase llama cada hora a GitHub para lanzar
-- la sincronización (Oura + Strava + envío a Garmin). Gratis: pg_cron + pg_net + Vault.
--
-- Uso: pégalo en Supabase → SQL Editor, cambia las DOS líneas marcadas con "CAMBIA" y pulsa Run.
-- Se puede ejecutar más de una vez (p. ej. para cambiar la llave cuando caduque).
-- La llave es un "fine-grained token" de GitHub con acceso solo a tu repositorio
-- y permiso Actions: Read and write.

create extension if not exists pg_cron;
create extension if not exists pg_net;

do $$
declare
  llave text := 'PEGA_AQUI_TU_LLAVE';                 -- <- CAMBIA tu llave github_pat_…
  repo  text := 'arisdejuan/claude-coach';            -- <- CAMBIA tu usuario/repositorio de GitHub
begin
  -- Guarda (o actualiza) los datos en la caja fuerte de Supabase (Vault), cifrados
  if exists (select 1 from vault.secrets where name = 'github_llave') then
    perform vault.update_secret((select id from vault.secrets where name = 'github_llave'), llave);
  else
    perform vault.create_secret(llave, 'github_llave');
  end if;
  if exists (select 1 from vault.secrets where name = 'github_repo') then
    perform vault.update_secret((select id from vault.secrets where name = 'github_repo'), repo);
  else
    perform vault.create_secret(repo, 'github_repo');
  end if;
end $$;

-- Función que avisa a GitHub para que ejecute la sincronización
create or replace function public.despertar_github()
returns bigint
language sql
security definer
set search_path = public
as $$
  select net.http_post(
    url := 'https://api.github.com/repos/'
           || (select decrypted_secret from vault.decrypted_secrets where name = 'github_repo')
           || '/actions/workflows/sync.yml/dispatches',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || (select decrypted_secret from vault.decrypted_secrets where name = 'github_llave'),
      'Accept', 'application/vnd.github+json',
      'X-GitHub-Api-Version', '2022-11-28',
      'User-Agent', 'claude-coach'
    ),
    body := '{"ref":"main"}'::jsonb
  );
$$;
revoke all on function public.despertar_github() from public, anon, authenticated;

-- Cada hora, de 5:05 a 23:05 (hora de Ámsterdam en invierno; el reloj va en UTC)
select cron.schedule('despertar-github', '5 4-22 * * *', 'select public.despertar_github()');

-- Prueba ahora mismo (en GitHub → Actions debe empezar una ejecución en unos segundos)
select public.despertar_github();
