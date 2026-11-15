"""tendencias_demo_corregido.py — tendencias de la demo Down to Earth (versión revisada).

Recibe el DataFrame mensual regional con columnas:
    fecha, P (mm/mes), T (°C), SM (m³/m³), ET (mm/mes)
y devuelve lo que pinta la pantalla de resultados.

Cambios respecto a la versión original (detalle en respuesta.md):
  1. Los huecos se dejan como NaN (antes se rellenaban con 0).
  2. Agregación anual por variable: P y ET se suman (mm/año), T y SM se promedian.
  3. Solo se usan años completos (12 meses válidos); años parciales se descartan.
  4. Tendencia por MCO con corrección por autocorrelación AR(1) de los residuos
     (tamaño muestral efectivo, Santer et al. 2000, con r1 corregido por sesgo
     de muestra corta) y distribución t; se reporta
     además la pendiente de Theil-Sen como chequeo de robustez.
  5. El p-valor ya NO se multiplica por 10: los p-valores no se escalan por década.
  6. La corrección por comparaciones múltiples (Holm) se hace sobre una familia
     FIJA (todas las variables analizadas), no sobre lo que el usuario deja visible.
  7. Un resultado no significativo se etiqueta "no concluyente", no "sin cambio".
  8. Unidades de la pendiente correctas ("mm/año por década", etc.).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

VARIABLES = ["P", "T", "SM", "ET"]

# Cómo se agrega cada variable de mensual a anual.
AGREGACION_ANUAL = {"P": "sum", "T": "mean", "SM": "mean", "ET": "sum"}

# Unidades de la pendiente: (unidad del valor anual) por década.
UNIDADES_DECADA = {
    "P": "mm/año por década",
    "T": "°C por década",
    "SM": "m³/m³ por década",
    "ET": "mm/año por década",
}

VALORES_FALTANTES = (-9999, -9999.0, -999, -999.0)
MIN_MESES_POR_ANIO = 12
MIN_ANIOS = 10
ALFA = 0.05


# --------------------------------------------------------------------------- #
# Preparación
# --------------------------------------------------------------------------- #
def preparar_mensual(df: pd.DataFrame) -> pd.DataFrame:
    """Indexa por fecha, ordena y marca los faltantes como NaN (sin rellenar)."""
    faltan = [c for c in ["fecha", *VARIABLES] if c not in df.columns]
    if faltan:
        raise ValueError(f"Faltan columnas en el DataFrame: {faltan}")

    df = df.copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.set_index("fecha").sort_index()
    if df.index.has_duplicates:
        raise ValueError("Hay fechas duplicadas en la serie mensual.")
    df[VARIABLES] = df[VARIABLES].apply(pd.to_numeric, errors="coerce")
    df[VARIABLES] = df[VARIABLES].replace(list(VALORES_FALTANTES), np.nan)
    # Los huecos se quedan como NaN: un 0 es un valor físico real
    # (0 °C, 0 mm de lluvia, suelo seco) y sesgaría sumas, medias y tendencias.
    return df


def anualizar(df_mensual: pd.DataFrame, min_meses: int = MIN_MESES_POR_ANIO) -> pd.DataFrame:
    """Serie anual por variable; años con menos de `min_meses` meses válidos -> NaN."""
    # Reindexa a meses calendario para que un mes ausente cuente como faltante.
    mensual = df_mensual[VARIABLES].resample("MS").mean()
    grupos = mensual.groupby(mensual.index.year)

    validos = grupos.count()
    anual = pd.DataFrame(
        {v: getattr(grupos[v], AGREGACION_ANUAL[v])() for v in VARIABLES}
    )
    # Año incompleto: sumar o promediar solo parte del ciclo estacional sesga el valor.
    anual = anual.where(validos >= min_meses)
    anual.index.name = "anio"
    return anual


# --------------------------------------------------------------------------- #
# Tendencia
# --------------------------------------------------------------------------- #
def tendencia(serie_anual: pd.Series, alfa: float = ALFA) -> dict:
    """Pendiente MCO con corrección AR(1) (n efectivo) + Theil-Sen como contraste.

    Devuelve pendientes e IC en unidades por década y el p-valor bilateral
    (sin escalar: el p-valor es el mismo se exprese la pendiente por año o por década).
    """
    s = serie_anual.dropna()
    n = len(s)
    if n < MIN_ANIOS:
        return {"n_anios": n, "suficiente": False}

    t = s.index.to_numpy(dtype=float)
    y = s.to_numpy(dtype=float)
    t_c = t - t.mean()

    # MCO
    sxx = np.sum(t_c**2)
    b = np.sum(t_c * (y - y.mean())) / sxx
    a = y.mean()
    resid = y - (a + b * t_c)

    # Autocorrelación lag-1 de los residuos y n efectivo (Santer et al. 2000).
    # Si hay años faltantes en medio, el lag-1 se calcula solo entre años consecutivos.
    consecutivos = np.diff(t) == 1
    if consecutivos.sum() >= 3:
        r0, r1v = resid[:-1][consecutivos], resid[1:][consecutivos]
        r1 = float(np.sum(r0 * r1v) / np.sqrt(np.sum(r0**2) * np.sum(r1v**2)))
    else:
        r1 = 0.0
    # El r1 de residuos de una serie corta está sesgado hacia abajo; corrección
    # aproximada de primer orden para no subestimar la autocorrelación.
    r1 = r1 + (1 + 4 * r1) / n
    # Autocorrelación negativa: no se "premia" con más n; tope para evitar n_eff ~ 0.
    r1 = float(min(max(r1, 0.0), 0.95))
    n_eff = n * (1 - r1) / (1 + r1)
    n_eff = float(min(max(n_eff, 3.0), n))  # al menos 1 grado de libertad
    gl = n_eff - 2

    s2 = np.sum(resid**2) / gl
    se_b = np.sqrt(s2 / sxx)
    t_stat = b / se_b
    p = float(2 * stats.t.sf(abs(t_stat), gl))
    t_crit = stats.t.ppf(1 - alfa / 2, gl)

    # Theil-Sen (robusto a atípicos) como chequeo de coherencia.
    sen = stats.theilslopes(y, t)

    return {
        "n_anios": n,
        "suficiente": True,
        "anio_inicio": int(t.min()),
        "anio_fin": int(t.max()),
        "pendiente_decada": float(b) * 10,
        "ic95": [float(b - t_crit * se_b) * 10, float(b + t_crit * se_b) * 10],
        "p": p,
        "r1": r1,
        "n_efectivo": n_eff,
        "pendiente_sen_decada": float(sen.slope) * 10,
    }


def holm(pvalores: dict[str, float]) -> dict[str, float]:
    """Corrección de Holm-Bonferroni (controla FWER, más potente que Bonferroni)."""
    claves = sorted(pvalores, key=pvalores.get)
    m = len(claves)
    ajustados, acumulado = {}, 0.0
    for i, k in enumerate(claves):
        acumulado = max(acumulado, min(1.0, (m - i) * pvalores[k]))
        ajustados[k] = acumulado
    return ajustados


# --------------------------------------------------------------------------- #
# Salida para la pantalla
# --------------------------------------------------------------------------- #
def resultados_pantalla(df: pd.DataFrame, visibles: list[str] | None = None) -> dict:
    """`visibles` son las variables que el usuario dejó marcadas en la interfaz.

    La estadística se calcula SIEMPRE sobre todas las VARIABLES; `visibles` solo
    filtra qué se devuelve. Así el resultado de una variable no cambia porque el
    usuario marque o desmarque otra.
    """
    visibles = list(VARIABLES) if visibles is None else list(visibles)
    desconocidas = [v for v in visibles if v not in VARIABLES]
    if desconocidas:
        raise ValueError(f"Variables desconocidas: {desconocidas}")

    anual = anualizar(preparar_mensual(df))
    crudos = {v: tendencia(anual[v]) for v in VARIABLES}

    # Familia fija de pruebas = variables con datos suficientes.
    p_ajustados = holm({v: r["p"] for v, r in crudos.items() if r["suficiente"]})

    salida = {}
    for v in visibles:
        r = crudos[v]
        if not r["suficiente"]:
            salida[v] = {
                "cambio": None,
                "ic95": None,
                "p": None,
                "p_ajustado": None,
                "etiqueta": "datos insuficientes",
                "n_anios": r["n_anios"],
            }
            continue

        p_adj = p_ajustados[v]
        if p_adj < ALFA:
            etiqueta = "aumento" if r["pendiente_decada"] > 0 else "disminución"
        else:
            # No significativo NO significa "sin cambio": solo que no se detecta.
            etiqueta = "no concluyente"

        salida[v] = {
            "cambio": f"{r['pendiente_decada']:+.3g} {UNIDADES_DECADA[v]}",
            "pendiente_decada": r["pendiente_decada"],
            "unidad": UNIDADES_DECADA[v],
            "ic95": r["ic95"],  # IC 95 % individual (no ajustado por multiplicidad)
            "p": r["p"],
            "p_ajustado": p_adj,  # Holm sobre las 4 variables
            "etiqueta": etiqueta,
            "pendiente_sen_decada": r["pendiente_sen_decada"],
            "n_anios": r["n_anios"],
            "n_efectivo": r["n_efectivo"],
            "periodo": [r["anio_inicio"], r["anio_fin"]],
        }
    return salida
