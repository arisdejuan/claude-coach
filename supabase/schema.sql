-- Claude Coach · esquema de la base de datos (Supabase)
-- Pégalo entero en Supabase → SQL Editor → Run. Se puede ejecutar más de una vez.
-- Cada fila lleva user_id: cada persona solo ve y toca lo suyo (preparado para varios atletas).

-- Perfil del atleta: FTP, RMs, peso, reto…
create table if not exists public.atletas (
  user_id uuid primary key references auth.users on delete cascade,
  nombre text,
  perfil jsonb not null default '{}'::jsonb,
  creado timestamptz not null default now()
);

-- Orden de los entrenos de cada semana y elección del comodín
create table if not exists public.semanas (
  user_id uuid not null references auth.users on delete cascade,
  semana date not null,                        -- lunes de esa semana
  datos jsonb not null default '{}'::jsonb,    -- {orden:[...], comodin:"bici"}
  actualizado timestamptz not null default now(),
  primary key (user_id, semana)
);

-- Un registro por día: check-in, series hechas, pesos reales, RPE, feedback
create table if not exists public.registros (
  user_id uuid not null references auth.users on delete cascade,
  fecha date not null,
  datos jsonb not null default '{}'::jsonb,
  actualizado timestamptz not null default now(),
  primary key (user_id, fecha)
);

-- Datos de Oura de cada mañana (los escribe la sincronización automática)
create table if not exists public.oura_diario (
  user_id uuid not null references auth.users on delete cascade,
  fecha date not null,
  readiness int,
  sueno_score int,
  sueno_horas numeric,
  vfc numeric,
  fc_reposo numeric,
  temperatura numeric,
  raw jsonb,
  actualizado timestamptz not null default now(),
  primary key (user_id, fecha)
);

-- Actividades de Strava (las escribe la sincronización automática)
create table if not exists public.actividades (
  user_id uuid not null references auth.users on delete cascade,
  id bigint not null,
  fuente text not null default 'strava',
  fecha timestamptz not null,
  tipo text,
  nombre text,
  duracion_s int,
  distancia_m numeric,
  desnivel_m numeric,
  potencia_media numeric,
  potencia_norm numeric,
  fc_media numeric,
  fc_max numeric,
  kj numeric,
  carga numeric,            -- carga estimada (tipo TSS)
  raw jsonb,
  primary key (user_id, id)
);
create index if not exists actividades_fecha on public.actividades (user_id, fecha desc);

-- Permisos de Oura/Strava de cada atleta. SOLO la sincronización (clave secreta) puede leerla.
create table if not exists public.conexiones (
  user_id uuid not null references auth.users on delete cascade,
  servicio text not null,          -- 'oura' | 'strava'
  refresh_token text not null,
  access_token text,
  expira timestamptz,
  actualizado timestamptz not null default now(),
  primary key (user_id, servicio)
);

-- ===== Seguridad: cada usuario solo ve sus filas =====
alter table public.atletas      enable row level security;
alter table public.semanas      enable row level security;
alter table public.registros    enable row level security;
alter table public.oura_diario  enable row level security;
alter table public.actividades  enable row level security;
alter table public.conexiones   enable row level security;   -- sin políticas: nadie desde la web

do $$
declare t text;
begin
  foreach t in array array['atletas','semanas','registros'] loop
    execute format('drop policy if exists "propio" on public.%I', t);
    execute format('create policy "propio" on public.%I for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid())', t);
  end loop;
  foreach t in array array['oura_diario','actividades'] loop
    execute format('drop policy if exists "leer propio" on public.%I', t);
    execute format('create policy "leer propio" on public.%I for select to authenticated using (user_id = auth.uid())', t);
  end loop;
end $$;
