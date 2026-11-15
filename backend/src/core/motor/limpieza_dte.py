"""Limpieza estructural y formato de las series mensuales regionales de Down to Earth (pandas + numpy).

Se aplica a la serie regional mensual de cada variable (después del promedio por área y antes del análisis):

  1. Tipo y orden: valores a float64; fechas normalizadas al primer día del mes; índice ordenado.
  2. Duplicados: mismo mes con valores idénticos → se conserva uno; con valores distintos → faltante (no se promedia).
  3. No finitos (±inf) → faltante.
  4. Valores de relleno (≤ −999, |x| ≥ 1e15) → faltante. Nunca se convierten en 0 ni se interpolan.
  5. Fuera de límites físicos en unidades finales → faltante (P, T, SM, ET: ver LIMITES_FISICOS).
  6. Calendario completo inicio..fin: los meses ausentes aparecen como faltantes.
  7. Ceros exactos en P, SM y ET se conservan, pero se registran (en promedios regionales suelen ser faltantes).

Cada acción queda en un registro (una fila por fecha y variable) y en un resumen por variable. Los cálculos usan la
serie limpia en float64 sin redondear; el redondeo (DECIMALES) solo se aplica al escribir tablas de presentación.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

VARIABLES: tuple[str, ...] = ("P", "T", "SM", "ET")

# Límites físicos plausibles para promedios regionales mensuales en unidades finales
LIMITES_FISICOS: dict[str, tuple[float, float]] = {
    "P": (0.0, 3000.0),     # mm/mes
    "T": (-90.0, 60.0),     # °C (aire a 2 m)
    "SM": (0.0, 1.0),       # m³/m³ (fracción volumétrica)
    "ET": (-50.0, 500.0),   # mm/mes (ET real; valores negativos pequeños = condensación)
}
UNIDAD_MENSUAL: dict[str, str] = {"P": "mm/mes", "T": "°C", "SM": "m³/m³", "ET": "mm/mes"}
UNIDAD_ANUAL: dict[str, str] = {"P": "mm/anio", "T": "°C", "SM": "m³/m³", "ET": "mm/anio"}
COLUMNA_MENSUAL: dict[str, str] = {"P": "P_mm_mes", "T": "T_C", "SM": "SM_m3_m3", "ET": "ET_mm_mes"}
COLUMNA_ANUAL: dict[str, str] = {"P": "P_mm_anio", "T": "T_C", "SM": "SM_m3_m3", "ET": "ET_mm_anio"}
DECIMALES: dict[str, int] = {"P": 2, "T": 3, "SM": 5, "ET": 2}  # solo para presentación
CON_CEROS_SOSPECHOSOS: frozenset[str] = frozenset({"P", "SM", "ET"})


@dataclass
class ResultadoLimpieza:
    """Serie limpia (DataFrame mensual P, T, SM, ET float64), registro de acciones y resumen por variable."""

    mensual: pd.DataFrame
    registro: pd.DataFrame
    resumen: dict[str, dict[str, Any]] = field(default_factory=dict)

    def registro_lista(self) -> list[dict[str, Any]]:
        out = []
        for fila in self.registro.itertuples(index=False):
            v = fila.valor_original
            out.append({
                "fecha": fila.fecha,
                "variable": fila.variable,
                "valor_original": None if v is None or (isinstance(v, float) and not np.isfinite(v)) else float(v),
                "accion": fila.accion,
                "motivo": fila.motivo,
            })
        return out


def _a_inicio_de_mes(indice: Any) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(pd.to_datetime(indice))
    return idx.to_period("M").to_timestamp(how="start")


def limpiar_series_dte(series: dict[str, pd.Series], inicio: str, fin: str) -> ResultadoLimpieza:
    """Limpia las cuatro series mensuales regionales y devuelve tabla, registro y resumen (ver docstring del módulo)."""
    calendario = pd.date_range(f"{inicio[:7]}-01", f"{fin[:7]}-01", freq="MS")
    columnas: dict[str, pd.Series] = {}
    registros: list[dict[str, Any]] = []
    resumen: dict[str, dict[str, Any]] = {}

    def anotar(fechas, var: str, valores, accion: str, motivo: str) -> None:
        for f, v in zip(fechas, valores):
            registros.append({"fecha": pd.Timestamp(f).strftime("%Y-%m"), "variable": var,
                              "valor_original": float(v) if v is not None else np.nan,
                              "accion": accion, "motivo": motivo})

    for var in VARIABLES:
        cont = {"duplicados_contradictorios": 0, "duplicados_identicos": 0, "no_finitos": 0, "relleno": 0,
                "fuera_de_rango": 0, "fuera_de_periodo": 0, "meses_ausentes": 0, "ceros_exactos": 0}
        s_in = series.get(var)
        if s_in is None:
            s = pd.Series(np.nan, index=calendario, dtype="float64")
            anotar(calendario, var, [np.nan] * len(calendario), "faltante", "variable ausente en la entrada")
            cont["meses_ausentes"] = len(calendario)
        else:
            # 1. tipo y orden
            valores = pd.to_numeric(pd.Series(np.asarray(s_in.values), dtype="object"), errors="coerce")
            s = pd.Series(valores.to_numpy(dtype="float64"), index=_a_inicio_de_mes(s_in.index)).sort_index()

            # 2. duplicados
            if s.index.has_duplicates:
                grupos = s.groupby(level=0)
                distintos = grupos.agg(lambda g: np.unique(g.to_numpy()[np.isfinite(g.to_numpy())]).size > 1)
                dup_fechas = s.index[s.index.duplicated(keep="first")].unique()
                for f in dup_fechas:
                    if bool(distintos.loc[f]):
                        cont["duplicados_contradictorios"] += 1
                        anotar([f], var, [np.nan], "faltante", "fecha duplicada con valores distintos")
                    else:
                        cont["duplicados_identicos"] += 1
                        anotar([f], var, [float(s.loc[f].iloc[0])], "conservado", "fecha duplicada con valor idéntico")
                primero = grupos.first()
                primero[distintos[distintos].index] = np.nan
                s = primero.astype("float64")

            # 3. no finitos
            inf = np.isinf(s.to_numpy())
            if inf.any():
                cont["no_finitos"] = int(inf.sum())
                anotar(s.index[inf], var, s.to_numpy()[inf], "faltante", "valor no finito (±inf)")
                s[inf] = np.nan

            # 4. relleno
            x = s.to_numpy()
            relleno = np.isfinite(x) & ((x <= -999.0) | (np.abs(x) >= 1e15))
            if relleno.any():
                cont["relleno"] = int(relleno.sum())
                anotar(s.index[relleno], var, x[relleno], "faltante", "valor de relleno (≤ −999 o |x| ≥ 1e15)")
                s[relleno] = np.nan

            # 5. límites físicos
            lo, hi = LIMITES_FISICOS[var]
            x = s.to_numpy()
            fuera = np.isfinite(x) & ((x < lo) | (x > hi))
            if fuera.any():
                cont["fuera_de_rango"] = int(fuera.sum())
                anotar(s.index[fuera], var, x[fuera], "faltante",
                       f"fuera del límite físico [{lo:g}, {hi:g}] {UNIDAD_MENSUAL[var]}")
                s[fuera] = np.nan

            # 6. calendario completo
            fuera_periodo = ~s.index.isin(calendario)
            cont["fuera_de_periodo"] = int(fuera_periodo.sum())
            ausentes = calendario.difference(s.index)
            if len(ausentes):
                cont["meses_ausentes"] = int(len(ausentes))
                anotar(ausentes, var, [np.nan] * len(ausentes), "faltante", "mes ausente en la entrada")
            s = s.reindex(calendario)

            # 7. ceros exactos
            if var in CON_CEROS_SOSPECHOSOS:
                ceros = s.to_numpy() == 0.0
                if ceros.any():
                    cont["ceros_exactos"] = int(ceros.sum())
                    anotar(s.index[ceros], var, [0.0] * int(ceros.sum()), "advertencia",
                           "cero exacto en un promedio regional (posible faltante disfrazado)")

        s.index.name = "fecha"
        columnas[var] = s.astype("float64")
        validos = int(s.notna().sum())
        anios_incompletos = sorted({int(a) for a in s.index[s.isna()].year})
        resumen[var] = {
            "unidad": UNIDAD_MENSUAL[var],
            "limites_fisicos": list(LIMITES_FISICOS[var]),
            "n_meses_esperados": int(len(calendario)),
            "n_meses_validos": validos,
            "n_meses_faltantes": int(len(calendario) - validos),
            "anios_incompletos": anios_incompletos,
            **cont,
        }

    mensual = pd.DataFrame(columnas, index=calendario)[list(VARIABLES)]
    mensual.index.name = "fecha"
    registro = pd.DataFrame(registros, columns=["fecha", "variable", "valor_original", "accion", "motivo"])
    if not registro.empty:
        registro = registro.sort_values(["fecha", "variable"], kind="stable").reset_index(drop=True)
    return ResultadoLimpieza(mensual=mensual, registro=registro, resumen=resumen)


# ----------------------------------------------------------------------------------------------- lectura de tablas
ALIAS_COLUMNAS: dict[str, tuple[str, ...]] = {
    "P": ("p", "p_mm_mes", "precip", "precipitacion", "precipitación", "lluvia", "sat_gauge_precip"),
    "T": ("t", "t_c", "t_degc", "t2m", "temp", "temperatura"),
    "SM": ("sm", "sm_m3_m3", "soilmoi0_10cm_inst", "humedad_suelo", "soil_moisture"),
    "ET": ("et", "et_mm_mes", "evap_tavg", "evapotranspiracion", "evapotranspiración", "evap"),
}
COLUMNAS_FECHA: tuple[str, ...] = ("fecha", "date", "time", "mes_fecha", "periodo")


def leer_tabla_mensual(df: pd.DataFrame) -> tuple[dict[str, pd.Series], list[dict[str, Any]], dict[str, str]]:
    """Convierte una tabla mensual (CSV o JSON) en cuatro series indexadas por fecha.

    Acepta una columna de fecha (`fecha`, `date`, `time`…, formato AAAA-MM o AAAA-MM-DD, con o sin hora) o el par
    `anio`+`mes`, y columnas de variables por código o nombre de campo NASA (ver ALIAS_COLUMNAS). Los textos no
    numéricos ("NA", "", "--") pasan a faltante. Las filas con fecha ilegible se descartan y se registran.
    Devuelve (series por variable presente, registro de lectura, mapa variable → columna usada).
    """
    normal = {str(c).strip().lower(): c for c in df.columns}
    registro: list[dict[str, Any]] = []
    col_fecha = next((normal[c] for c in COLUMNAS_FECHA if c in normal), None)
    if col_fecha is not None:
        texto = df[col_fecha].astype(str).str.strip().str.slice(0, 7).str.replace("/", "-", regex=False)
        fechas = pd.to_datetime(texto, format="%Y-%m", errors="coerce")
    else:
        col_a = next((normal[c] for c in ("anio", "año", "ano", "year") if c in normal), None)
        col_m = next((normal[c] for c in ("mes", "month") if c in normal), None)
        if col_a is None or col_m is None:
            raise ValueError("La tabla necesita una columna de fecha (fecha/date/time) o las columnas anio y mes.")
        anio = pd.to_numeric(df[col_a], errors="coerce")
        mes = pd.to_numeric(df[col_m], errors="coerce")
        ok = anio.notna() & mes.between(1, 12)
        fechas = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
        fechas[ok] = pd.to_datetime(
            {"year": anio[ok].astype(int), "month": mes[ok].astype(int), "day": 1}, errors="coerce"
        )
    malas = fechas.isna()
    for i in np.flatnonzero(malas.to_numpy()):
        registro.append({"fecha": None, "variable": "*", "valor_original": np.nan, "accion": "descartado",
                         "motivo": f"fila {int(i) + 1}: fecha ilegible"})
    columnas: dict[str, str] = {}
    for var, alias in ALIAS_COLUMNAS.items():
        col = next((normal[a] for a in alias if a in normal), None)
        if col is not None:
            columnas[var] = str(col)
    if not columnas:
        raise ValueError("No se encontró ninguna columna de variables (P, T, SM, ET o sus nombres de campo NASA).")
    series: dict[str, pd.Series] = {}
    idx = pd.DatetimeIndex(fechas[~malas])
    for var, col in columnas.items():
        valores = pd.to_numeric(
            df.loc[~malas, col].astype(str).str.strip().str.replace(",", ".", regex=False), errors="coerce"
        )
        series[var] = pd.Series(valores.to_numpy(dtype="float64"), index=idx)
    for var in VARIABLES:
        if var not in columnas:
            registro.append({"fecha": None, "variable": var, "valor_original": np.nan, "accion": "faltante",
                             "motivo": "columna ausente en la entrada"})
    return series, registro, columnas


def convertir_unidades_originales(series: dict[str, pd.Series]) -> tuple[dict[str, pd.Series], list[dict[str, Any]]]:
    """Convierte de unidades NASA a finales, una sola vez y con los días reales de cada mes.

    P mm/día × días → mm/mes; T K − 273.15 → °C; SM kg/m² ÷ 100 → m³/m³; ET kg/m²/s × 86 400 × días → mm/mes.
    Los valores de relleno en unidades originales (≤ −999 o |x| ≥ 1e15) se marcan como faltante ANTES de convertir,
    para que el motivo quede bien registrado.
    """
    registro: list[dict[str, Any]] = []
    salida: dict[str, pd.Series] = {}
    for var, s in series.items():
        x = s.to_numpy(dtype="float64").copy()
        relleno = np.isfinite(x) & ((x <= -999.0) | (np.abs(x) >= 1e15))
        for f, v in zip(s.index[relleno], x[relleno]):
            registro.append({"fecha": pd.Timestamp(f).strftime("%Y-%m"), "variable": var, "valor_original": float(v),
                             "accion": "faltante", "motivo": "valor de relleno en unidades originales"})
        x[relleno] = np.nan
        dias = s.index.days_in_month.to_numpy(dtype="float64")
        if var == "P":
            x = x * dias
        elif var == "T":
            x = x - 273.15
        elif var == "SM":
            x = x / 100.0
        elif var == "ET":
            x = x * 86400.0 * dias
        salida[var] = pd.Series(x, index=s.index)
    return salida, registro


# ----------------------------------------------------------------------------------------------- tablas con formato
def _fmt(x: Any, dec: int) -> str:
    if x is None:
        return ""
    xf = float(x)
    return f"{xf:.{dec}f}" if np.isfinite(xf) else ""


def tabla_mensual_formateada(resultado_dte: dict[str, Any]) -> pd.DataFrame:
    """Tabla mensual de presentación: fecha, año, mes, días, P/T/SM/ET (decimales fijos) y z (3 decimales)."""
    vars_d = resultado_dte["variables"]
    fechas = [m["date"] for m in vars_d["P"]["monthly"]]
    filas = []
    for i, f in enumerate(fechas):
        a, m = int(f[:4]), int(f[5:7])
        fila: dict[str, Any] = {"fecha": f, "anio": a, "mes": m, "dias_mes": calendar.monthrange(a, m)[1]}
        for v in VARIABLES:
            fila[COLUMNA_MENSUAL[v]] = _fmt(vars_d[v]["monthly"][i]["value"], DECIMALES[v])
        for v in VARIABLES:
            fila[f"z_{v}"] = _fmt(vars_d[v]["monthly"][i]["z"], 3)
        fila["meses_validos_4_variables"] = int(sum(vars_d[v]["monthly"][i]["value"] is not None for v in VARIABLES))
        filas.append(fila)
    return pd.DataFrame(filas)


def tabla_anual_formateada(resultado_dte: dict[str, Any]) -> pd.DataFrame:
    """Tabla anual de presentación: valores anuales, marca de año completo por variable y si entra en el tramo."""
    vars_d = resultado_dte["variables"]
    tr = resultado_dte["metadata"].get("trend_span") or {}
    filas = []
    for i, fila_p in enumerate(vars_d["P"]["annual"]):
        a = int(fila_p["year"])
        fila: dict[str, Any] = {"anio": a}
        for v in VARIABLES:
            fila[COLUMNA_ANUAL[v]] = _fmt(vars_d[v]["annual"][i]["value"], DECIMALES[v])
        for v in VARIABLES:
            fila[f"completo_{v}"] = int(vars_d[v]["annual"][i]["value"] is not None)
        fila["en_tramo_tendencias"] = int(bool(tr) and tr["start"] <= a <= tr["end"])
        filas.append(fila)
    return pd.DataFrame(filas)


TABLAS_DTE: tuple[str, ...] = ("mensual", "anual", "limpieza", "diccionario", "serie_regional")


def tabla_dte(resultado_dte: dict[str, Any], tabla: str) -> pd.DataFrame:
    """Devuelve una de las tablas de presentación como DataFrame (mensual, anual, limpieza, diccionario, serie_regional)."""
    if tabla == "mensual":
        return tabla_mensual_formateada(resultado_dte)
    if tabla == "anual":
        return tabla_anual_formateada(resultado_dte)
    if tabla == "limpieza":
        return pd.DataFrame(resultado_dte.get("data_cleaning", {}).get("log", []),
                            columns=["fecha", "variable", "valor_original", "accion", "motivo"])
    if tabla == "diccionario":
        return diccionario_datos()
    if tabla == "serie_regional":
        vars_d = resultado_dte["variables"]
        return pd.DataFrame({
            "fecha": [m["date"] for m in vars_d["P"]["monthly"]],
            **{v: [m["value"] for m in vars_d[v]["monthly"]] for v in VARIABLES},
        })
    raise ValueError(f"tabla debe ser una de {list(TABLAS_DTE)}, no {tabla!r}")


def tablas_dte_json(resultado_dte: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Tablas mensual, anual y diccionario como listas de registros (para respuestas JSON)."""
    return {t: tabla_dte(resultado_dte, t).to_dict(orient="records") for t in ("mensual", "anual", "diccionario")}


def diccionario_datos() -> pd.DataFrame:
    """Descripción de cada columna de las tablas mensual y anual (unidad, tipo, fuente, conversión, decimales)."""
    fuentes = {
        "P": ("GPCP mensual v3.3 (GPCPMON), sat_gauge_precip", "mm/día × días del mes"),
        "T": ("MERRA-2 mensual (M2TMNXSLV), T2M", "K − 273.15"),
        "SM": ("GLDAS Noah mensual 2.1, SoilMoi0_10cm_inst", "kg/m² ÷ 100 (capa 0–10 cm)"),
        "ET": ("GLDAS Noah mensual 2.1, Evap_tavg", "kg/m²/s × 86 400 × días del mes"),
    }
    filas = [
        {"tabla": "mensual", "columna": "fecha", "descripcion": "Mes (AAAA-MM)", "unidad": "", "tipo": "texto",
         "fuente": "", "conversion": "", "decimales": ""},
        {"tabla": "mensual", "columna": "dias_mes", "descripcion": "Días reales del mes (bisiestos incluidos)",
         "unidad": "días", "tipo": "entero", "fuente": "", "conversion": "", "decimales": 0},
    ]
    for v in VARIABLES:
        fu, conv = fuentes[v]
        filas.append({"tabla": "mensual", "columna": COLUMNA_MENSUAL[v],
                      "descripcion": f"{v}: promedio regional ponderado por área (vacío = faltante)",
                      "unidad": UNIDAD_MENSUAL[v], "tipo": "decimal", "fuente": fu, "conversion": conv,
                      "decimales": DECIMALES[v]})
    for v in VARIABLES:
        filas.append({"tabla": "mensual", "columna": f"z_{v}",
                      "descripcion": f"Anomalía estandarizada de {v} por mes calendario (conserva la tendencia)",
                      "unidad": "adimensional", "tipo": "decimal", "fuente": "", "conversion": "", "decimales": 3})
    for v in VARIABLES:
        agg = "suma de 12 meses" if v in ("P", "ET") else "media ponderada por días Σ(X·días)/Σ(días)"
        filas.append({"tabla": "anual", "columna": COLUMNA_ANUAL[v],
                      "descripcion": f"{v} anual: {agg}; vacío si falta algún mes", "unidad": UNIDAD_ANUAL[v],
                      "tipo": "decimal", "fuente": fuentes[v][0], "conversion": "", "decimales": DECIMALES[v]})
    filas.append({"tabla": "anual", "columna": "completo_<VAR>", "descripcion": "1 si el año tiene los 12 meses",
                  "unidad": "", "tipo": "entero 0/1", "fuente": "", "conversion": "", "decimales": 0})
    filas.append({"tabla": "anual", "columna": "en_tramo_tendencias",
                  "descripcion": "1 si el año entra en el tramo común usado para las tendencias", "unidad": "",
                  "tipo": "entero 0/1", "fuente": "", "conversion": "", "decimales": 0})
    return pd.DataFrame(filas)
