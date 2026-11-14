"""Fixtures compartidos (skill validacion-y-pruebas)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
RUTA_SRC = RAIZ_BACKEND / "src"
for _p in (str(RUTA_SRC), str(RAIZ_BACKEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def generar_serie_ar1(
    n: int,
    pendiente: float,
    phi: float,
    sigma: float = 1.0,
    semilla: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """(t, y) con t = 0..n-1 y y = pendiente·t + ruido AR(1) estacionario de desviación marginal sigma."""
    rng = np.random.default_rng(semilla)
    eta = rng.normal(0.0, sigma * np.sqrt(1 - phi**2), size=n)
    e = np.empty(n)
    e[0] = rng.normal(0.0, sigma)
    for i in range(1, n):
        e[i] = phi * e[i - 1] + eta[i]
    t = np.arange(n, dtype=float)
    return t, pendiente * t + e


@pytest.fixture
def serie_ar1():
    """Devuelve la función generadora para usarla con distintos parámetros dentro del test."""
    return generar_serie_ar1


@pytest.fixture
def dir_datos_temporal(tmp_path: Path) -> Path:
    """Limpia la caché en memoria RAM antes y después de cada test (sin archivos en disco)."""
    from core.config import obtener_ajustes
    from core.motor.datos import limpiar_cache_memoria
    from core.motor.escaner import limpiar_cache_mapas_memoria

    limpiar_cache_memoria()
    limpiar_cache_mapas_memoria()
    obtener_ajustes.cache_clear()
    yield tmp_path
    limpiar_cache_memoria()
    limpiar_cache_mapas_memoria()
    obtener_ajustes.cache_clear()
