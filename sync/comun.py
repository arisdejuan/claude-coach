"""Utilidades compartidas: hablar con Supabase usando la clave secreta (service role).

Variables de entorno (GitHub Secrets):
  SUPABASE_URL          https://xxxx.supabase.co
  SUPABASE_SERVICE_KEY  clave "service_role" (secreta, nunca en la web)
"""
import os
import sys
import time

import requests
from datetime import datetime, timezone

URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")


def ahora():
    return datetime.now(timezone.utc).isoformat()


def _cab(extra=None):
    h = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h


def comprobar_entorno(*nombres):
    faltan = [n for n in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", *nombres) if not os.environ.get(n)]
    if faltan:
        print("Faltan variables:", ", ".join(faltan))
        sys.exit(1)


def peticion(metodo, url, reintentos=4, **kw):
    """Petición HTTP con reintentos (las APIs fallan a veces)."""
    for intento in range(reintentos):
        try:
            r = requests.request(metodo, url, timeout=30, **kw)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"{r.status_code} {r.text[:200]}")
            return r
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
            if intento == reintentos - 1:
                raise
            espera = 2 ** intento * 3
            print(f"  reintento en {espera}s ({e})")
            time.sleep(espera)


def leer(tabla, filtro=""):
    r = peticion("GET", f"{URL}/rest/v1/{tabla}?{filtro}", headers=_cab())
    r.raise_for_status()
    return r.json()


def guardar(tabla, filas, conflicto):
    """Inserta o actualiza filas (upsert)."""
    if not filas:
        return
    r = peticion(
        "POST",
        f"{URL}/rest/v1/{tabla}?on_conflict={conflicto}",
        headers=_cab({"Prefer": "resolution=merge-duplicates,return=minimal"}),
        json=filas,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"Supabase {tabla}: {r.status_code} {r.text[:300]}")


def conexiones(servicio):
    return leer("conexiones", f"servicio=eq.{servicio}&select=*")


def guardar_conexion(user_id, servicio, refresh, access=None, expira=None):
    guardar(
        "conexiones",
        [{"user_id": user_id, "servicio": servicio, "refresh_token": refresh,
          "access_token": access, "expira": expira, "actualizado": ahora()}],
        "user_id,servicio",
    )


def perfil(user_id):
    filas = leer("atletas", f"user_id=eq.{user_id}&select=perfil")
    return (filas[0]["perfil"] if filas else {}) or {}
