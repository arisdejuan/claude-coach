-- Claude Coach · envío inmediato a Garmin
-- Requiere haber ejecutado antes supabase/despertador.sql.
-- Cuando la web guarda un entreno de bici nuevo o cambiado (tabla planificados, enviado = null),
-- Supabase avisa al momento a GitHub para que lo mande a intervals.icu → Garmin (1-2 minutos).
-- El despertador de cada hora sigue de respaldo. Se puede ejecutar más de una vez.

create or replace function public.planificados_cambio()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if exists (select 1 from nuevas where enviado is null) then
    perform public.despertar_github();
  end if;
  return null;
end $$;
revoke all on function public.planificados_cambio() from public, anon, authenticated;

drop trigger if exists planificados_ins on public.planificados;
drop trigger if exists planificados_upd on public.planificados;
create trigger planificados_ins after insert on public.planificados
  referencing new table as nuevas for each statement execute function public.planificados_cambio();
create trigger planificados_upd after update on public.planificados
  referencing new table as nuevas for each statement execute function public.planificados_cambio();
