"""Configuración del backend leída de variables de entorno (arquitectura OPeNDAP en memoria RAM).

Variables:
    NASA_CORS_ORIGINS       orígenes permitidos para el frontend, separados por comas ("*" = todos).
    NASA_CACHE_MEMORIA_MAX  número máximo de cubos regionales en la caché LRU en RAM (por defecto 128).
    NASA_OPENDAP_WORKERS    hilos simultáneos para consultar rebanadas OPeNDAP en memoria (por defecto 6).
    NASA_OPENDAP_TIMEOUT    timeout HTTP en segundos por petición OPeNDAP (por defecto 60).
    NASA_MAX_DESCARGAS      tareas de precarga OPeNDAP simultáneas en segundo plano (por defecto 2).
    NASA_MAX_PIXELES        tope de píxeles para el mapa de tendencias en una petición síncrona.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DIR_RECURSOS = Path(__file__).resolve().parent / "recursos"

PERIODO_COMUN: tuple[str, str] = ("2001-01", "2024-12")   # todas las fuentes lo cubren: para comparar variables
PERIODO_GLOBAL: tuple[str, str] = ("1983-01", "2024-12")  # GPCP / MERRA-2

_CORS_POR_DEFECTO = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"


@dataclass(frozen=True)
class Ajustes:
    cors_origins: tuple[str, ...]
    cache_memoria_max: int
    opendap_workers: int
    opendap_timeout: int
    max_descargas: int
    max_pixeles: int
    ruta_catalogo: Path
    ruta_regiones: Path


@lru_cache(maxsize=1)
def obtener_ajustes() -> Ajustes:
    """Lee el entorno una vez. En tests, llama a obtener_ajustes.cache_clear() tras cambiar variables."""
    origenes = os.environ.get("NASA_CORS_ORIGINS", _CORS_POR_DEFECTO)
    return Ajustes(
        cors_origins=tuple(o.strip() for o in origenes.split(",") if o.strip()),
        cache_memoria_max=max(8, int(os.environ.get("NASA_CACHE_MEMORIA_MAX", "128"))),
        opendap_workers=max(1, int(os.environ.get("NASA_OPENDAP_WORKERS", "6"))),
        opendap_timeout=max(5, int(os.environ.get("NASA_OPENDAP_TIMEOUT", "60"))),
        max_descargas=max(1, int(os.environ.get("NASA_MAX_DESCARGAS", "2"))),
        max_pixeles=max(1, int(os.environ.get("NASA_MAX_PIXELES", "20000"))),
        ruta_catalogo=Path(os.environ.get("NASA_CATALOGO", DIR_RECURSOS / "catalogo.yaml")),
        ruta_regiones=Path(os.environ.get("NASA_REGIONES", DIR_RECURSOS / "regiones.yaml")),
    )
