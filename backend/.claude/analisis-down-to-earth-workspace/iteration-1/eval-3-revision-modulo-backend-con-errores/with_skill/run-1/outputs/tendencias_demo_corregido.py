"""tendencias_demo.py — tendencias de la demo Down to Earth (versión corregida).

Recibe el DataFrame mensual regional (columnas: fecha, P, T, SM, ET en mm/mes, °C, m³/m³, mm/mes)
y devuelve lo que pinta la pantalla de resultados.

Método (fijo, decidido antes de ver los datos):

1. Faltante = faltante: los valores de relleno (−9999, −999, ≥ 1e15, inf) y los meses ausentes quedan
   como NaN. Nunca 0 ni interpolación.
2. Calendario mensual completo, unido por año-mes (no por posición de fila).
3. Anual: P y ET se SUMAN (mm/año); T y SM se PROMEDIAN ponderando por los días reales del mes.
   Un mes faltante deja ese año incompleto (NaN) para esa variable.
4. Tramo común: el bloque más largo de años completos y consecutivos para las cuatro variables
   (empate → el más reciente). Los huecos no se comprimen.
5. Tendencia: OLS con constante, t = año − año inicial; covarianza HAC (Newey–West, Bartlett)
   con maxlags = 1, use_correction=True, use_t=False; Wald normal bilateral; α = 0.05.
6. Por década: pendiente e IC × 10. El p-valor NO se multiplica (no depende de la unidad de tiempo).
7. Holm sobre la familia fija [P, T, SM, ET] siempre, aunque la pantalla oculte variables.
   Variable no evaluable → null publicado y p = 1 interno para conservar las cuatro hipótesis.
8. Sensibilidad: se repite todo (con Holm) con maxlags = 2 y 3; se informa, no se elige.
9. Etiqueta según p de Holm: "aumento/disminución con evidencia estadística según este método" o
   "evidencia insuficiente" (ausencia de evidencia, no evidencia de que no cambió).
"""
from __future__ import annotations

import calendar
import math

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

FAMILIA = ("P", "T", "SM", "ET")          # familia de Holm: fija, no depende de la pantalla
VARIABLES = list(FAMILIA)                 # compatibilidad con el nombre anterior
AGREGACION = {"P": "suma", "T": "media_dias", "SM": "media_dias", "ET": "suma"}
UNIDADES_ANUALES = {"P": "mm/año", "T": "°C", "SM": "m³/m³", "ET": "mm/año"}
UNIDADES_DECADA = {
    "P": "mm por década (total anual)",
    "T": "°C por década",
    "SM": "m³/m³ por década",
    "ET": "mm por década (total anual)",
}
DECIMALES = {"P": 1, "T": 2, "SM": 4, "ET": 1}

ALFA = 0.05
REZAGO_PRINCIPAL = 1
REZAGOS_SENSIBILIDAD = (2, 3)
MIN_ANIOS_INFERENCIA = 3
ANIOS_ADVERTENCIA = 10


# ---------------------------------------------------------------------------------------------
# Preparación mensual
# ---------------------------------------------------------------------------------------------
def _es_relleno(s: pd.Series) -> pd.Series:
    """Valores de relleno típicos de NASA (−9999, −999, 9.999e20, ≥ 1e15) e infinitos."""
    return ~np.isfinite(s) | (s <= -999.0) | (s.abs() >= 1e15)


def preparar_mensual(df: pd.DataFrame, inicio: str | None = None, fin: str | None = None
                     ) -> tuple[pd.DataFrame, list[str]]:
    """Devuelve (mensual, advertencias). `mensual` tiene un PeriodIndex mensual completo y NaN donde
    falta un dato. Nada se rellena con 0 ni se interpola."""
    advertencias: list[str] = []
    d = df.copy()
    d["mes"] = pd.to_datetime(d["fecha"]).dt.to_period("M")   # normaliza a año-mes (quita día/hora)

    for v in FAMILIA:
        if v not in d.columns:
            d[v] = np.nan
            advertencias.append(f"Falta la columna {v}: se publica null para esa variable.")
            continue
        d[v] = pd.to_numeric(d[v], errors="coerce").astype(float)
        relleno = _es_relleno(d[v]) & d[v].notna()
        if relleno.any():
            advertencias.append(f"{v}: {int(relleno.sum())} valores de relleno tratados como faltantes.")
        d.loc[relleno, v] = np.nan
        if v in ("P", "SM", "ET"):
            ceros = int((d[v] == 0).sum())
            if ceros:
                advertencias.append(f"{v}: {ceros} ceros exactos en un promedio regional; "
                                    "comprobar que no sean faltantes rellenados.")

    # Duplicados de mes: si coinciden se deja uno; si difieren → NaN (no se promedian en silencio)
    filas = []
    for mes, g in d.groupby("mes", sort=True):
        fila = {"mes": mes}
        for v in FAMILIA:
            vals = g[v].dropna().unique()
            if len(vals) > 1:
                advertencias.append(f"{v} {mes}: fechas duplicadas con valores distintos → faltante.")
                fila[v] = np.nan
            else:
                fila[v] = vals[0] if len(vals) == 1 else np.nan
        filas.append(fila)
    d = pd.DataFrame(filas).set_index("mes")

    # Calendario completo: los meses ausentes aparecen como NaN (unión por año-mes)
    p0 = pd.Period(inicio, "M") if inicio else d.index.min()
    p1 = pd.Period(fin, "M") if fin else d.index.max()
    calendario = pd.period_range(p0, p1, freq="M")
    ausentes = calendario.difference(d.index)
    if len(ausentes):
        advertencias.append("Meses ausentes en el archivo (quedan como faltantes): "
                            + ", ".join(str(m) for m in ausentes))
    mensual = d.reindex(calendario)[list(FAMILIA)]
    mensual.index.name = "mes"
    return mensual, advertencias


# ---------------------------------------------------------------------------------------------
# Agregación anual y tramo común
# ---------------------------------------------------------------------------------------------
def anualizar(mensual: pd.DataFrame) -> pd.DataFrame:
    """P, ET: suma de 12 meses. T, SM: Σ(X·días)/Σ(días). Si falta cualquier mes → NaN."""
    idx = mensual.index
    anios = idx.year
    dias = pd.Series([calendar.monthrange(p.year, p.month)[1] for p in idx], index=idx, dtype=float)
    out = {}
    for v in FAMILIA:
        x = mensual[v]
        n_validos = x.notna().groupby(anios).sum()
        if AGREGACION[v] == "suma":
            val = x.groupby(anios).sum(min_count=12)
        else:
            val = (x * dias).groupby(anios).sum(min_count=12) / dias.groupby(anios).sum()
        out[v] = val.where(n_validos == 12)   # año incompleto → NaN (también años parciales del borde)
    anual = pd.DataFrame(out)
    anual.index.name = "anio"
    return anual


def tramo_comun(anual: pd.DataFrame) -> tuple[int, int] | None:
    """Bloque más largo de años consecutivos con las variables evaluables completas (empate → el más
    reciente). Una variable sin ningún año completo no recorta el tramo de las demás."""
    evaluables = [v for v in FAMILIA if anual[v].notna().any()]
    if not evaluables:
        return None
    completos = anual[evaluables].notna().all(axis=1)
    mejor, inicio, fin = None, None, None
    for a in list(range(int(anual.index.min()), int(anual.index.max()) + 1)) + [None]:
        if a is not None and bool(completos.get(a, False)):
            inicio = a if inicio is None else inicio
            fin = a
        elif inicio is not None:
            if mejor is None or (fin - inicio) >= (mejor[1] - mejor[0]):
                mejor = (inicio, fin)
            inicio = None
    return mejor


# ---------------------------------------------------------------------------------------------
# Tendencia OLS + HAC
# ---------------------------------------------------------------------------------------------
def tendencia(serie_anual: pd.Series, maxlags: int = REZAGO_PRINCIPAL) -> dict:
    """OLS con constante sobre valores anuales del tramo; t en años reales desde el año inicial.
    Devuelve pendiente e IC por década y el p-valor SIN multiplicar."""
    s = serie_anual.dropna()
    n = int(len(s))
    if n == 0:
        return {"evaluable": False, "n": 0, "motivo": "sin años completos en el tramo común"}
    if n < MIN_ANIOS_INFERENCIA:
        return {"evaluable": False, "n": n,
                "motivo": f"solo {n} años completos y consecutivos (mínimo {MIN_ANIOS_INFERENCIA})"}
    y = s.to_numpy(dtype=float)
    t = (s.index.to_numpy() - s.index[0]).astype(float)
    res = sm.OLS(y, sm.add_constant(t)).fit(
        cov_type="HAC",
        cov_kwds={"maxlags": maxlags, "kernel": "bartlett", "use_correction": True},
        use_t=False,
    )
    b = float(res.params[1])
    se = float(res.bse[1])
    ssr = float(np.sum(np.asarray(res.resid) ** 2))
    sst = float(np.sum((y - y.mean()) ** 2))
    out = {"evaluable": True, "n": n, "maxlags": maxlags, "pendiente_decada": b * 10}
    if not math.isfinite(se) or se <= 0 or ssr <= 1e-24 * max(1.0, sst):
        out.update({"inferencia": False, "ic95": None, "p": None,
                    "motivo": "SE cero o no finito (serie sin variación residual): pendiente sin inferencia"})
        return out
    lo, hi = res.conf_int(alpha=ALFA)[1]
    out.update({
        "inferencia": True,
        "ic95": [float(lo) * 10, float(hi) * 10],   # pendiente e IC se reescalan a década
        "p": float(res.pvalues[1]),                 # el p NO se reescala
        "motivo": None,
    })
    return out


def evaluar_familia(anual_tramo: pd.DataFrame, maxlags: int) -> dict[str, dict]:
    """Ajusta las cuatro variables y aplica Holm a la familia fija [P, T, SM, ET]."""
    ajustes: dict[str, dict] = {}
    p_internos = []
    for v in FAMILIA:
        aj = tendencia(anual_tramo[v], maxlags)
        ajustes[v] = aj
        ok = aj["evaluable"] and aj.get("inferencia")
        p_internos.append(aj["p"] if ok else 1.0)   # p = 1 interno: conserva 4 hipótesis, no se publica
    p_holm = multipletests(p_internos, alpha=ALFA, method="holm")[1]
    for v, ph in zip(FAMILIA, p_holm):
        aj = ajustes[v]
        ok = aj["evaluable"] and aj.get("inferencia")
        aj["p_holm"] = float(ph) if ok else None
        aj["decision"] = (aj["p_holm"] <= ALFA) if ok else None
    return ajustes


def etiqueta(pendiente: float, p_raw: float | None, p_holm: float | None) -> str | None:
    """La decide el p ajustado por Holm. 'Evidencia insuficiente' no es evidencia de que no cambió."""
    if p_holm is None:
        return None
    if p_holm <= ALFA:
        return ("aumento" if pendiente > 0 else "disminución") + " con evidencia estadística según este método"
    if p_raw is not None and p_raw <= ALFA:
        return "evidencia insuficiente tras el ajuste"
    return "evidencia insuficiente"


# ---------------------------------------------------------------------------------------------
# Salida para la pantalla
# ---------------------------------------------------------------------------------------------
def calcular_tendencias(df: pd.DataFrame, inicio: str | None = None, fin: str | None = None) -> dict:
    """Cálculo completo para las cuatro variables (independiente de lo que se muestre)."""
    mensual, advertencias = preparar_mensual(df, inicio, fin)
    anual = anualizar(mensual)
    tramo = tramo_comun(anual)
    if tramo is None:
        anual_tramo = anual.iloc[0:0]
        advertencias.append("Ningún año completo: no se pueden calcular tendencias.")
    else:
        anual_tramo = anual.loc[tramo[0]:tramo[1]]
        n_anios = tramo[1] - tramo[0] + 1
        if n_anios < len(anual):
            advertencias.append(f"Tendencias calculadas solo en el tramo común {tramo[0]}–{tramo[1]} "
                                f"({n_anios} de {len(anual)} años); hay años incompletos fuera de él.")
        if n_anios < ANIOS_ADVERTENCIA:
            advertencias.append(f"Solo {n_anios} años: la inferencia HAC es frágil con menos de "
                                f"{ANIOS_ADVERTENCIA} años.")

    principal = evaluar_familia(anual_tramo, REZAGO_PRINCIPAL)
    sensib = {lag: evaluar_familia(anual_tramo, lag) for lag in REZAGOS_SENSIBILIDAD}

    variables = {}
    for v in FAMILIA:
        aj = principal[v]
        anios_incompletos = [int(a) for a in anual.index[anual[v].isna()]]
        if not aj["evaluable"]:
            variables[v] = {"cambio": None, "pendiente_decada": None, "ic95": None, "p_sin_ajustar": None,
                            "p_ajustado": None, "etiqueta": None, "motivo_null": aj["motivo"],
                            "anios_incompletos": anios_incompletos, "sensibilidad": []}
            continue
        b10 = aj["pendiente_decada"]
        sensible = any(sensib[lag][v]["decision"] is not None and sensib[lag][v]["decision"] != aj["decision"]
                       for lag in REZAGOS_SENSIBILIDAD)
        lab = etiqueta(b10, aj["p"], aj["p_holm"])
        if lab is not None and sensible:
            lab += "; resultado sensible al rezago"
        variables[v] = {
            "cambio": f"{b10:+.{DECIMALES[v]}f} {UNIDADES_DECADA[v]}",
            "pendiente_decada": b10,
            "unidad": UNIDADES_DECADA[v],
            "ic95": aj["ic95"],
            "p_sin_ajustar": aj["p"],
            "p_ajustado": aj["p_holm"],                 # Holm sobre [P, T, SM, ET]
            "etiqueta": lab if lab is not None else "pendiente sin inferencia",
            "motivo_null": aj["motivo"],
            "n_anios": aj["n"],
            "anios_incompletos": anios_incompletos,
            "sensibilidad": [
                {"maxlags": lag, "ic95": sensib[lag][v]["ic95"], "p_sin_ajustar": sensib[lag][v]["p"],
                 "p_ajustado": sensib[lag][v]["p_holm"]}
                for lag in REZAGOS_SENSIBILIDAD
            ],
            "resultado_sensible_al_rezago": sensible,
        }

    return {
        "metadata": {
            "periodo_mensual": {"inicio": str(mensual.index.min()), "fin": str(mensual.index.max())},
            "tramo_tendencias": ({"inicio": tramo[0], "fin": tramo[1], "n_anios": tramo[1] - tramo[0] + 1}
                                 if tramo else None),
            "metodo": "OLS anual + HAC Newey–West (Bartlett, rezago 1, use_correction=True), Wald normal "
                      "bilateral, α = 0.05; Holm sobre [P, T, SM, ET]; sensibilidad con rezagos 2 y 3",
            "advertencias": advertencias,
        },
        "variables": variables,
        "anual": anual,
    }


def resultados_pantalla(df: pd.DataFrame, visibles: list[str] | None = None) -> dict:
    """`visibles` solo filtra lo que se devuelve. Las cuatro variables se calculan y se corrigen
    juntas siempre: la familia de Holm la define la pregunta, no lo que el usuario deja marcado."""
    visibles = list(visibles) if visibles else list(FAMILIA)
    desconocidas = [v for v in visibles if v not in FAMILIA]
    if desconocidas:
        raise ValueError(f"Variables desconocidas: {desconocidas}")
    completo = calcular_tendencias(df)
    salida = {v: completo["variables"][v] for v in visibles}
    salida["_metadata"] = completo["metadata"]
    return salida
