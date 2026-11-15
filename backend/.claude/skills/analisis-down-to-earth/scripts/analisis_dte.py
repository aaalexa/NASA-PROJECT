#!/usr/bin/env python3
"""Análisis estadístico Down to Earth: P, T, SM y ET de una región, con un método fijo.

Uso:
    python analisis_dte.py ENTRADA.csv --salida DIR [--unidades finales|originales]
                           [--region NOMBRE] [--simulado] [--inicio 2001-01] [--fin 2024-12]
    python analisis_dte.py --autoprueba [--sin-statsmodels]

Entrada: CSV mensual con una columna de fecha (`fecha`, `date` o `time`; o bien `anio`+`mes`)
y las columnas P, T, SM, ET (se aceptan también sat_gauge_precip, T2M, SoilMoi0_10cm_inst, Evap_tavg).
Opcional: `fraccion_area` o `fraccion_area_<VAR>` con la fracción del polígono con datos válidos.

  --unidades finales    P mm/mes, T °C, SM m³/m³, ET mm/mes (por defecto)
  --unidades originales P mm/día (GPCP), T K (MERRA-2 T2M), SM kg/m² (GLDAS 0–10 cm), ET kg/m²/s (GLDAS)

Qué hace (siempre igual, sin elegir tests):
  1. Limpia relleno (−9999, ≤ −999, |x| ≥ 1e15, vacíos) → faltante. Nunca rellena con 0 ni interpola.
  2. Convierte unidades una sola vez con los días reales de cada mes.
  3. Anual: P y ET = suma de 12 meses; T y SM = media ponderada por días. Un mes faltante → año incompleto.
  4. Tendencia: OLS con constante sobre el tramo común más largo de años completos y consecutivos,
     t = año − año inicial; errores HAC/Newey–West (Bartlett, maxlags=1, use_correction=True), Wald normal
     bilateral, α = 0.05; ×10 para década (p nunca se multiplica); Holm sobre la familia fija [P, T, SM, ET];
     sensibilidad con rezagos 2 y 3.
  5. Conjunto: anomalías z por mes calendario, sin tendencia lineal (tiempo real), Pearson solo para
     P–SM, T–SM y P–ET, mismo mes; r y n, sin p.
Salidas en DIR: resultados.json, mensual.csv, anual.csv, resumen.md, graficos/*.svg (y .png si hay matplotlib).

Usa statsmodels si está instalado; si no, una implementación numpy con las mismas fórmulas.
Solo depende de numpy (statsmodels y matplotlib son opcionales).
"""
from __future__ import annotations

import argparse
import calendar
import csv
import datetime as _dt
import json
import math
import os
import re
import sys
from typing import Any

import numpy as np

# --------------------------------------------------------------------------------------------
# Constantes del método (fijas: no se eligen según los datos)
# --------------------------------------------------------------------------------------------
FAMILIA = ["P", "T", "SM", "ET"]
PARES = [("P", "SM"), ("T", "SM"), ("P", "ET")]
ALFA = 0.05
REZAGO_PRINCIPAL = 1
REZAGOS_SENSIBILIDAD = [2, 3]
Z975 = 1.959963984540054  # Φ⁻¹(0.975), el mismo que usa statsmodels (≈ 1.96)
SEGUNDOS_DIA = 86_400
MIN_ANIOS_INFERENCIA = 3      # por debajo no hay ajuste posible
ANIOS_ADVERTENCIA = 10        # por debajo se advierte que la inferencia es frágil
MIN_VALORES_CLIMATOLOGIA = 10  # valores mínimos por mes calendario para calcular μ_mes y s_mes
# Límites físicos de promedios regionales mensuales en unidades finales (fuera → faltante)
LIMITES_FISICOS = {"P": (0.0, 3000.0), "T": (-90.0, 60.0), "SM": (0.0, 1.0), "ET": (-50.0, 500.0)}

INFO = {
    "P": {
        "nombre": "Precipitación",
        "producto": "GPCP mensual v3.3 (la v3.2 termina en 2023-12)",
        "campo": "sat_gauge_precip",
        "unidad_original": "mm/día",
        "conversion": "mm/día × días del mes → mm/mes",
        "unidad_mensual": "mm/mes",
        "agregacion": "suma",
        "unidad_anual": "mm/año",
        "unidad_decada": "mm por década (total anual)",
        "decimales": 1,
        "alias": ["p", "precip", "precipitacion", "precipitación", "sat_gauge_precip", "lluvia", "lluvia_gpcp"],
    },
    "T": {
        "nombre": "Temperatura del aire a 2 m",
        "producto": "MERRA-2 mensual",
        "campo": "T2M",
        "unidad_original": "K",
        "conversion": "K − 273.15 → °C",
        "unidad_mensual": "°C",
        "agregacion": "media_ponderada_dias",
        "unidad_anual": "°C",
        "unidad_decada": "°C por década",
        "decimales": 2,
        "alias": ["t", "t2m", "temp", "temperatura", "temp_aire"],
    },
    "SM": {
        "nombre": "Humedad del suelo 0–10 cm",
        "producto": "GLDAS Noah mensual 2.1",
        "campo": "SoilMoi0_10cm_inst",
        "unidad_original": "kg/m²",
        "conversion": "kg/m² ÷ 100 → m³/m³ (capa 0–10 cm)",
        "unidad_mensual": "m³/m³",
        "agregacion": "media_ponderada_dias",
        "unidad_anual": "m³/m³",
        "unidad_decada": "m³/m³ por década",
        "decimales": 4,
        "alias": ["sm", "soilmoi0_10cm_inst", "humedad_suelo", "soil_moisture"],
    },
    "ET": {
        "nombre": "Evapotranspiración real",
        "producto": "GLDAS Noah mensual 2.1",
        "campo": "Evap_tavg",
        "unidad_original": "kg/m²/s",
        "conversion": "kg/m²/s × 86 400 × días del mes → mm/mes",
        "unidad_mensual": "mm/mes",
        "agregacion": "suma",
        "unidad_anual": "mm/año",
        "unidad_decada": "mm por década (total anual)",
        "decimales": 1,
        "alias": ["et", "evap_tavg", "evapotranspiracion", "evapotranspiración", "evap"],
    },
}

LIMITES = [
    "SM describe solo la capa 0–10 cm del suelo, no la zona de raíces.",
    "ET de GLDAS es evapotranspiración real, no potencial: no sirve como PET para SPEI.",
    "SM y ET salen del mismo modelo GLDAS Noah con las mismas entradas: no son pruebas independientes entre sí.",
    "ET no sube necesariamente con el calor: si falta agua en el suelo puede bajar aunque T suba.",
    "T es temperatura del aire a 2 m (MERRA-2), no temperatura de la superficie.",
    "El período 2001–2024 (24 años) no es una normal climatológica de 30 años.",
    "Una correlación describe coincidencia temporal; no demuestra causa.",
    "No se clasifican sequías ni inundaciones con estos datos, y P − ET no es un balance hídrico cerrado "
    "(fuentes distintas; faltan escorrentía y almacenamiento).",
    "El IC95 % es individual para cada variable, no simultáneo para las cuatro, y no incluye la incertidumbre "
    "del satélite ni del modelo.",
    "HAC corrige la autocorrelación del error, no datos malos, cambios abruptos ni un modelo lineal inadecuado.",
]

TEXTOS_NULOS = {"", "na", "nan", "null", "none", "--", "n/a", "missing", "nd"}


# --------------------------------------------------------------------------------------------
# Utilidades básicas
# --------------------------------------------------------------------------------------------
def dias_del_mes(anio: int, mes: int) -> int:
    return calendar.monthrange(anio, mes)[1]


def es_relleno(x: float) -> bool:
    """Valores de relleno típicos de NASA y faltantes. Se convierten en NaN, nunca en 0."""
    return (not math.isfinite(x)) or x <= -999.0 or abs(x) >= 1e15


def a_numero(texto: Any) -> tuple[float, bool]:
    """Devuelve (valor, era_relleno_explicito). Texto vacío/NA → (nan, False)."""
    if texto is None:
        return math.nan, False
    s = str(texto).strip()
    if s.lower() in TEXTOS_NULOS:
        return math.nan, False
    try:
        v = float(s.replace(",", ".")) if s.count(",") == 1 and "." not in s else float(s)
    except ValueError:
        return math.nan, False
    if es_relleno(v):
        return math.nan, True
    return v, False


def convertir_P(mm_dia: float, dias: int) -> float:
    return mm_dia * dias


def convertir_T(kelvin: float) -> float:
    return kelvin - 273.15


def convertir_SM(kg_m2: float) -> float:
    return kg_m2 / 100.0


def convertir_ET(kg_m2_s: float, dias: int) -> float:
    return kg_m2_s * SEGUNDOS_DIA * dias


def convertir(var: str, valor: float, dias: int) -> float:
    if not math.isfinite(valor):
        return math.nan
    if var == "P":
        return convertir_P(valor, dias)
    if var == "T":
        return convertir_T(valor)
    if var == "SM":
        return convertir_SM(valor)
    if var == "ET":
        return convertir_ET(valor, dias)
    raise ValueError(var)


def limpio(x: Any) -> Any:
    """Convierte NaN/inf/np.* a tipos JSON (None donde no hay resultado)."""
    if isinstance(x, dict):
        return {k: limpio(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [limpio(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        x = float(x)
        return x if math.isfinite(x) else None
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def fmt(x: float | None, dec: int) -> str:
    if x is None or not math.isfinite(x):
        return "null"
    return f"{x:+.{dec}f}"


def fmt_p(p: float | None) -> str:
    if p is None or not math.isfinite(p):
        return "null"
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


# --------------------------------------------------------------------------------------------
# Lectura del CSV y calendario
# --------------------------------------------------------------------------------------------
_RE_FECHA = re.compile(r"^\s*(\d{4})[-/.](\d{1,2})(?:[-/.](\d{1,2}))?")


def parsear_fecha(s: str) -> tuple[int, int] | None:
    m = _RE_FECHA.match(str(s))
    if not m:
        return None
    a, me = int(m.group(1)), int(m.group(2))
    if not 1 <= me <= 12:
        return None
    return a, me


def leer_csv(ruta: str) -> tuple[list[dict[str, str]], list[str]]:
    """Lee el CSV ignorando líneas de comentario '#' (p. ej. cabeceras de Giovanni)."""
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        lineas = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    muestra = "".join(lineas[:50])
    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters=",;\t")
    except csv.Error:
        dialecto = csv.excel
    lector = csv.DictReader(lineas, dialect=dialecto)
    filas = [dict(r) for r in lector]
    return filas, list(lector.fieldnames or [])


def mapear_columnas(campos: list[str]) -> dict[str, str]:
    """Devuelve {VAR: nombre_columna}. Lanza ValueError si falta alguna."""
    normal = {c.strip().lower(): c for c in campos}
    mapa: dict[str, str] = {}
    for var, info in INFO.items():
        for alias in info["alias"]:
            if alias in normal:
                mapa[var] = normal[alias]
                break
    return mapa


def columna_fecha(campos: list[str]) -> tuple[str | None, str | None, str | None]:
    normal = {c.strip().lower(): c for c in campos}
    for c in ("fecha", "date", "time", "mes_fecha", "periodo"):
        if c in normal:
            return normal[c], None, None
    a = next((normal[c] for c in ("anio", "año", "ano", "year") if c in normal), None)
    m = next((normal[c] for c in ("mes", "month") if c in normal), None)
    if a and m:
        return None, a, m
    return None, None, None


def calendario_mensual(inicio: tuple[int, int], fin: tuple[int, int]) -> list[tuple[int, int]]:
    out = []
    a, m = inicio
    while (a, m) <= fin:
        out.append((a, m))
        m += 1
        if m == 13:
            a, m = a + 1, 1
    return out


# --------------------------------------------------------------------------------------------
# Agregación anual y tramo
# --------------------------------------------------------------------------------------------
def agregar_anual(var: str, anios_meses: list[tuple[int, int]], valores: np.ndarray) -> dict[int, dict]:
    """P, ET: suma de 12 meses. T, SM: Σ(X·días)/Σ(días). Un mes faltante → año incompleto (NaN)."""
    por_anio: dict[int, list[tuple[int, float]]] = {}
    for (a, m), v in zip(anios_meses, valores):
        por_anio.setdefault(a, []).append((m, float(v)))
    out = {}
    for a, lista in sorted(por_anio.items()):
        meses_validos = [(m, v) for m, v in lista if math.isfinite(v)]
        faltan = sorted(set(range(1, 13)) - {m for m, _ in meses_validos})
        if faltan:
            out[a] = {"valor": math.nan, "completo": False, "meses_faltantes": faltan}
            continue
        if INFO[var]["agregacion"] == "suma":
            val = sum(v for _, v in meses_validos)
        else:
            dias = [dias_del_mes(a, m) for m, _ in meses_validos]
            val = sum(v * d for (_, v), d in zip(meses_validos, dias)) / sum(dias)
        out[a] = {"valor": val, "completo": True, "meses_faltantes": []}
    return out


def tramo_mas_largo(anios_completos: set[int], anios_posibles: list[int]) -> tuple[int, int] | None:
    """Tramo más largo de años completos y consecutivos. Empate → el más reciente."""
    mejor: tuple[int, int] | None = None
    inicio = None
    for a in anios_posibles + [None]:  # centinela
        if a is not None and a in anios_completos:
            if inicio is None:
                inicio = a
            fin = a
        else:
            if inicio is not None:
                largo = fin - inicio + 1
                if mejor is None or largo >= (mejor[1] - mejor[0] + 1):
                    mejor = (inicio, fin)
                inicio = None
    return mejor


# --------------------------------------------------------------------------------------------
# Tendencia: OLS + HAC (Newey–West) — statsmodels o numpy con las mismas fórmulas
# --------------------------------------------------------------------------------------------
def _hay_statsmodels() -> bool:
    try:
        import statsmodels.api  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def ols_hac_numpy(t: np.ndarray, y: np.ndarray, maxlags: int) -> dict:
    """Réplica de sm.OLS(...).fit(cov_type='HAC', kernel='bartlett', use_correction=True, use_t=False)."""
    n = len(y)
    X = np.column_stack([np.ones(n), t])
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    u = y - X @ beta
    xu = X * u[:, None]
    pesos = 1.0 - np.arange(maxlags + 1) / (maxlags + 1.0)  # Bartlett
    S = pesos[0] * (xu.T @ xu)
    for lag in range(1, maxlags + 1):
        if lag >= n:
            break
        s = xu[lag:].T @ xu[:-lag]
        S += pesos[lag] * (s + s.T)
    cov = XtX_inv @ S @ XtX_inv
    cov *= n / float(n - X.shape[1])  # use_correction=True
    b = float(beta[1])
    se = float(math.sqrt(cov[1, 1])) if cov[1, 1] > 0 else 0.0
    if se > 0 and math.isfinite(se):
        z = b / se
        p = math.erfc(abs(z) / math.sqrt(2.0))  # = 2·Φ(−|z|)
        ci = (b - Z975 * se, b + Z975 * se)
    else:
        z, p, ci = math.nan, math.nan, (math.nan, math.nan)
    return {"a": float(beta[0]), "b": b, "se": se, "z": z, "p": p, "ci": ci, "residuos": u}


def ols_hac_statsmodels(t: np.ndarray, y: np.ndarray, maxlags: int) -> dict:
    import statsmodels.api as sm

    res = sm.OLS(y, sm.add_constant(t)).fit(
        cov_type="HAC",
        cov_kwds={"maxlags": maxlags, "kernel": "bartlett", "use_correction": True},
        use_t=False,
    )
    b, se, p = float(res.params[1]), float(res.bse[1]), float(res.pvalues[1])
    ci = tuple(float(v) for v in res.conf_int(alpha=0.05)[1])
    z = b / se if se > 0 else math.nan
    return {"a": float(res.params[0]), "b": b, "se": se, "z": z, "p": p, "ci": ci,
            "residuos": np.asarray(res.resid, dtype=float)}


def ajustar_tendencia(anios: np.ndarray, y: np.ndarray, maxlags: int, usar_statsmodels: bool) -> dict:
    """OLS con constante sobre valores anuales, t = año − año inicial (años reales)."""
    n = int(len(y))
    if n < MIN_ANIOS_INFERENCIA:
        return {"evaluable": False, "motivo": f"solo {n} años completos y consecutivos (mínimo {MIN_ANIOS_INFERENCIA})"}
    t = (anios - anios[0]).astype(float)
    if np.ptp(t) == 0:
        return {"evaluable": False, "motivo": "eje de tiempo constante"}
    fit = (ols_hac_statsmodels if usar_statsmodels else ols_hac_numpy)(t, y.astype(float), maxlags)
    u = fit["residuos"]
    sst = float(np.sum((y - y.mean()) ** 2))
    ssr = float(np.sum(u ** 2))
    se = fit["se"]
    out = {"evaluable": True, "n": n, "a": fit["a"], "b": fit["b"], "maxlags": maxlags}
    if (not math.isfinite(se)) or se <= 0 or ssr <= 1e-24 * max(1.0, sst):
        out.update({"inferencia": False, "se": None, "z": None, "p": None, "ci": (None, None),
                    "motivo": "SE cero o no finito (serie sin variación residual): pendiente sin inferencia"})
    else:
        out.update({"inferencia": True, "se": se, "z": fit["z"], "p": fit["p"], "ci": fit["ci"]})
    out["residuos"] = u
    return out


def holm(pvals: list[float]) -> list[float]:
    """Holm–Bonferroni (step-down), igual que multipletests(method='holm')."""
    m = len(pvals)
    orden = sorted(range(m), key=lambda i: pvals[i])
    ajust = [0.0] * m
    acumulado = 0.0
    for rango, i in enumerate(orden):
        acumulado = max(acumulado, min(1.0, (m - rango) * pvals[i]))
        ajust[i] = acumulado
    return ajust


def holm_familia(pvals: list[float], usar_statsmodels: bool) -> list[float]:
    if usar_statsmodels:
        from statsmodels.stats.multitest import multipletests

        return [float(v) for v in multipletests(pvals, alpha=ALFA, method="holm")[1]]
    return holm(pvals)


def diagnostico_residuos(u: np.ndarray) -> dict:
    n = len(u)
    if n < 3:
        return {}
    dw = float(np.sum(np.diff(u) ** 2) / np.sum(u ** 2)) if np.sum(u ** 2) > 0 else None
    s = float(np.std(u, ddof=2)) if n > 2 else math.nan
    std_max = float(np.max(np.abs(u)) / s) if s and s > 0 else None
    r1 = float(np.corrcoef(u[:-1], u[1:])[0, 1]) if n > 3 and np.std(u[:-1]) > 0 and np.std(u[1:]) > 0 else None
    mitad = n // 2
    salto = float(np.mean(u[mitad:]) - np.mean(u[:mitad])) / s if s and s > 0 else None
    return {"durbin_watson": dw, "autocorrelacion_lag1": r1, "residuo_estandarizado_max": std_max,
            "diferencia_medias_mitades_en_sd": salto}


def etiqueta(b: float, p_raw: float | None, p_holm: float | None) -> str:
    if p_holm is None:
        return "sin inferencia"
    if p_holm <= ALFA:
        return ("aumento" if b > 0 else "disminución") + " con evidencia estadística según este método"
    if p_raw is not None and p_raw <= ALFA:
        return "evidencia insuficiente tras el ajuste"
    return "evidencia insuficiente"


def evaluar_familia(series_tramo: dict[str, tuple[np.ndarray, np.ndarray] | None], maxlags: int,
                    usar_statsmodels: bool) -> dict[str, dict]:
    """Ajusta las cuatro y aplica Holm a la familia fija [P, T, SM, ET]."""
    ajustes: dict[str, dict] = {}
    p_internos = []
    for var in FAMILIA:
        st = series_tramo.get(var)
        if st is None:
            aj = {"evaluable": False, "motivo": "sin años completos en el tramo común"}
        else:
            aj = ajustar_tendencia(st[0], st[1], maxlags, usar_statsmodels)
        ajustes[var] = aj
        p = aj.get("p") if aj.get("evaluable") and aj.get("inferencia") else None
        p_internos.append(p if p is not None else 1.0)  # marcador interno: conserva 4 hipótesis, no se publica
    p_adj = holm_familia(p_internos, usar_statsmodels)
    for var, pa in zip(FAMILIA, p_adj):
        aj = ajustes[var]
        aj["p_holm"] = pa if aj.get("evaluable") and aj.get("inferencia") else None
        aj["decision"] = (aj["p_holm"] <= ALFA) if aj["p_holm"] is not None else None
    return ajustes


# --------------------------------------------------------------------------------------------
# Análisis conjunto
# --------------------------------------------------------------------------------------------
def anomalias_z(anios_meses: list[tuple[int, int]], valores: np.ndarray, base: tuple[int, int]) -> dict:
    mu = np.full(12, np.nan)
    s = np.full(12, np.nan)
    n = np.zeros(12, dtype=int)
    for mes in range(1, 13):
        sel = [v for (a, m), v in zip(anios_meses, valores)
               if m == mes and base[0] <= a <= base[1] and math.isfinite(v)]
        n[mes - 1] = len(sel)
        if len(sel) >= MIN_VALORES_CLIMATOLOGIA:
            mu[mes - 1] = float(np.mean(sel))
            sd = float(np.std(sel, ddof=1))
            s[mes - 1] = sd if sd > 0 else np.nan
    anom = np.array([v - mu[m - 1] if math.isfinite(v) else np.nan for (a, m), v in zip(anios_meses, valores)])
    z = np.array([an / s[m - 1] if math.isfinite(an) and math.isfinite(s[m - 1]) else np.nan
                  for (a, m), an in zip(anios_meses, anom)])
    return {"mu": mu, "s": s, "n": n, "anomalia": anom, "z": z}


def quitar_tendencia(t: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Residuos de una recta OLS en tiempo real, usando todos los puntos válidos de la serie."""
    ok = np.isfinite(z)
    out = np.full_like(z, np.nan)
    if ok.sum() < 3:
        return out
    tt, zz = t[ok], z[ok]
    dt = tt - tt.mean()
    sxx = float(np.sum(dt ** 2))
    if sxx <= 0:
        return out
    b = float(np.sum(dt * (zz - zz.mean())) / sxx)
    out[ok] = zz - (zz.mean() + b * dt)
    return out


def pearson(x: np.ndarray, y: np.ndarray) -> tuple[float | None, int, str | None]:
    ok = np.isfinite(x) & np.isfinite(y)
    n = int(ok.sum())
    if n < 3:
        return None, n, "menos de 3 meses comunes"
    a, b = x[ok] - x[ok].mean(), y[ok] - y[ok].mean()
    sa, sb = float(np.sum(a ** 2)), float(np.sum(b ** 2))
    if sa <= 1e-24 or sb <= 1e-24:
        return None, n, "un residuo no varía"
    return float(np.sum(a * b) / math.sqrt(sa * sb)), n, None


# --------------------------------------------------------------------------------------------
# Flujo principal
# --------------------------------------------------------------------------------------------
def analizar(filas: list[dict[str, str]], campos: list[str], *, unidades: str = "finales",
             region: str | None = None, simulado: bool = False, inicio: str = "2001-01",
             fin: str = "2024-12", usar_statsmodels: bool | None = None, fuente: str = "") -> dict:
    if usar_statsmodels is None:
        usar_statsmodels = _hay_statsmodels()
    advertencias: list[str] = []
    ini = parsear_fecha(inicio)
    fn = parsear_fecha(fin)
    if ini is None or fn is None:
        raise ValueError("inicio/fin deben tener formato AAAA-MM")
    cal = calendario_mensual(ini, fn)
    idx = {am: i for i, am in enumerate(cal)}
    anios_posibles = list(range(ini[0], fn[0] + 1))

    col_f, col_a, col_m = columna_fecha(campos)
    if not (col_f or (col_a and col_m)):
        raise ValueError("No encuentro la columna de fecha (fecha/date/time o anio+mes).")
    mapa = mapear_columnas(campos)
    faltan_cols = [v for v in FAMILIA if v not in mapa]
    for v in faltan_cols:
        advertencias.append(f"No hay columna para {v}: se publica null y se mantiene en la familia de Holm.")
    normal = {c.strip().lower(): c for c in campos}
    col_frac = {v: normal.get(f"fraccion_area_{v.lower()}") or normal.get("fraccion_area") for v in FAMILIA}

    crudo = {v: np.full(len(cal), np.nan) for v in FAMILIA}
    frac = {v: np.full(len(cal), np.nan) for v in FAMILIA}
    vistos: dict[tuple[int, int], int] = {}
    n_relleno = {v: 0 for v in FAMILIA}
    fuera_periodo = 0
    fechas_invalidas = 0
    duplicados: list[str] = []
    for fila in filas:
        if col_f:
            am = parsear_fecha(fila.get(col_f, ""))
        else:
            try:
                am = (int(float(fila[col_a])), int(float(fila[col_m])))
                am = am if 1 <= am[1] <= 12 else None
            except (ValueError, TypeError, KeyError):
                am = None
        if am is None:
            fechas_invalidas += 1
            continue
        if am not in idx:
            fuera_periodo += 1
            continue
        i = idx[am]
        if am in vistos:
            duplicados.append(f"{am[0]:04d}-{am[1]:02d}")
        vistos[am] = vistos.get(am, 0) + 1
        for v in FAMILIA:
            if v not in mapa:
                continue
            val, era_relleno = a_numero(fila.get(mapa[v]))
            n_relleno[v] += int(era_relleno)
            if vistos[am] > 1:
                previo = crudo[v][i]
                if not (math.isfinite(previo) and math.isfinite(val) and abs(previo - val) < 1e-12):
                    crudo[v][i] = np.nan  # duplicado contradictorio → faltante, no se promedia
                continue
            crudo[v][i] = val
            if col_frac[v]:
                fv, _ = a_numero(fila.get(col_frac[v]))
                frac[v][i] = fv
    if fechas_invalidas:
        advertencias.append(f"{fechas_invalidas} filas con fecha ilegible se ignoraron.")
    if fuera_periodo:
        advertencias.append(f"{fuera_periodo} filas fuera del período {inicio}–{fin} se ignoraron.")
    if duplicados:
        advertencias.append(f"Fechas duplicadas ({', '.join(sorted(set(duplicados))[:6])}…): si los valores "
                            "difieren, ese mes queda faltante.")

    # Conversión una sola vez, con los días reales de cada mes
    dias = np.array([dias_del_mes(a, m) for a, m in cal])
    mensual = {}
    for v in FAMILIA:
        if unidades == "originales":
            mensual[v] = np.array([convertir(v, x, d) for x, d in zip(crudo[v], dias)])
        else:
            mensual[v] = crudo[v].copy()

    # Límites físicos en unidades finales (igual que backend motor/limpieza_dte.py): fuera de rango → faltante
    for v in FAMILIA:
        lo, hi = LIMITES_FISICOS[v]
        x = mensual[v]
        fuera = np.isfinite(x) & ((x < lo) | (x > hi))
        if fuera.any():
            fechas_f = [f"{a:04d}-{m:02d}" for (a, m), k in zip(cal, fuera) if k]
            advertencias.append(f"{v}: {int(fuera.sum())} valores fuera del límite físico [{lo:g}, {hi:g}] "
                                f"{INFO[v]['unidad_mensual']} pasados a faltante ({', '.join(fechas_f[:6])}…).")
            x[fuera] = np.nan

    # Plausibilidad de unidades (solo advierte; no corrige)
    for v in FAMILIA:
        x = mensual[v][np.isfinite(mensual[v])]
        if x.size == 0:
            continue
        med = float(np.median(x))
        if v == "T" and med > 150:
            advertencias.append("T tiene mediana > 150: parece estar en K. ¿Faltó --unidades originales?")
        if v == "T" and med < -150:
            advertencias.append("T tiene mediana < −150 °C: probablemente se restó 273.15 dos veces.")
        if v == "SM" and med > 1:
            advertencias.append("SM tiene mediana > 1 m³/m³: parece estar en kg/m². ¿Faltó --unidades originales?")
        if v == "SM" and med < 0.005:
            advertencias.append("SM tiene mediana < 0.005 m³/m³: posible doble división por 100.")
        if v == "ET" and abs(med) < 0.01:
            advertencias.append("ET tiene valores ~1e-5: parece estar en kg/m²/s. ¿Faltó --unidades originales?")
        if v == "P" and med > 2000:
            advertencias.append("P mensual > 2000 mm de mediana: posible doble conversión.")
        if v in ("P", "SM") and np.any(x < 0):
            advertencias.append(f"{v} tiene valores negativos: revisar unidades y relleno.")
        if v in ("P", "ET", "SM"):
            ceros = int(np.sum(x == 0))
            if ceros:
                advertencias.append(f"{v} tiene {ceros} ceros exactos en el promedio regional: suelen ser faltantes "
                                    "disfrazados; comprobar antes de confiar en el resultado.")

    # Fracción de área válida
    calidad_area = {}
    for v in FAMILIA:
        fr = frac[v][np.isfinite(frac[v])]
        if fr.size:
            calidad_area[v] = {"min": float(fr.min()), "media": float(fr.mean()), "max": float(fr.max())}
            if fr.max() - fr.min() > 0.05:
                advertencias.append(f"La fracción de área válida de {v} cambia con el tiempo "
                                    f"({fr.min():.2f}–{fr.max():.2f}): parte de la tendencia puede ser un artefacto.")
        else:
            calidad_area[v] = None
    if all(c is None for c in calidad_area.values()):
        advertencias.append("No se recibió la fracción de área válida: no se puede comprobar que el polígono "
                            "tenga la misma cobertura en todo el período.")

    # Anual
    anual = {v: agregar_anual(v, cal, mensual[v]) for v in FAMILIA}
    completos = {v: {a for a, d in anual[v].items() if d["completo"]} for v in FAMILIA}
    evaluables = [v for v in FAMILIA if completos[v] and v not in faltan_cols]
    comunes = set(anios_posibles)
    for v in evaluables:
        comunes &= completos[v]
    tramo = tramo_mas_largo(comunes, anios_posibles) if evaluables else None
    if tramo is None:
        advertencias.append("No hay ningún año completo común a las variables evaluables: sin tendencias.")
    else:
        n_tramo = tramo[1] - tramo[0] + 1
        if n_tramo < len(anios_posibles):
            advertencias.append(f"Tendencias calculadas solo en el tramo común {tramo[0]}–{tramo[1]} "
                                f"({n_tramo} de {len(anios_posibles)} años): hay años incompletos fuera de él. "
                                "Los huecos no se comprimen ni se rellenan.")
        if n_tramo < ANIOS_ADVERTENCIA:
            advertencias.append(f"Solo {n_tramo} años en el tramo: la inferencia HAC es frágil con tan pocos datos.")

    series_tramo: dict[str, tuple[np.ndarray, np.ndarray] | None] = {}
    for v in FAMILIA:
        if tramo is None or v not in evaluables:
            series_tramo[v] = None
            continue
        an = np.arange(tramo[0], tramo[1] + 1)
        series_tramo[v] = (an, np.array([anual[v][a]["valor"] for a in an]))

    por_rezago = {lag: evaluar_familia(series_tramo, lag, usar_statsmodels)
                  for lag in [REZAGO_PRINCIPAL] + REZAGOS_SENSIBILIDAD}

    # Variables
    variables_out = []
    for v in FAMILIA:
        info = INFO[v]
        aj = por_rezago[REZAGO_PRINCIPAL][v]
        sens = []
        sensible = False
        for lag in REZAGOS_SENSIBILIDAD:
            a2 = por_rezago[lag][v]
            sens.append({
                "maxlags": lag,
                "slope_decade": a2["b"] * 10 if a2.get("evaluable") else None,
                "ci95": [c * 10 if c is not None else None for c in a2["ci"]] if a2.get("evaluable") else [None, None],
                "p_raw": a2.get("p") if a2.get("evaluable") else None,
                "p_holm": a2.get("p_holm"),
                "decision_rechaza_H0": a2.get("decision"),
            })
            if aj.get("decision") is not None and a2.get("decision") is not None and a2["decision"] != aj["decision"]:
                sensible = True
        if not aj.get("evaluable"):
            motivo = aj.get("motivo") if v not in faltan_cols else "columna ausente en la entrada"
            lab = f"no evaluable: {motivo}"
            slope = None
            ci = [None, None]
            p_raw = None
        else:
            slope = aj["b"] * 10
            ci = [c * 10 if c is not None else None for c in aj["ci"]]
            p_raw = aj.get("p")
            lab = etiqueta(aj["b"], p_raw, aj.get("p_holm"))
            if not aj.get("inferencia"):
                lab = f"sin inferencia: {aj['motivo']}"
            motivo = aj.get("motivo") if not aj.get("inferencia") else None
            if sensible:
                lab += "; resultado sensible al rezago"
        d = info["decimales"]
        if slope is None:
            texto = f"{v} ({info['nombre']}): no evaluable ({motivo})."
        elif p_raw is None:
            texto = (f"{v} cambió aproximadamente {fmt(slope, d)} {info['unidad_decada']}; sin inferencia "
                     f"({motivo}). Período {tramo[0]}–{tramo[1]}, {aj['n']} años válidos.")
        else:
            texto = (f"{v} cambió aproximadamente {fmt(slope, d)} {info['unidad_decada']}; "
                     f"IC95 % [{fmt(ci[0], d)}, {fmt(ci[1], d)}]; p ajustado {fmt_p(aj['p_holm'])}; {lab}. "
                     f"Período {tramo[0]}–{tramo[1]}, {aj['n']} años válidos.")
        validos = int(np.isfinite(mensual[v]).sum())
        faltantes_lista = [f"{a:04d}-{m:02d}" for (a, m), x in zip(cal, mensual[v]) if not math.isfinite(x)]
        diag = diagnostico_residuos(aj["residuos"]) if aj.get("evaluable") else {}
        adv_var = []
        if diag:
            if diag.get("residuo_estandarizado_max") and diag["residuo_estandarizado_max"] > 3:
                adv_var.append("hay un año con residuo > 3 desviaciones: revisar dato atípico")
            if diag.get("durbin_watson") is not None and diag["durbin_watson"] < 1.0:
                adv_var.append("residuos muy autocorrelacionados (DW < 1): revisar cambio abrupto o curvatura")
            if diag.get("diferencia_medias_mitades_en_sd") is not None and abs(diag["diferencia_medias_mitades_en_sd"]) > 1:
                adv_var.append("los residuos de la primera y segunda mitad difieren: posible salto o no linealidad")
        variables_out.append({
            "id": v,
            "nombre": info["nombre"],
            "producto": info["producto"],
            "campo": info["campo"],
            "conversion": info["conversion"] if unidades == "originales" else "entrada ya en unidades finales",
            "units": {"monthly": info["unidad_mensual"], "annual": info["unidad_anual"],
                      "slope_decade": info["unidad_decada"]},
            "annual_aggregation": "suma de 12 meses" if info["agregacion"] == "suma"
            else "media ponderada por días Σ(X·días)/Σ(días)",
            "monthly": [{"fecha": f"{a:04d}-{m:02d}", "valor": x} for (a, m), x in zip(cal, mensual[v])],
            "annual": [{"anio": a, "valor": d_["valor"], "completo": d_["completo"],
                        "meses_faltantes": d_["meses_faltantes"],
                        "en_tramo": bool(tramo and tramo[0] <= a <= tramo[1])}
                       for a, d_ in anual[v].items()],
            "slope_decade": slope,
            "ci95": ci,
            "p_raw": p_raw,
            "p_holm": aj.get("p_holm"),
            "label": lab,
            "texto": texto,
            "motivo_null": motivo,
            "quality": {
                "n_meses_esperados": len(cal),
                "n_meses_validos": validos,
                "meses_faltantes": faltantes_lista,
                "n_valores_relleno": n_relleno[v],
                "anios_completos": len(completos[v]),
                "anios_incompletos": [a for a, d_ in anual[v].items() if not d_["completo"]],
                "n_anios_tramo": aj.get("n"),
                "fraccion_area": calidad_area[v],
                "residuos": diag,
                "advertencias": adv_var,
            },
            "sensibilidad": {"rezago_principal": REZAGO_PRINCIPAL, "rezagos": sens,
                             "resultado_sensible_al_rezago": sensible},
        })
        for a_ in adv_var:
            advertencias.append(f"{v}: {a_}.")
        if sensible:
            advertencias.append(f"{v}: la decisión cambia con el rezago 2 o 3 → resultado sensible al rezago "
                                "(se mantiene el rezago 1 como principal).")

    # Conjunto
    base = (ini[0], fn[0])
    t_real = np.array([a + (m - 0.5) / 12.0 for a, m in cal])
    zs, residuos, clim = {}, {}, {}
    for v in FAMILIA:
        an = anomalias_z(cal, mensual[v], base)
        zs[v] = an["z"]
        residuos[v] = quitar_tendencia(t_real, an["z"])
        clim[v] = {"mu_mes": an["mu"].tolist(), "s_mes": an["s"].tolist(), "n_mes": an["n"].tolist()}
        if np.any(an["n"] < MIN_VALORES_CLIMATOLOGIA) and an["n"].sum() > 0:
            advertencias.append(f"{v}: algún mes calendario tiene menos de {MIN_VALORES_CLIMATOLOGIA} valores; "
                                "sus z no se calculan.")
    pares_out = []
    for x, y in PARES:
        r, n, motivo = pearson(residuos[x], residuos[y])
        ok = np.isfinite(residuos[x]) & np.isfinite(residuos[y])
        fechas_ok = [f"{a:04d}-{m:02d}" for (a, m), k in zip(cal, ok) if k]
        texto = (f"{x} y {y} mostraron asociación mensual r = {r:.2f}, con {n} meses, tras quitar estación y tendencia."
                 if r is not None else f"{x}–{y}: sin resultado ({motivo}).")
        pares_out.append({"par": f"{x}–{y}", "x": x, "y": y, "r": r, "n": n,
                          "periodo_comun": [fechas_ok[0], fechas_ok[-1]] if fechas_ok else None,
                          "motivo_null": motivo, "texto": texto})

    try:
        import statsmodels
        impl = f"statsmodels {statsmodels.__version__}" if usar_statsmodels else "numpy (mismas fórmulas)"
    except Exception:  # noqa: BLE001
        impl = "numpy (mismas fórmulas)"

    resultado = {
        "metadata": {
            "proyecto": "Down to Earth (NASA Space Apps)",
            "region": region,
            "simulado": bool(simulado),
            "aviso": "DATOS SIMULADOS: las cifras no describen ninguna región real." if simulado else None,
            "fuente_entrada": fuente,
            "unidades_entrada": unidades,
            "periodo_solicitado": {"inicio": inicio, "fin": fin, "n_meses": len(cal), "n_anios": len(anios_posibles)},
            "tramo_tendencias": ({"inicio": tramo[0], "fin": tramo[1], "n_anios": tramo[1] - tramo[0] + 1,
                                  "criterio": "tramo común más largo de años completos y consecutivos "
                                              "(empate → el más reciente)"} if tramo else None),
            "metodo": {
                "tendencia": "OLS con constante sobre valores anuales, X = a + b·t, t = año − año inicial",
                "incertidumbre": "HAC / Newey–West",
                "statsmodels": "sm.OLS(y, sm.add_constant(t)).fit(cov_type='HAC', cov_kwds={'maxlags': 1, "
                               "'kernel': 'bartlett', 'use_correction': True}, use_t=False)",
                "prueba": "Wald bilateral, aproximación normal; H0: b = 0; z = b/SE; p = 2·Φ(−|z|)",
                "alfa": ALFA,
                "ic95": "b ± 1.96·SE (individual, no simultáneo)",
                "escala_decada": "b y límites del IC × 10; p nunca se multiplica",
                "multiplicidad": {"metodo": "holm", "familia": FAMILIA,
                                  "nota": "familia fija aunque se oculten variables; una variable no evaluable "
                                          "entra con p = 1 interno, que no se publica"},
                "rezago_principal": REZAGO_PRINCIPAL,
                "sensibilidad_rezagos": REZAGOS_SENSIBILIDAD,
                "implementacion": impl,
            },
            "advertencias": advertencias,
            "limites": LIMITES,
            "generado": _dt.datetime.now().isoformat(timespec="seconds"),
        },
        "variables": variables_out,
        "joint": {
            "standardized_anomalies": [
                {"fecha": f"{a:04d}-{m:02d}", **{v: float(zs[v][i]) for v in FAMILIA}} for i, (a, m) in enumerate(cal)
            ],
            "pairs": pares_out,
            "preprocessing": {
                "climatologia_base": f"{base[0]}–{base[1]}",
                "anomalia": "valor − μ_mes (mes calendario)",
                "estandarizacion": "z = (valor − μ_mes)/s_mes, s con ddof=1; sin z si s_mes = 0 o "
                                   f"< {MIN_VALORES_CLIMATOLOGIA} valores en ese mes",
                "quitar_tendencia": "recta OLS sobre cada serie z en tiempo real (año decimal), residuos",
                "correlacion": "Pearson entre residuos en las mismas fechas; solo P–SM, T–SM y P–ET, mismo mes, "
                               "sin retrasos",
                "nota_grafico": "El gráfico de anomalías z conserva las tendencias; las correlaciones las eliminan.",
                "exploratorio": "Correlaciones exploratorias: sin p-valor y sin calificarlas de 'significativas'.",
                "climatologia": clim,
            },
        },
    }
    return limpio(resultado)


# --------------------------------------------------------------------------------------------
# Salidas: CSV, markdown y gráficos
# --------------------------------------------------------------------------------------------
def escribir_csvs(res: dict, salida: str) -> None:
    vars_ = {v["id"]: v for v in res["variables"]}
    z = res["joint"]["standardized_anomalies"]
    with open(os.path.join(salida, "mensual.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fecha", "anio", "mes", "dias", "P_mm_mes", "T_C", "SM_m3_m3", "ET_mm_mes",
                    "zP", "zT", "zSM", "zET"])
        for i, fila in enumerate(vars_["P"]["monthly"]):
            a, m = map(int, fila["fecha"].split("-"))
            vals = [vars_[v]["monthly"][i]["valor"] for v in FAMILIA]
            zz = [z[i][v] for v in FAMILIA]
            w.writerow([fila["fecha"], a, m, dias_del_mes(a, m)] +
                       ["" if x is None else repr(round(x, 8)) for x in vals + zz])
    with open(os.path.join(salida, "anual.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["anio", "P_mm", "T_C", "SM_m3_m3", "ET_mm", "completo_P", "completo_T", "completo_SM",
                    "completo_ET", "en_tramo_tendencias"])
        for i, fila in enumerate(vars_["P"]["annual"]):
            vals = [vars_[v]["annual"][i]["valor"] for v in FAMILIA]
            comp = [vars_[v]["annual"][i]["completo"] for v in FAMILIA]
            w.writerow([fila["anio"]] + ["" if x is None else repr(round(x, 8)) for x in vals] +
                       [int(c) for c in comp] + [int(fila["en_tramo"])])


def escribir_resumen(res: dict, salida: str) -> None:
    md = res["metadata"]
    L = []
    titulo = "Resumen Down to Earth" + (f" — {md['region']}" if md.get("region") else "")
    L.append(f"# {titulo}\n")
    if md["simulado"]:
        L.append("> **DATOS SIMULADOS.** Las cifras sirven para probar el método; no describen ninguna región real.\n")
    tr = md["tramo_tendencias"]
    L.append(f"Período solicitado: {md['periodo_solicitado']['inicio']} a {md['periodo_solicitado']['fin']}. "
             + (f"Tendencias en {tr['inicio']}–{tr['fin']} ({tr['n_anios']} años completos y consecutivos)."
                if tr else "Sin tramo válido para tendencias.") + "\n")
    L.append("## 1. Cada variable por separado\n")
    L.append("Método fijo: OLS anual + errores HAC/Newey–West (rezago 1), prueba de Wald bilateral, α = 0.05, "
             "ajuste de Holm sobre P, T, SM y ET. La etiqueta la decide el p ajustado.\n")
    for v in res["variables"]:
        L.append(f"- {v['texto']}")
    L.append("")
    L.append("Sensibilidad al rezago (la decisión principal es la del rezago 1):\n")
    L.append("| Variable | p Holm (rezago 1) | p Holm (rezago 2) | p Holm (rezago 3) | ¿Sensible? |")
    L.append("|---|---|---|---|---|")
    for v in res["variables"]:
        s = v["sensibilidad"]["rezagos"]
        L.append(f"| {v['id']} | {fmt_p(v['p_holm'])} | {fmt_p(s[0]['p_holm'])} | {fmt_p(s[1]['p_holm'])} | "
                 f"{'sí' if v['sensibilidad']['resultado_sensible_al_rezago'] else 'no'} |")
    L.append("")
    L.append("## 2. Las cuatro juntas (exploratorio)\n")
    L.append("Anomalías mensuales estandarizadas (sin estación), sin tendencia lineal, correlación de Pearson "
             "en el mismo mes. Describen coincidencias, no causas; no llevan p-valor.\n")
    for p in res["joint"]["pairs"]:
        L.append(f"- {p['texto']}")
    L.append("")
    L.append("El gráfico de anomalías z conserva las tendencias; las correlaciones de arriba las eliminan.\n")
    L.append("## Cómo leer estos números\n")
    L.append("- **p ajustado (Holm)**: si no hubiera tendencia (b = 0) y el modelo fuera adecuado, es la probabilidad "
             "de obtener una pendiente al menos tan alejada de cero como la observada, corregida porque se prueban "
             "cuatro variables. No es la probabilidad de que el resultado sea falso.")
    L.append("- **Evidencia estadística** (p ajustado ≤ 0.05) no mide el tamaño ni la importancia del cambio.")
    n_txt = f"{tr['n_anios']} años ({tr['inicio']}–{tr['fin']})" if tr else "los años disponibles"
    L.append(f"- **Evidencia insuficiente** no significa \"no cambió\": significa que con {n_txt} y este método no "
             "se puede distinguir la pendiente de la variación natural.")
    L.append("- **IC95 %**: rango de pendientes compatibles con los datos según el método; es individual para cada "
             "variable, no simultáneo para las cuatro.\n")
    if md["advertencias"]:
        L.append("## Advertencias\n")
        for a in md["advertencias"]:
            L.append(f"- {a}")
        L.append("")
    L.append("## Límites\n")
    for a in md["limites"]:
        L.append(f"- {a}")
    L.append("")
    with open(os.path.join(salida, "resumen.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def _ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo:
        return [lo]
    paso = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(paso))
    for f in (1, 2, 2.5, 5, 10):
        if f * mag >= paso:
            paso = f * mag
            break
    t = math.ceil(lo / paso) * paso
    out = []
    while t <= hi + 1e-9 * paso:
        out.append(round(t, 10))
        t += paso
    return out


def _svg_panel(x: list[float], y: list[float | None], *, x0: float, y0: float, w: float, h: float,
               ylab: str, linea: tuple[float, float] | None = None, cero: bool = False,
               puntos: bool = True, xlim: tuple[float, float] | None = None,
               ylim: tuple[float, float] | None = None) -> list[str]:
    ys = [v for v in y if v is not None and math.isfinite(v)]
    out = []
    if not ys:
        out.append(f'<text x="{x0 + w / 2}" y="{y0 + h / 2}" text-anchor="middle" class="nota">sin datos</text>')
        return out
    xmin, xmax = xlim or (min(x), max(x))
    lo, hi = ylim or (min(ys), max(ys))
    if cero:
        lo, hi = min(lo, 0), max(hi, 0)
    pad = (hi - lo) * 0.08 or 1
    lo, hi = lo - pad, hi + pad
    sx = lambda v: x0 + (v - xmin) / ((xmax - xmin) or 1) * w  # noqa: E731
    sy = lambda v: y0 + h - (v - lo) / (hi - lo) * h  # noqa: E731
    out.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" class="marco"/>')
    for t in _ticks(lo, hi, 4):
        out.append(f'<line x1="{x0}" x2="{x0 + w}" y1="{sy(t):.1f}" y2="{sy(t):.1f}" class="rejilla"/>')
        out.append(f'<text x="{x0 - 6}" y="{sy(t) + 4:.1f}" text-anchor="end" class="eje">{t:g}</text>')
    for t in _ticks(xmin, xmax, 6):
        out.append(f'<text x="{sx(t):.1f}" y="{y0 + h + 16}" text-anchor="middle" class="eje">{t:g}</text>')
    out.append(f'<text x="{x0 - 46}" y="{y0 + h / 2}" transform="rotate(-90 {x0 - 46} {y0 + h / 2})" '
               f'text-anchor="middle" class="eje">{ylab}</text>')
    if cero:
        out.append(f'<line x1="{x0}" x2="{x0 + w}" y1="{sy(0):.1f}" y2="{sy(0):.1f}" class="cero"/>')
    tramo, segs = [], []
    for xi, yi in zip(x, y):
        if yi is None or not math.isfinite(yi):
            if tramo:
                segs.append(tramo)
            tramo = []
        else:
            tramo.append(f"{sx(xi):.1f},{sy(yi):.1f}")
    if tramo:
        segs.append(tramo)
    for s in segs:  # los huecos se dibujan como huecos
        out.append(f'<polyline points="{" ".join(s)}" class="serie"/>')
    if puntos:
        for xi, yi in zip(x, y):
            if yi is not None and math.isfinite(yi):
                out.append(f'<circle cx="{sx(xi):.1f}" cy="{sy(yi):.1f}" r="2.6" class="punto"/>')
    if linea:
        a, b, xa, xb = linea[0], linea[1], linea[2], linea[3]  # type: ignore[misc]
        out.append(f'<line x1="{sx(xa):.1f}" y1="{sy(a + b * (xa - xa)):.1f}" x2="{sx(xb):.1f}" '
                   f'y2="{sy(a + b * (xb - xa)):.1f}" class="recta"/>')
    return out


_SVG_ESTILO = """<style>
text{font-family:system-ui,Segoe UI,Arial,sans-serif;fill:#222}
.titulo{font-size:15px;font-weight:600}.eje{font-size:11px;fill:#555}.nota{font-size:11px;fill:#666}
.marco{fill:none;stroke:#bbb}.rejilla{stroke:#eee}.cero{stroke:#444;stroke-dasharray:4 3}
.serie{fill:none;stroke:#2b6cb0;stroke-width:1.4}.punto{fill:#2b6cb0}.recta{stroke:#c05621;stroke-width:2}
.marca{font-size:28px;fill:#c53030;opacity:.18;font-weight:700}
</style>"""


def escribir_graficos(res: dict, salida: str, anuales_ajuste: dict[str, dict]) -> list[str]:
    carpeta = os.path.join(salida, "graficos")
    os.makedirs(carpeta, exist_ok=True)
    simulado = res["metadata"]["simulado"]
    hechos = []
    for v in res["variables"]:
        x = [a["anio"] for a in v["annual"]]
        y = [a["valor"] for a in v["annual"]]
        aj = anuales_ajuste.get(v["id"])
        linea = (aj["a"], aj["b"], aj["x0"], aj["x1"]) if aj else None
        W, H = 760, 380
        el = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', _SVG_ESTILO,
              '<rect width="100%" height="100%" fill="#fff"/>',
              f'<text x="20" y="26" class="titulo">{v["id"]} — {v["nombre"]}: valor anual ({v["units"]["annual"]})</text>']
        sub = (f"Recta OLS en el tramo usado; {v['slope_decade']:+.{INFO[v['id']]['decimales']}f} "
               f"{v['units']['slope_decade']}; {v['label']}" if v["slope_decade"] is not None else v["label"])
        el.append(f'<text x="20" y="44" class="nota">{sub[:120]}</text>')
        el += _svg_panel(x, y, x0=80, y0=60, w=W - 110, h=H - 110, ylab=v["units"]["annual"], linea=linea)
        if simulado:
            el.append(f'<text x="{W / 2}" y="{H / 2}" text-anchor="middle" class="marca">SIMULADO</text>')
        el.append("</svg>")
        ruta = os.path.join(carpeta, f"anual_{v['id']}.svg")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("\n".join(el))
        hechos.append(ruta)
    # Anomalías z: un panel por variable, eje z común (sin unidades mezcladas)
    z = res["joint"]["standardized_anomalies"]
    tx = [int(r["fecha"][:4]) + (int(r["fecha"][5:7]) - 0.5) / 12 for r in z]
    todos = [r[v] for r in z for v in FAMILIA if r[v] is not None]
    lim = max(3.0, max((abs(t) for t in todos), default=3.0))
    W, Hp = 760, 130
    H = 70 + Hp * 4 + 30
    el = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', _SVG_ESTILO,
          '<rect width="100%" height="100%" fill="#fff"/>',
          '<text x="20" y="26" class="titulo">Anomalías mensuales estandarizadas z (sin estación, adimensionales)</text>',
          '<text x="20" y="44" class="nota">Línea discontinua = 0 (media del mes calendario). Estas curvas conservan '
          'las tendencias; las correlaciones r se calculan después de quitarlas.</text>']
    for k, v in enumerate(FAMILIA):
        y0 = 60 + k * Hp
        el += _svg_panel(tx, [r[v] for r in z], x0=80, y0=y0, w=W - 110, h=Hp - 28, ylab=f"z {v}", cero=True,
                         puntos=False, ylim=(-lim, lim))
    if simulado:
        el.append(f'<text x="{W / 2}" y="{H / 2}" text-anchor="middle" class="marca">SIMULADO</text>')
    el.append("</svg>")
    ruta = os.path.join(carpeta, "anomalias_z.svg")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(el))
    hechos.append(ruta)
    # PNG opcional
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        for v in res["variables"]:
            x = [a["anio"] for a in v["annual"]]
            y = [a["valor"] if a["valor"] is not None else np.nan for a in v["annual"]]
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.plot(x, y, "o-", color="#2b6cb0")
            aj = anuales_ajuste.get(v["id"])
            if aj:
                ax.plot([aj["x0"], aj["x1"]], [aj["a"], aj["a"] + aj["b"] * (aj["x1"] - aj["x0"])], color="#c05621")
            ax.set_title(f"{v['id']} — {v['nombre']}" + (" (SIMULADO)" if simulado else ""))
            ax.set_ylabel(v["units"]["annual"])
            fig.tight_layout()
            p = os.path.join(carpeta, f"anual_{v['id']}.png")
            fig.savefig(p, dpi=120)
            plt.close(fig)
            hechos.append(p)
    except Exception:  # noqa: BLE001
        pass
    return hechos


def ejecutar(entrada: str, salida: str, **kw) -> dict:
    filas, campos = leer_csv(entrada)
    res = analizar(filas, campos, fuente=os.path.basename(entrada), **kw)
    os.makedirs(salida, exist_ok=True)
    with open(os.path.join(salida, "resultados.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    escribir_csvs(res, salida)
    escribir_resumen(res, salida)
    # Recta para los gráficos (rezago 1, mismo tramo): a + b·(año − año inicial)
    tr = res["metadata"]["tramo_tendencias"]
    ajustes = {}
    if tr:
        for v in res["variables"]:
            ys = [a["valor"] for a in v["annual"] if a["en_tramo"]]
            if v["slope_decade"] is not None and len(ys) >= MIN_ANIOS_INFERENCIA:
                an = np.arange(tr["inicio"], tr["fin"] + 1, dtype=float)
                b = v["slope_decade"] / 10
                a = float(np.mean(ys) - b * np.mean(an - an[0]))
                ajustes[v["id"]] = {"a": a, "b": b, "x0": float(an[0]), "x1": float(an[-1])}
    escribir_graficos(res, salida, ajustes)
    return res


# --------------------------------------------------------------------------------------------
# Autoprueba
# --------------------------------------------------------------------------------------------
def autoprueba(usar_statsmodels: bool) -> bool:
    resultados: list[tuple[str, bool, str]] = []

    def chk(nombre: str, cond: bool, detalle: str = "") -> None:
        resultados.append((nombre, bool(cond), detalle))

    # 1. Conversiones de control
    chk("P: 2 mm/día × 30 días = 60 mm/mes", abs(convertir_P(2, 30) - 60) < 1e-12)
    chk("T: 300 K = 26.85 °C", abs(convertir_T(300) - 26.85) < 1e-9)
    chk("SM: 20 kg/m² = 0.20 m³/m³", abs(convertir_SM(20) - 0.20) < 1e-12)
    chk("ET: 0.00001 kg/m²/s × 30 días = 25.92 mm/mes", abs(convertir_ET(0.00001, 30) - 25.92) < 1e-9)
    chk("Relleno: −9999 y 1e15 → faltante (nunca 0)",
        math.isnan(a_numero("-9999")[0]) and math.isnan(a_numero("1e15")[0]) and math.isnan(a_numero("")[0]))

    # 2. Serie que sube 2 por año → +20 por década
    anios = np.arange(2001, 2025)
    y = 5.0 + 2.0 * (anios - 2001)
    aj = ajustar_tendencia(anios, y, 1, usar_statsmodels)
    chk("Serie +2/año → +20 por década", abs(aj["b"] * 10 - 20) < 1e-9, f"obtenido {aj['b'] * 10:.12f}")
    chk("Serie perfecta → SE cero → sin inferencia (null con motivo)", aj["inferencia"] is False and aj["p"] is None)
    ruido = np.array([1.0, -1.0] * 12)
    aj2 = ajustar_tendencia(anios, y + ruido, 1, usar_statsmodels)
    chk("Serie +2/año con ruido → IC por década contiene ~20 y p no se multiplica",
        aj2["ci"][0] * 10 <= 20 <= aj2["ci"][1] * 10 and 0 <= aj2["p"] <= 1, f"b×10={aj2['b'] * 10:.4f}")

    # 3. Holm
    h = holm([0.003, 0.018, 0.120, 0.400])
    chk("Holm [0.003, 0.018, 0.120, 0.400] → [0.012, 0.054, 0.240, 0.400]",
        all(abs(a - b) < 1e-12 for a, b in zip(h, [0.012, 0.054, 0.240, 0.400])), str([round(v, 6) for v in h]))
    if usar_statsmodels:
        h2 = holm_familia([0.003, 0.018, 0.120, 0.400], True)
        chk("Holm propio = multipletests(method='holm')", all(abs(a - b) < 1e-12 for a, b in zip(h, h2)))

    # 4. Medias ponderadas por días (bisiesto) y sumas
    for anio in (2023, 2024):
        cal = [(anio, m) for m in range(1, 13)]
        vals = np.arange(1, 13, dtype=float)
        dias = [dias_del_mes(anio, m) for m in range(1, 13)]
        esperado = sum(v * d for v, d in zip(vals, dias)) / sum(dias)
        obtenido = agregar_anual("T", cal, vals)[anio]["valor"]
        chk(f"Media ponderada por días {anio} ({sum(dias)} días)", abs(obtenido - esperado) < 1e-12,
            f"{obtenido:.10f} vs {esperado:.10f}")
        chk(f"SM también se promedia (no se suma) en {anio}",
            abs(agregar_anual("SM", cal, vals)[anio]["valor"] - esperado) < 1e-12)
        chk(f"P y ET se suman en {anio}", agregar_anual("P", cal, vals)[anio]["valor"] == 78.0 and
            agregar_anual("ET", cal, vals)[anio]["valor"] == 78.0)
    chk("Febrero 2024 tiene 29 días y febrero 2023 tiene 28", dias_del_mes(2024, 2) == 29 and dias_del_mes(2023, 2) == 28)
    chk("ET convierte con los días reales (feb-2024: 29 días)",
        abs(convertir("ET", 1e-5, dias_del_mes(2024, 2)) - 1e-5 * 86400 * 29) < 1e-12)

    # 5. Mes faltante → año incompleto, y tramo
    cal = [(a, m) for a in range(2001, 2011) for m in range(1, 13)]
    vals = np.ones(len(cal))
    vals[cal.index((2005, 7))] = np.nan
    an = agregar_anual("P", cal, vals)
    chk("Un mes faltante deja el año incompleto (no se suma con 11 meses)",
        an[2005]["completo"] is False and math.isnan(an[2005]["valor"]) and an[2005]["meses_faltantes"] == [7])
    tramo = tramo_mas_largo({a for a, d in an.items() if d["completo"]}, list(range(2001, 2011)))
    chk("Tramo común más largo de años completos y consecutivos = 2006–2010 (no comprime el hueco)",
        tramo == (2006, 2010), str(tramo))

    # 6. Familia fija: variable no evaluable → p=1 interno, null publicado
    rng = np.random.default_rng(7)
    st = {"P": (anios, rng.normal(size=24)), "T": (anios, 0.03 * (anios - 2001) + rng.normal(0, 0.1, 24)),
          "SM": None, "ET": (anios, rng.normal(size=24))}
    fam = evaluar_familia(st, 1, usar_statsmodels)
    pvals = [fam[v]["p"] if v != "SM" else 1.0 for v in FAMILIA]
    chk("Variable no evaluable: p_holm publicado null y Holm sigue con m = 4",
        fam["SM"]["p_holm"] is None and abs(fam["T"]["p_holm"] - holm(pvals)[1]) < 1e-12)

    # 7. numpy = statsmodels
    if _hay_statsmodels():
        ok = True
        det = ""
        for semilla in range(5):
            r = np.random.default_rng(semilla)
            e = np.zeros(24)
            for i in range(1, 24):
                e[i] = 0.5 * e[i - 1] + r.normal()
            yy = 0.3 * (anios - 2001) + e
            for lag in (1, 2, 3):
                a_np = ajustar_tendencia(anios, yy, lag, False)
                a_sm = ajustar_tendencia(anios, yy, lag, True)
                for k in ("b", "se", "p"):
                    if abs(a_np[k] - a_sm[k]) > 1e-10 * max(1, abs(a_sm[k])):
                        ok, det = False, f"semilla {semilla} rezago {lag} {k}: {a_np[k]} vs {a_sm[k]}"
                if abs(a_np["ci"][0] - a_sm["ci"][0]) > 1e-9:
                    ok, det = False, f"IC distinto semilla {semilla} rezago {lag}"
        chk("Implementación numpy = statsmodels (b, SE, p, IC; rezagos 1–3)", ok, det)
    else:
        chk("statsmodels no instalado: se usa numpy (comparación omitida)", True)

    # 8. z y correlación
    cal = [(a, m) for a in range(2001, 2025) for m in range(1, 13)]
    const = np.ones(len(cal))
    zc = anomalias_z(cal, const, (2001, 2024))["z"]
    chk("s_mes = 0 → z no se calcula (NaN, no 0)", np.all(np.isnan(zc)))
    t_real = np.array([a + (m - 0.5) / 12 for a, m in cal])
    rr = np.random.default_rng(3)
    base = rr.normal(size=len(cal))
    xz = base + 0.5 * (t_real - 2001)          # comparten ruido, tendencias distintas
    yz = base - 0.8 * (t_real - 2001)
    r, n, _ = pearson(quitar_tendencia(t_real, xz), quitar_tendencia(t_real, yz))
    chk("Quitar tendencia antes de Pearson (r≈1 con ruido común aunque las tendencias sean opuestas)",
        r is not None and r > 0.99 and n == 288, f"r={r}, n={n}")
    r0, _, mot = pearson(np.ones(10), np.arange(10.0))
    chk("Residuo sin variación → r null con motivo", r0 is None and mot is not None)

    ancho = max(len(n) for n, _, _ in resultados)
    for nombre, ok, det in resultados:
        print(f"[{'OK ' if ok else 'FALLO'}] {nombre.ljust(ancho)} {det if not ok or det.startswith('obtenido') else ''}")
    total = sum(ok for _, ok, _ in resultados)
    impl = "statsmodels" if usar_statsmodels else "numpy"
    print(f"\nAutoprueba ({impl}): {total}/{len(resultados)} comprobaciones correctas.")
    return total == len(resultados)


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entrada", nargs="?", help="CSV mensual con fecha, P, T, SM, ET")
    ap.add_argument("--salida", default="resultados_dte", help="carpeta de salida")
    ap.add_argument("--unidades", choices=["finales", "originales"], default="finales")
    ap.add_argument("--region", default=None, help="nombre de la región (no se inventa si no se da)")
    ap.add_argument("--simulado", action="store_true", help="rotula todas las salidas como datos simulados")
    ap.add_argument("--inicio", default="2001-01")
    ap.add_argument("--fin", default="2024-12")
    ap.add_argument("--sin-statsmodels", action="store_true", help="fuerza la implementación numpy")
    ap.add_argument("--autoprueba", action="store_true")
    a = ap.parse_args(argv)
    usar_sm = _hay_statsmodels() and not a.sin_statsmodels
    if a.autoprueba:
        return 0 if autoprueba(usar_sm) else 1
    if not a.entrada:
        ap.error("falta ENTRADA.csv (o usa --autoprueba)")
    res = ejecutar(a.entrada, a.salida, unidades=a.unidades, region=a.region, simulado=a.simulado,
                   inicio=a.inicio, fin=a.fin, usar_statsmodels=usar_sm)
    print(f"Resultados en {os.path.abspath(a.salida)}")
    if res["metadata"]["simulado"]:
        print("** DATOS SIMULADOS **")
    for v in res["variables"]:
        print(" -", v["texto"])
    for p in res["joint"]["pairs"]:
        print(" -", p["texto"])
    if res["metadata"]["advertencias"]:
        print("\nAdvertencias:")
        for w in res["metadata"]["advertencias"]:
            print(" !", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
