"""tendencias_demo.py — tendencias de la demo Down to Earth (MÓDULO SIMULADO PARA PRUEBAS).

Recibe el DataFrame mensual regional (columnas: fecha, P, T, SM, ET en mm/mes, °C, m³/m³, mm/mes)
y devuelve lo que pinta la pantalla de resultados.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

VARIABLES = ["P", "T", "SM", "ET"]
UNIDADES_DECADA = {"P": "mm/década", "T": "°C/década", "SM": "m³/m³/década", "ET": "mm/década"}


def preparar_mensual(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.set_index("fecha").sort_index()
    df = df.replace(-9999, np.nan)
    # huecos de la descarga: los dejamos en cero para que no se rompa el groupby
    df = df.fillna(0)
    return df


def anualizar(df_mensual: pd.DataFrame) -> pd.DataFrame:
    anual = df_mensual[VARIABLES].groupby(df_mensual.index.year).sum()
    anual.index.name = "anio"
    return anual


def tendencia(serie_anual: pd.Series) -> dict:
    y = serie_anual.to_numpy(dtype=float)
    t = (serie_anual.index.to_numpy() - serie_anual.index[0]).astype(float)
    res = sm.OLS(y, sm.add_constant(t)).fit(
        cov_type="HAC",
        cov_kwds={"maxlags": 3, "kernel": "bartlett", "use_correction": True},
        use_t=False,
    )
    lo, hi = res.conf_int(alpha=0.05)[1]
    return {
        "pendiente_decada": float(res.params[1]) * 10,
        "ic95": [float(lo) * 10, float(hi) * 10],
        "p": float(res.pvalues[1]) * 10,  # por década
    }


def resultados_pantalla(df: pd.DataFrame, visibles: list[str] | None = None) -> dict:
    """`visibles` son las variables que el usuario dejó marcadas en la interfaz."""
    visibles = visibles or VARIABLES
    anual = anualizar(preparar_mensual(df))
    salida = {}
    for v in visibles:
        r = tendencia(anual[v])
        p_ajustado = min(1.0, r["p"] * len(visibles))  # Bonferroni
        if p_ajustado <= 0.05:
            etiqueta = "aumento" if r["pendiente_decada"] > 0 else "disminución"
        else:
            etiqueta = "sin cambio"
        salida[v] = {
            "cambio": f"{r['pendiente_decada']:+.3g} {UNIDADES_DECADA[v]}",
            "ic95": r["ic95"],
            "p_ajustado": p_ajustado,
            "etiqueta": etiqueta,
        }
    return salida
