"""Plantilla de motor/tendencias.py — firmas, tipos y esquema de salida.

Copiar a motor/tendencias.py y completar cada función siguiendo referencia.md (las fórmulas
exactas están allí, con el número de sección indicado en cada docstring).
Reglas: funciones puras (sin red, archivos ni print), float64, salida con tipos nativos de Python.
"""
from __future__ import annotations

from typing import Literal, NamedTuple

import numpy as np
from numpy.typing import ArrayLike

UnidadTiempo = Literal["mes", "anio"]
FACTOR_DECADA: dict[str, int] = {"mes": 120, "anio": 10}
CLAVES_SALIDA: tuple[str, ...] = (
    "variable", "region", "periodo", "n", "r1", "n_ef",
    "pendiente_ols_decada", "ic95_decada", "p_t",
    "sen_decada", "mk_z", "mk_tau", "p_mk",
    "cambio_pct_decada", "snr", "n_star_anios", "anios_faltantes",
    "veredicto", "direccion", "metodos",
)


class ResultadoOLS(NamedTuple):
    beta0: float          # unidades de y
    beta1: float          # unidades de y por unidad de t
    residuos: np.ndarray  # unidades de y
    sxx: float            # Σ(t − t̄)², unidades de t²


class ResultadoT(NamedTuple):
    se: float             # unidades de y por unidad de t
    t: float
    gl: float
    p: float
    ic95: tuple[float, float]  # unidades de y por unidad de t


class ResultadoMK(NamedTuple):
    z: float
    tau: float
    p: float
    metodo: str           # "mk_hamed_rao" | "mk_original"


def ols(y: np.ndarray, t: np.ndarray) -> ResultadoOLS:
    """§1. Mínimos cuadrados y = β₀ + β₁·t."""
    raise NotImplementedError


def n_efectivo(residuos: np.ndarray) -> tuple[float, float]:
    """§2. Devuelve (r₁, n_ef) con n_ef acotado a [3, n]."""
    raise NotImplementedError


def prueba_t_corregida(beta1: float, residuos: np.ndarray, sxx: float, n_ef: float) -> ResultadoT:
    """§3. Prueba t con gl = n_ef − 2 e IC 95 %."""
    raise NotImplementedError


def mann_kendall(y: np.ndarray, alfa: float = 0.05) -> ResultadoMK:
    """§4. Hamed-Rao con alternativa original_test (n < 10, excepción o p no finito)."""
    raise NotImplementedError


def pendiente_sen(y: np.ndarray, t: np.ndarray) -> float:
    """§5. Mediana de (y_j − y_k)/(t_j − t_k), j > k. Unidades de y por unidad de t."""
    raise NotImplementedError


def anios_para_detectar(beta1_mes: float, residuos: np.ndarray, r1: float, n: int) -> tuple[float | None, float | None]:
    """§7. Weatherhead (solo mensual). Devuelve (n_star_anios, anios_faltantes) o (None, None)."""
    raise NotImplementedError


def veredicto(p_t: float, p_mk: float, sen: float, alfa: float = 0.05) -> tuple[str, str]:
    """§9. Devuelve (veredicto, direccion)."""
    raise NotImplementedError


def calcular_tendencia(
    y: ArrayLike, t: ArrayLike, *,
    unidad_tiempo: UnidadTiempo,
    variable: str, region: str, periodo: tuple[str, str],
    media_climatologia: float | None = None,
    alfa: float = 0.05,
) -> dict:
    """Calcula tendencia y significancia. Devuelve un dict con CLAVES_SALIDA (§10).

    Entrada: y en sus unidades (p. ej. mm/mes de anomalía); t en meses o años según unidad_tiempo.
    Salida: pendientes en unidades de y por década; p-valores 0–1; n* en años.
    """
    raise NotImplementedError
