"""Motor de tendencias: tasa de cambio, significancia y veredicto de una serie temporal.

Implementa exactamente las fórmulas de .claude/skills/motor-tendencias/referencia.md (los números de sección
§ de cada docstring remiten a ese archivo). Todas las funciones son puras: sin red, archivos ni estado global.
Es la única fuente de los números del veredicto; nada fuera de este módulo debe recalcularlos.
"""
from __future__ import annotations

import math
from typing import Literal, NamedTuple

import numpy as np
import pymannkendall as mk
from numpy.typing import ArrayLike
from scipy import stats

UnidadTiempo = Literal["mes", "anio"]

FACTOR_DECADA: dict[str, int] = {"mes": 120, "anio": 10}
N_MINIMO = 5
N_MINIMO_HAMED_RAO = 10
CLAVES_SALIDA: tuple[str, ...] = (
    "variable", "region", "periodo", "n", "r1", "n_ef",
    "pendiente_ols_decada", "ic95_decada", "p_t",
    "sen_decada", "mk_z", "mk_tau", "p_mk",
    "cambio_pct_decada", "snr", "n_star_anios", "anios_faltantes",
    "veredicto", "direccion", "metodos",
)


class ResultadoOLS(NamedTuple):
    """Ajuste y = β₀ + β₁·t. beta0 en unidades de y; beta1 en unidades de y por unidad de t."""

    beta0: float
    beta1: float
    residuos: np.ndarray
    sxx: float


class ResultadoT(NamedTuple):
    """Prueba t corregida. se e ic95 en unidades de y por unidad de t; p entre 0 y 1."""

    se: float
    t: float
    gl: float
    p: float
    ic95: tuple[float, float]


class ResultadoMK(NamedTuple):
    """Mann-Kendall: z (normal estándar), tau (−1 a 1), p (0 a 1) y método usado."""

    z: float
    tau: float
    p: float
    metodo: str


def _limpiar(y: ArrayLike, t: ArrayLike) -> tuple[np.ndarray, np.ndarray]:
    """§0. Convierte a float64, quita pares con NaN/inf y ordena por t."""
    y = np.asarray(y, dtype=np.float64).ravel()
    t = np.asarray(t, dtype=np.float64).ravel()
    if y.shape != t.shape:
        raise ValueError(f"y y t deben tener la misma longitud ({y.size} ≠ {t.size})")
    valido = np.isfinite(y) & np.isfinite(t)
    y, t = y[valido], t[valido]
    orden = np.argsort(t, kind="stable")
    y, t = y[orden], t[orden]
    if y.size < N_MINIMO:
        raise ValueError(f"serie demasiado corta: {y.size} datos válidos (mínimo {N_MINIMO})")
    if np.unique(t).size < 2:
        raise ValueError("el eje de tiempo necesita al menos dos valores distintos")
    return y, t


def ols(y: np.ndarray, t: np.ndarray) -> ResultadoOLS:
    """§1. Mínimos cuadrados y = β₀ + β₁·t.

    Entrada: y (unidades de y), t (unidad de tiempo). Salida: β₀ (unidades de y), β₁ (unidades de y por unidad de t),
    residuos (unidades de y) y Sxx = Σ(t − t̄)² (unidad de tiempo al cuadrado).
    """
    y = np.asarray(y, dtype=np.float64)
    t = np.asarray(t, dtype=np.float64)
    dt = t - t.mean()
    sxx = float(np.sum(dt**2))
    beta1 = float(np.sum(dt * (y - y.mean())) / sxx)
    beta0 = float(y.mean() - beta1 * t.mean())
    residuos = y - (beta0 + beta1 * t)
    return ResultadoOLS(beta0, beta1, residuos, sxx)


def n_efectivo(residuos: np.ndarray) -> tuple[float, float]:
    """§2. Autocorrelación lag-1 de los residuos y número efectivo de datos.

    Entrada: residuos (unidades de y). Salida: (r₁ adimensional, n_ef acotado a [3, n]).
    """
    e = np.asarray(residuos, dtype=np.float64)
    n = e.size
    if n < 3 or np.std(e[:-1]) == 0 or np.std(e[1:]) == 0:
        r1 = 0.0
    else:
        r1 = float(np.corrcoef(e[:-1], e[1:])[0, 1])
    if r1 <= -1.0:
        n_ef = float(n)
    else:
        n_ef = n * (1.0 - r1) / (1.0 + r1)
    n_ef = float(min(max(n_ef, 3.0), float(n)))
    return r1, n_ef


def prueba_t_corregida(beta1: float, residuos: np.ndarray, sxx: float, n_ef: float) -> ResultadoT:
    """§3. Prueba t con gl = n_ef − 2 e IC 95 % de la pendiente.

    Entrada: β₁ (unidades de y por unidad de t), residuos (unidades de y), Sxx, n_ef.
    Salida: SE e IC 95 % en unidades de y por unidad de t; t; gl; p bilateral (0–1).
    """
    e = np.asarray(residuos, dtype=np.float64)
    gl = n_ef - 2.0
    s2 = float(np.sum(e**2)) / gl
    se = math.sqrt(s2) / math.sqrt(sxx)
    t_crit = float(stats.t.ppf(0.975, gl))
    if se == 0.0:  # §11: serie constante o ajuste perfecto
        p = 1.0 if beta1 == 0.0 else 0.0
        t_est = 0.0 if beta1 == 0.0 else math.copysign(math.inf, beta1)
        return ResultadoT(0.0, t_est, gl, p, (beta1, beta1))
    t_est = beta1 / se
    p = float(2.0 * stats.t.sf(abs(t_est), gl))
    return ResultadoT(se, t_est, gl, p, (beta1 - t_crit * se, beta1 + t_crit * se))


def mann_kendall(y: np.ndarray, alfa: float = 0.05) -> ResultadoMK:
    """§4. Mann-Kendall con modificación de Hamed-Rao; si n < 10, falla o da p no finito, usa la prueba original.

    Entrada: y en orden temporal. Salida: z, tau, p (0–1) y "mk_hamed_rao" o "mk_original".
    """
    y = np.asarray(y, dtype=np.float64)
    if y.size >= N_MINIMO_HAMED_RAO:
        try:
            r = mk.hamed_rao_modification_test(y, alpha=alfa)
            if np.isfinite(r.p) and np.isfinite(r.z):
                return ResultadoMK(float(r.z), float(r.Tau), float(r.p), "mk_hamed_rao")
        except (ValueError, ZeroDivisionError, FloatingPointError, np.linalg.LinAlgError):
            pass
    r = mk.original_test(y, alpha=alfa)
    p = float(r.p) if np.isfinite(r.p) else 1.0
    z = float(r.z) if np.isfinite(r.z) else 0.0
    tau = float(r.Tau) if np.isfinite(r.Tau) else 0.0
    return ResultadoMK(z, tau, p, "mk_original")


def pendiente_sen(y: np.ndarray, t: np.ndarray) -> float:
    """§5. Pendiente de Sen: mediana de (y_j − y_k)/(t_j − t_k) para j > k, con los t reales.

    Entrada: y (unidades de y), t (unidad de tiempo). Salida: unidades de y por unidad de t.
    """
    y = np.asarray(y, dtype=np.float64)
    t = np.asarray(t, dtype=np.float64)
    j, k = np.triu_indices(y.size, k=1)
    dt = t[k] - t[j]
    validos = dt != 0
    return float(np.median((y[k] - y[j])[validos] / dt[validos]))


def anios_para_detectar(
    beta1: float, residuos: np.ndarray, r1: float, n: int, unidad_tiempo: UnidadTiempo
) -> tuple[float | None, float | None, str | None]:
    """§7. Años necesarios para detectar la tendencia (Weatherhead et al., 1998). Solo datos mensuales.

    Entrada: β₁ (unidades de y por mes), residuos mensuales, r₁, n (meses).
    Salida: (n* en años, años faltantes ≥ 0, nota para 'metodos' o None).
    """
    if unidad_tiempo != "mes":
        return None, None, "n_star_no_aplica_anual"
    omega = beta1 * 12.0
    sigma_n = float(np.std(residuos, ddof=1))
    phi = r1
    if omega == 0.0 or phi >= 1.0 or phi <= -1.0:
        return None, None, "n_star_indefinido"
    n_star = ((3.3 * sigma_n / abs(omega)) * math.sqrt((1.0 + phi) / (1.0 - phi))) ** (2.0 / 3.0)
    faltantes = max(0.0, n_star - n / 12.0)
    return float(n_star), float(faltantes), None


def veredicto(p_t: float, p_mk: float, sen: float, alfa: float = 0.05) -> tuple[str, str]:
    """§9. Veredicto ("significativo" | "indicio" | "sin tendencia clara") y dirección ("sube" | "baja" | "estable")."""
    sig_t = p_t < alfa
    sig_mk = p_mk < alfa
    if sig_t and sig_mk:
        v = "significativo"
    elif sig_t or sig_mk:
        v = "indicio"
    else:
        v = "sin tendencia clara"
    d = "sube" if sen > 0 else "baja" if sen < 0 else "estable"
    return v, d


def calcular_tendencia(
    y: ArrayLike,
    t: ArrayLike,
    *,
    unidad_tiempo: UnidadTiempo,
    variable: str,
    region: str,
    periodo: tuple[str, str] | list[str],
    media_climatologia: float | None = None,
    alfa: float = 0.05,
) -> dict:
    """Calcula tendencia y significancia de una serie y devuelve el dict JSON del motor (§10).

    Entrada:
        y: serie (anomalías mensuales o serie anual) en las unidades de la variable; puede tener NaN.
        t: eje de tiempo en meses (unidad_tiempo="mes") o años (unidad_tiempo="anio").
        media_climatologia: media de la climatología en las unidades de y, para el cambio %.
    Salida (claves en CLAVES_SALIDA): pendientes e IC en unidades de y por década; p-valores 0–1;
        cambio_pct_decada en % por década; snr adimensional; n_star_anios y anios_faltantes en años.
    """
    if unidad_tiempo not in FACTOR_DECADA:
        raise ValueError(f"unidad_tiempo debe ser 'mes' o 'anio', no {unidad_tiempo!r}")
    yv, tv = _limpiar(y, t)
    n = int(yv.size)
    k = FACTOR_DECADA[unidad_tiempo]
    metodos = ["ols_neff"]

    ajuste = ols(yv, tv)
    r1, n_ef = n_efectivo(ajuste.residuos)
    prueba = prueba_t_corregida(ajuste.beta1, ajuste.residuos, ajuste.sxx, n_ef)
    resultado_mk = mann_kendall(yv, alfa)
    metodos.append(resultado_mk.metodo)
    sen = pendiente_sen(yv, tv)

    pendiente_decada = ajuste.beta1 * k
    if media_climatologia is None or media_climatologia == 0 or not np.isfinite(media_climatologia):
        cambio_pct = None
    else:
        cambio_pct = float(100.0 * pendiente_decada / media_climatologia)

    sigma_y = float(np.std(yv, ddof=1))
    snr = float(pendiente_decada / sigma_y) if sigma_y > 0 else None

    n_star, faltantes, nota = anios_para_detectar(ajuste.beta1, ajuste.residuos, r1, n, unidad_tiempo)
    if nota:
        metodos.append(nota)

    ver, direccion = veredicto(prueba.p, resultado_mk.p, sen, alfa)

    resultado = {
        "variable": str(variable),
        "region": str(region),
        "periodo": [str(periodo[0]), str(periodo[1])],
        "n": n,
        "r1": float(r1),
        "n_ef": float(n_ef),
        "pendiente_ols_decada": float(pendiente_decada),
        "ic95_decada": [float(prueba.ic95[0] * k), float(prueba.ic95[1] * k)],
        "p_t": float(prueba.p),
        "sen_decada": float(sen * k),
        "mk_z": float(resultado_mk.z),
        "mk_tau": float(resultado_mk.tau),
        "p_mk": float(resultado_mk.p),
        "cambio_pct_decada": cambio_pct,
        "snr": snr,
        "n_star_anios": n_star,
        "anios_faltantes": faltantes,
        "veredicto": ver,
        "direccion": direccion,
        "metodos": metodos,
    }
    return resultado
