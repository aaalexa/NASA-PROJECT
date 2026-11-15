"""Motor estadístico y análisis conjunto "Down to Earth: Cuatro variables, dos formas de analizarlas".

Implementa fielmente las secciones §01–§06 de la guía práctica Down to Earth:
    - Cuatro variables mensuales en una región:
        P  (lluvia_gpcp, GPCPMON, mm/mes → suma anual en mm/anio)
        T  (temp_aire, M2TMNXSLV, degC → promedio anual ponderado por días del mes en degC)
        SM (humedad_suelo, GLDAS_NOAH025_M, m3/m3 → promedio anual ponderado por días del mes en m3/m3)
        ET (evapotranspiracion, GLDAS_NOAH025_M, mm/mes → suma anual en mm/anio)
    - Tendencia individual (§03 y §03.1):
        Regresión lineal OLS con constante sobre años completos y consecutivos (`t = anio - anio_inicial`),
        errores estándar HAC / Newey-West (`maxlags=1`, `kernel='bartlett'`, `use_correction=True`, `use_t=False`),
        prueba bilateral normal de Wald, cambio e IC95 % por década (× 10), ajuste de multiplicidad de Holm
        sobre la familia fija `[P, T, SM, ET]` y análisis de sensibilidad con rezagos 2 y 3.
    - Análisis conjunto (§04):
        Anomalías mensuales estandarizadas `z = (valor - μ_mes) / s_mes` en el período 2001–2024 y correlación
        exploratoria de Pearson `r` sobre los residuos sin tendencia lineal para los tres pares prioritarios:
        `P–SM`, `T–SM` y `P–ET` (sin asignar significancia ni causalidad).
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
import xarray as xr

from core.motor.limpieza_dte import limpiar_series_dte
from core.motor.series import (
    agregar_anual,
    anomalias_estandarizadas,
    fraccion_tierra_desde_malla,
    pesos_area_region,
    promedio_area,
    reindexar_calendario,
)

PERIODO_DTE_DEFECTO: tuple[str, str] = ("2001-01", "2024-12")
MIN_VALORES_CLIMATOLOGIA: int = 10  # valores mínimos por mes calendario para calcular μ_mes y s_mes (z)
ANIOS_ADVERTENCIA_DTE: int = 10  # por debajo se advierte que la inferencia HAC es frágil
ORDEN_FAMILIA_DTE: tuple[str, str, str, str] = ("P", "T", "SM", "ET")
ORDEN_VARIABLES_DTE: tuple[str, str, str, str] = ORDEN_FAMILIA_DTE

MAPA_CODIGO_A_VARIABLE: dict[str, str] = {
    "P": "lluvia_gpcp",
    "T": "temp_aire",
    "SM": "humedad_suelo",
    "ET": "evapotranspiracion",
}

MAPA_VARIABLE_A_CODIGO: dict[str, str] = {v: k for k, v in MAPA_CODIGO_A_VARIABLE.items()}

INFO_VARIABLES_DTE: dict[str, dict[str, Any]] = {
    "P": {
        "id": "lluvia_gpcp",
        "code": "P",
        "nombre": "Precipitación (P)",
        "pregunta": "¿Está llegando más o menos agua?",
        "por_que_elegirla": "Es el fenómeno principal del proyecto.",
        "coleccion": "GPCP mensual v3.3 (la v3.2 termina en 2023-12; v3.3 conserva sat_gauge_precip)",
        "short_name": "GPCPMON",
        "campo": "sat_gauge_precip",
        "conversion_texto": "mm/día × días del mes → mm/mes",
        "agregacion_anual": "suma",
        "unidad_mensual": "mm/mes",
        "unidad_anual": "mm/anio",
        "unidad_decada": "mm por década (total anual)",
        "decimales": 1,
    },
    "T": {
        "id": "temp_aire",
        "code": "T",
        "nombre": "Temperatura del aire (T)",
        "pregunta": "¿La región se está calentando?",
        "por_que_elegirla": "Permite estudiar si los cambios de lluvia coinciden con más calor.",
        "coleccion": "MERRA-2 mensual",
        "short_name": "M2TMNXSLV",
        "campo": "T2M",
        "conversion_texto": "K − 273.15 → °C",
        "agregacion_anual": "media_ponderada_dias",
        "unidad_mensual": "°C",
        "unidad_anual": "°C",
        "unidad_decada": "°C por década",
        "decimales": 2,
    },
    "SM": {
        "id": "humedad_suelo",
        "code": "SM",
        "nombre": "Humedad superficial del suelo (SM)",
        "pregunta": "¿El suelo conserva más o menos agua?",
        "por_que_elegirla": "Muestra una respuesta terrestre a las condiciones de agua y energía.",
        "coleccion": "GLDAS Noah mensual 2.1",
        "short_name": "GLDAS_NOAH025_M",
        "campo": "SoilMoi0_10cm_inst",
        "conversion_texto": "kg/m² ÷ 100 → m³/m³ (capa 0–10 cm)",
        "agregacion_anual": "media_ponderada_dias",
        "unidad_mensual": "m³/m³",
        "unidad_anual": "m³/m³",
        "unidad_decada": "m³/m³ por década",
        "decimales": 4,
    },
    "ET": {
        "id": "evapotranspiracion",
        "code": "ET",
        "nombre": "Evapotranspiración real (ET)",
        "pregunta": "¿Cuánta agua pasa del suelo y las plantas al aire?",
        "por_que_elegirla": "Ayuda a interpretar intercambios de agua, junto con lluvia y humedad.",
        "coleccion": "GLDAS Noah mensual 2.1",
        "short_name": "GLDAS_NOAH025_M",
        "campo": "Evap_tavg",
        "conversion_texto": "kg/m²/s × 86 400 × días del mes → mm/mes",
        "agregacion_anual": "suma",
        "unidad_mensual": "mm/mes",
        "unidad_anual": "mm/anio",
        "unidad_decada": "mm por década (total anual)",
        "decimales": 1,
    },
}

PARES_PRIORITARIOS_DTE: tuple[dict[str, str], ...] = (
    {
        "pair": "P-SM",
        "var_x": "P",
        "var_y": "SM",
        "pregunta": "¿Meses con menos lluvia también tienen el suelo más seco?",
        "cuidado": "El suelo puede responder con retraso; la correlación del mismo mes no detecta todo.",
    },
    {
        "pair": "T-SM",
        "var_x": "T",
        "var_y": "SM",
        "pregunta": "¿Meses más cálidos coinciden con suelo más seco?",
        "cuidado": "Pueden intervenir lluvia, vegetación y otras condiciones.",
    },
    {
        "pair": "P-ET",
        "var_x": "P",
        "var_y": "ET",
        "pregunta": "¿La ET cambia junto con la disponibilidad de lluvia?",
        "cuidado": "ET depende también de energía y plantas; su signo no está prefijado.",
    },
)


def _limpiar_num(v: Any) -> float | None:
    if v is None:
        return None
    f = float(v)
    return f if np.isfinite(f) else None


def tramo_anios_completos_consecutivos(anios: np.ndarray, valores: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Selecciona el tramo más largo de años completos y consecutivos sin comprimir huecos (§02 y §03.1 paso 1)."""
    anios_int = np.asarray(anios, dtype=int).ravel()
    vals = np.asarray(valores, dtype=np.float64).ravel()
    advertencias: list[str] = []

    valido = np.isfinite(vals)
    if not np.any(valido):
        return np.array([], dtype=int), np.array([], dtype=np.float64), ["No hay ningún año completo válido."]

    indices_validos = np.flatnonzero(valido)
    anios_val = anios_int[indices_validos]
    vals_val = vals[indices_validos]

    # Dividir donde los años válidos no sean consecutivos (diff != 1) para nunca comprimir huecos.
    cortes = np.flatnonzero(np.diff(anios_val) != 1) + 1
    bloques_a = np.split(anios_val, cortes)
    bloques_v = np.split(vals_val, cortes)

    if len(bloques_a) > 1 or anios_val.size < anios_int.size:
        faltantes = sorted(set(anios_int.tolist()) - set(anios_val.tolist()))
        if faltantes:
            advertencias.append(f"Años incompletos excluidos sin comprimir huecos: {faltantes}.")

    idx_mejor = int(np.argmax([b.size for b in bloques_a]))
    mejor_a = bloques_a[idx_mejor]
    mejor_v = bloques_v[idx_mejor]
    if len(bloques_a) > 1:
        advertencias.append(
            f"Se seleccionó el tramo continuo más largo de años completos y consecutivos: "
            f"{int(mejor_a[0])}–{int(mejor_a[-1])} ({mejor_a.size} años)."
        )
    return mejor_a, mejor_v, advertencias


def tramo_comun_anios_completos(
    series_anuales: dict[str, tuple[np.ndarray, np.ndarray]],
) -> tuple[int, int] | None:
    """Tramo común más largo de años completos y consecutivos para las variables evaluables (§02).

    Una variable es evaluable si tiene al menos un año completo; las que no tienen ninguno no recortan el tramo de
    las demás (se publican como null). El tramo es el mismo para las cuatro variables, de modo que la familia de
    Holm compara pendientes del mismo período. Los huecos no se comprimen. Empate → el tramo más reciente.
    """
    completos: list[set[int]] = []
    todos: set[int] = set()
    for cod in ORDEN_FAMILIA_DTE:
        if cod not in series_anuales:
            continue
        anios, vals = series_anuales[cod]
        anios_i = np.asarray(anios, dtype=int).ravel()
        vals_f = np.asarray(vals, dtype=np.float64).ravel()
        todos |= set(anios_i.tolist())
        ok = set(anios_i[np.isfinite(vals_f)].tolist())
        if ok:
            completos.append(ok)
    if not completos:
        return None
    comunes = set.intersection(*completos)
    mejor: tuple[int, int] | None = None
    ini: int | None = None
    prev: int | None = None
    for a in [*sorted(todos), None]:  # None = centinela que cierra el último bloque
        if a is not None and a in comunes and prev is not None and a == prev + 1:
            prev = a
            continue
        if ini is not None and prev is not None:
            if mejor is None or (prev - ini) >= (mejor[1] - mejor[0]):  # >= → empate gana el más reciente
                mejor = (ini, prev)
        if a is not None and a in comunes:
            ini = prev = a
        else:
            ini = prev = None
    return mejor


def _fmt_signo(x: float | None, dec: int) -> str:
    return "null" if x is None or not np.isfinite(x) else f"{x:+.{dec}f}"


def _fmt_p(p: float | None) -> str:
    if p is None or not np.isfinite(p):
        return "null"
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def ajustar_ols_hac_anual(
    anios: np.ndarray,
    valores: np.ndarray,
    *,
    maxlags: int = 1,
    alfa: float = 0.05,
) -> dict[str, Any]:
    """Ejecuta los pasos 1–5 de §03.1 sobre una serie anual con statsmodels OLS + HAC (Newey–West).

    Configuración exacta (§03):
        `sm.OLS(y, sm.add_constant(t)).fit(cov_type='HAC', cov_kwds={'maxlags': maxlags, 'kernel': 'bartlett', 'use_correction': True}, use_t=False)`
    """
    anios_tramo, y, advertencias = tramo_anios_completos_consecutivos(anios, valores)
    n = int(y.size)
    if n < 3:
        return {
            "valido": False,
            "n_anios": n,
            "periodo_anual": [int(anios_tramo[0]), int(anios_tramo[-1])] if n > 0 else None,
            "anio_inicial": int(anios_tramo[0]) if n > 0 else None,
            "t": [],
            "anios_usados": anios_tramo.tolist(),
            "valores_usados": [_limpiar_num(v) for v in y],
            "ajustados": [],
            "residuos": [],
            "intercept_a": None,
            "slope_annual": None,
            "se_annual": None,
            "z_stat": None,
            "p_raw": None,
            "slope_decade": None,
            "ci95": None,
            "maxlags": int(maxlags),
            "advertencias": [*advertencias, f"Serie anual insuficiente ({n} años completos; mínimo 3)."],
        }

    anio_0 = int(anios_tramo[0])
    t = (anios_tramo - anio_0).astype(np.float64)
    x_mat = sm.add_constant(t, has_constant="add")
    res = sm.OLS(y, x_mat).fit(
        cov_type="HAC",
        cov_kwds={"maxlags": int(maxlags), "kernel": "bartlett", "use_correction": True},
        use_t=False,
    )

    a = float(res.params[0])
    b = float(res.params[1])
    slope_decade = 10.0 * b
    ajustados = a + b * t
    residuos = y - ajustados

    se = float(res.bse[1]) if res.bse.size > 1 else float("nan")
    ss_res = float(np.sum(residuos**2))

    # Paso 3 (§03.1): Si SE es cero o no finito (o ajuste determinista exacto sin ruido), no emitir inferencia automática.
    if not np.isfinite(se) or se <= 1e-15 or ss_res <= 1e-24 * max(1.0, float(np.sum((y - y.mean()) ** 2))):
        advertencias.append("SE es cero o no finito; se reporta la pendiente pero no se emite inferencia automática.")
        return {
            "valido": True,
            "inferencia_disponible": False,
            "n_anios": n,
            "periodo_anual": [int(anios_tramo[0]), int(anios_tramo[-1])],
            "anio_inicial": anio_0,
            "t": t.tolist(),
            "anios_usados": anios_tramo.tolist(),
            "valores_usados": [_limpiar_num(v) for v in y],
            "ajustados": [_limpiar_num(v) for v in ajustados],
            "residuos": [_limpiar_num(v) for v in residuos],
            "intercept_a": _limpiar_num(a),
            "slope_annual": _limpiar_num(b),
            "se_annual": None,
            "z_stat": None,
            "p_raw": None,
            "slope_decade": _limpiar_num(slope_decade),
            "ci95": None,
            "maxlags": int(maxlags),
            "advertencias": advertencias,
        }

    z_stat = float(res.tvalues[1])
    p_raw = float(res.pvalues[1])
    ci_anual = res.conf_int(alpha=alfa)[1]
    ci95_decada = [10.0 * float(ci_anual[0]), 10.0 * float(ci_anual[1])]

    return {
        "valido": True,
        "inferencia_disponible": True,
        "n_anios": n,
        "periodo_anual": [int(anios_tramo[0]), int(anios_tramo[-1])],
        "anio_inicial": anio_0,
        "t": t.tolist(),
        "anios_usados": anios_tramo.tolist(),
        "valores_usados": [_limpiar_num(v) for v in y],
        "ajustados": [_limpiar_num(v) for v in ajustados],
        "residuos": [_limpiar_num(v) for v in residuos],
        "intercept_a": _limpiar_num(a),
        "slope_annual": _limpiar_num(b),
        "se_annual": _limpiar_num(se),
        "z_stat": _limpiar_num(z_stat),
        "p_raw": _limpiar_num(p_raw),
        "slope_decade": _limpiar_num(slope_decade),
        "ci95": [_limpiar_num(ci95_decada[0]), _limpiar_num(ci95_decada[1])],
        "maxlags": int(maxlags),
        "advertencias": advertencias,
    }


def _etiqueta_y_mensaje_dte(
    codigo: str,
    ajuste: dict[str, Any],
    p_holm: float | None,
    sensible_al_rezago: bool,
    alfa: float = 0.05,
) -> tuple[str, str | None, str | None, str]:
    """Etiqueta, dirección, signo de la estimación y texto de pantalla según las reglas de comunicación (§03.2).

    - La etiqueta la decide el p ajustado por Holm, no el IC individual ni el p sin ajustar.
    - p_holm ≤ α → "aumento/disminución con evidencia estadística según este método".
    - p_holm > α → "evidencia insuficiente" (no significa "no cambió"); "tras el ajuste" solo si p_raw ≤ α.
    - Nunca se emite "sin cambio".
    Devuelve (etiqueta, direction, estimate_sign, texto). `direction` solo es "aumento"/"disminucion" cuando hay
    evidencia; si no, None. `estimate_sign` describe el signo de la pendiente estimada (positiva/negativa/nula).
    """
    info = INFO_VARIABLES_DTE[codigo]
    nombre = info["nombre"]
    unidad_dec = info["unidad_decada"]
    dec = int(info.get("decimales", 3))
    b_dec = ajuste.get("slope_decade")
    ci95 = ajuste.get("ci95")
    p_raw = ajuste.get("p_raw")
    n = ajuste.get("n_anios", 0)
    per = ajuste.get("periodo_anual")
    per_txt = f"{per[0]}–{per[1]}" if per else "sin período válido"

    if b_dec is None:
        motivo = "; ".join(ajuste.get("advertencias") or ["datos insuficientes para estimar tendencia"])
        return f"no evaluable: {motivo}", None, None, f"{nombre}: no evaluable ({motivo})."

    signo = "positiva" if b_dec > 0 else ("negativa" if b_dec < 0 else "nula")
    if p_holm is None or p_raw is None or ci95 is None:
        etiqueta = "sin inferencia: SE cero o no finito (serie sin variación residual)"
        texto = (
            f"{nombre} cambió aproximadamente {_fmt_signo(b_dec, dec)} {unidad_dec}; {etiqueta}. "
            f"Período {per_txt}, {n} años válidos."
        )
        return etiqueta, None, signo, texto

    direccion: str | None = None
    if p_holm <= alfa:
        if b_dec > 0:
            etiqueta, direccion = "aumento con evidencia estadística según este método", "aumento"
        else:
            etiqueta, direccion = "disminución con evidencia estadística según este método", "disminucion"
    elif p_raw <= alfa:
        etiqueta = "evidencia insuficiente tras el ajuste"
    else:
        etiqueta = "evidencia insuficiente"
    if sensible_al_rezago:
        etiqueta += "; resultado sensible al rezago"

    texto = (
        f"{nombre} cambió aproximadamente {_fmt_signo(b_dec, dec)} {unidad_dec}; "
        f"IC95 % [{_fmt_signo(ci95[0], dec)}, {_fmt_signo(ci95[1], dec)}]; p ajustado {_fmt_p(p_holm)}; {etiqueta}. "
        f"Período {per_txt}, {n} años válidos."
    )
    return etiqueta, direccion, signo, texto


def evaluar_cuatro_tendencias_holm(
    series_anuales: dict[str, tuple[np.ndarray, np.ndarray]],
    *,
    alfa: float = 0.05,
) -> dict[str, dict[str, Any]]:
    """Evalúa la familia fija [P, T, SM, ET] con OLS+HAC (rezago 1), ajuste Holm y sensibilidad en rezagos 2 y 3 (§03.1).

    Si una variable no puede evaluarse, se coloca internamente `p=1.0` en su posición solo para conservar las
    cuatro hipótesis en `multipletests(..., method='holm')`, pero se publica `p_raw=None` y `p_holm=None`.

    Las cuatro pendientes se estiman en el mismo tramo: el tramo común más largo de años completos y consecutivos
    (`tramo_comun_anios_completos`). Cada resultado incluye `tramo_comun` ([inicio, fin] o None).
    """
    tramo = tramo_comun_anios_completos(series_anuales)
    series_tramo: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for cod, (anios, vals) in series_anuales.items():
        anios_i = np.asarray(anios, dtype=int).ravel()
        vals_f = np.asarray(vals, dtype=np.float64).ravel()
        if tramo is None or not np.any(np.isfinite(vals_f)):
            continue  # no evaluable: se publica null con motivo
        sel = (anios_i >= tramo[0]) & (anios_i <= tramo[1])
        series_tramo[cod] = (anios_i[sel], vals_f[sel])

    por_rezago: dict[int, dict[str, dict[str, Any]]] = {}
    decision_por_rezago: dict[int, dict[str, bool | None]] = {}

    for lag in (1, 2, 3):
        ajustes_lag: dict[str, dict[str, Any]] = {}
        pvals_internos: list[float] = []
        tiene_p_real: dict[str, bool] = {}

        for cod in ORDEN_FAMILIA_DTE:
            if cod in series_tramo:
                anios, vals = series_tramo[cod]
                aj = ajustar_ols_hac_anual(anios, vals, maxlags=lag, alfa=alfa)
            else:
                aj = ajustar_ols_hac_anual(np.array([]), np.array([]), maxlags=lag, alfa=alfa)
                if cod not in series_anuales:
                    aj["advertencias"] = ["variable ausente en la entrada"]
                else:
                    aj["advertencias"] = ["sin años completos (12 meses válidos) en el período"]
            ajustes_lag[cod] = aj
            p_r = aj.get("p_raw")
            if p_r is not None and np.isfinite(p_r):
                pvals_internos.append(float(p_r))
                tiene_p_real[cod] = True
            else:
                # Paso 6 (§03.1): marcador interno p=1 para conservar las 4 hipótesis en Holm; no se publica.
                pvals_internos.append(1.0)
                tiene_p_real[cod] = False

        rechazo, p_holm_arr, _, _ = multipletests(pvals_internos, alpha=alfa, method="holm")
        decision_por_rezago[lag] = {}
        for idx, cod in enumerate(ORDEN_FAMILIA_DTE):
            if tiene_p_real[cod]:
                p_h = float(p_holm_arr[idx])
                sig = bool(rechazo[idx])
                ajustes_lag[cod]["p_holm"] = _limpiar_num(p_h)
                ajustes_lag[cod]["significant"] = sig
                decision_por_rezago[lag][cod] = sig
            else:
                ajustes_lag[cod]["p_holm"] = None
                ajustes_lag[cod]["significant"] = None
                decision_por_rezago[lag][cod] = None

        por_rezago[lag] = ajustes_lag

    salida: dict[str, dict[str, Any]] = {}
    for cod in ORDEN_FAMILIA_DTE:
        principal = dict(por_rezago[1][cod])
        sig_1 = decision_por_rezago[1][cod]
        sig_2 = decision_por_rezago[2][cod]
        sig_3 = decision_por_rezago[3][cod]
        sensible = bool(
            sig_1 is not None
            and ((sig_2 is not None and sig_2 != sig_1) or (sig_3 is not None and sig_3 != sig_1))
        )
        if sensible and "resultado sensible al rezago" not in principal["advertencias"]:
            principal["advertencias"] = [*principal["advertencias"], "resultado sensible al rezago"]

        etiqueta, direccion, signo, texto = _etiqueta_y_mensaje_dte(
            cod, principal, principal.get("p_holm"), sensible, alfa=alfa
        )
        principal["label"] = etiqueta
        principal["direction"] = direccion
        principal["estimate_sign"] = signo
        principal["summary_text"] = texto
        principal["sensible_al_rezago"] = sensible
        principal["tramo_comun"] = [int(tramo[0]), int(tramo[1])] if tramo else None
        principal["sensibilidad_rezagos"] = {
            f"lag_{lag}": {
                "maxlags": lag,
                "se_annual": por_rezago[lag][cod].get("se_annual"),
                "z_stat": por_rezago[lag][cod].get("z_stat"),
                "ci95": por_rezago[lag][cod].get("ci95"),
                "p_raw": por_rezago[lag][cod].get("p_raw"),
                "p_holm": por_rezago[lag][cod].get("p_holm"),
                "significant": por_rezago[lag][cod].get("significant"),
            }
            for lag in (1, 2, 3)
        }
        salida[cod] = principal

    return salida


def _residuos_ols_tiempo_real(t: np.ndarray, z: np.ndarray) -> np.ndarray | None:
    """Quita por regresión OLS la tendencia lineal de una serie `z` usando el eje de tiempo real `t` (§04 paso 3)."""
    dt = t - np.mean(t)
    sxx = float(np.sum(dt**2))
    if sxx <= 0.0:
        return None
    b1 = float(np.sum(dt * (z - np.mean(z))) / sxx)
    b0 = float(np.mean(z) - b1 * np.mean(t))
    return z - (b0 + b1 * t)


def correlacion_exploratoria_sin_tendencia(
    z_x: xr.DataArray,
    z_y: xr.DataArray,
) -> dict[str, Any]:
    """Calcula la correlación de Pearson descriptiva `r` entre residuos sin tendencia lineal de dos series `z` (§04).

    Une por fecha mensual exacta (`time`). Primero quita la tendencia lineal de **cada** serie `z` con todos sus
    meses válidos y el tiempo real (meses desde el inicio); después calcula Pearson entre los residuos en las
    fechas comunes:
        r = Σ(u − ū)(v − v̄) / √[Σ(u − ū)² × Σ(v − v̄)²]
    Si algún residuo no varía o hay menos de 3 meses comunes, devuelve `r = None`.
    """
    al_x, al_y = xr.align(z_x, z_y, join="outer")
    if al_x.sizes.get("time", 0) == 0:
        return {"r": None, "n": 0, "periodo_comun": None}

    fechas = pd.DatetimeIndex(al_x["time"].values)
    t_real = ((fechas.year - fechas.year[0]) * 12 + (fechas.month - fechas.month[0])).values.astype(np.float64)
    vx = np.asarray(al_x.values, dtype=np.float64).ravel()
    vy = np.asarray(al_y.values, dtype=np.float64).ravel()

    def _sin_tendencia(v: np.ndarray) -> np.ndarray:
        ok = np.isfinite(v)
        out = np.full(v.shape, np.nan)
        if ok.sum() >= 3:
            res = _residuos_ols_tiempo_real(t_real[ok], v[ok])
            if res is not None:
                out[ok] = res
        return out

    ux_all = _sin_tendencia(vx)
    vy_all = _sin_tendencia(vy)
    comun = np.isfinite(ux_all) & np.isfinite(vy_all)
    n = int(np.sum(comun))
    if n < 3:
        return {"r": None, "n": n, "periodo_comun": None}

    fechas_c = fechas[comun]
    u = ux_all[comun]
    v = vy_all[comun]

    du = u - np.mean(u)
    dv = v - np.mean(v)
    ss_u = float(np.sum(du**2))
    ss_v = float(np.sum(dv**2))
    # Si un residuo no varía (§04 paso 3), devolver null.
    if ss_u <= 1e-20 or ss_v <= 1e-20:
        return {"r": None, "n": n, "periodo_comun": [fechas_c[0].strftime("%Y-%m"), fechas_c[-1].strftime("%Y-%m")]}

    r = float(np.sum(du * dv) / np.sqrt(ss_u * ss_v))
    r = float(np.clip(r, -1.0, 1.0))
    return {
        "r": _limpiar_num(r),
        "n": n,
        "periodo_comun": [fechas_c[0].strftime("%Y-%m"), fechas_c[-1].strftime("%Y-%m")],
    }


def analizar_cuatro_variables_dte(
    series_mensuales: dict[str, xr.DataArray],
    inicio: str = "2001-01",
    fin: str = "2024-12",
    *,
    alfa: float = 0.05,
    region_meta: dict[str, Any] | None = None,
    fuente_datos: str = "opendap_memoria",
    bbox: Sequence[float] | None = None,
    huella_tierra: bool = True,
    simulado: bool | None = None,
    registro_entrada: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Ejecuta el flujo completo de Down to Earth (§02, §03, §04 y §05) sobre las 4 variables mensuales.

    Entrada:
        `series_mensuales`: diccionario `{"P": da_p, "T": da_t, "SM": da_sm, "ET": da_et}` ya convertidas a sus
        unidades mensuales finales (`mm/mes`, `degC`, `m3/m3`, `mm/mes`). Acepta cubos 3-D `(time, lat, lon)` en
        su propia grilla nativa o series regionales 1-D `(time,)`.

    Promedio regional de los cubos 3-D (§02): X = Σ(Aᵢ·Xᵢ)/Σ(Aᵢ), con Aᵢ = área esférica de la celda dentro de la
    región (`bbox`, o `region_meta["bbox"]`). Con `huella_tierra=True`, el mismo territorio terrestre para las tres
    fuentes: las celdas de tierra de GLDAS (cubo de SM) definen la huella y P (GPCP) y T (MERRA-2) se ponderan por
    la fracción de cada celda cubierta por esa huella.

    `simulado` fuerza la marca `metadata.simulated` (por defecto: True solo si `fuente_datos == "sintetico"`).
    `registro_entrada` antepone al registro de limpieza las acciones previas (lectura de tabla, conversión de unidades).
    """
    calendario = pd.date_range(f"{inicio[:7]}-01", f"{fin[:7]}-01", freq="MS")
    n_meses_esperados = len(calendario)
    anios_esperados = np.arange(int(inicio[:4]), int(fin[:4]) + 1, dtype=int)
    n_anios_esperados = int(anios_esperados.size)
    advertencias_globales: list[str] = []
    simulado = (fuente_datos == "sintetico") if simulado is None else bool(simulado)
    if simulado:
        advertencias_globales.append(
            "DATOS SIMULADOS: al menos una variable es sintética; las cifras no describen la región real."
        )

    if bbox is None and region_meta and region_meta.get("bbox"):
        bbox = region_meta["bbox"]
    es_cubo = {c: ("lat" in series_mensuales[c].dims and "lon" in series_mensuales[c].dims) for c in ORDEN_FAMILIA_DTE}
    huella: xr.DataArray | None = None
    if huella_tierra and es_cubo.get("SM"):
        huella = series_mensuales["SM"]  # GLDAS: solo tiene datos sobre tierra
    ponderacion_txt = (
        "área esférica de cada celda dentro de la región"
        + (" × fracción de tierra según la huella de GLDAS" if huella is not None else "")
    )

    reind_mensual: dict[str, xr.DataArray] = {}
    series_z: dict[str, xr.DataArray] = {}
    series_anuales_da: dict[str, xr.DataArray] = {}
    series_anuales_tuplas: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    calidad_por_cod: dict[str, dict[str, Any]] = {}

    # 1) Promedio regional ponderado por área de cada variable (serie 1-D mensual)
    regionales: dict[str, xr.DataArray] = {}
    for cod in ORDEN_FAMILIA_DTE:
        da_in = series_mensuales[cod]
        if es_cubo[cod]:
            pesos = pesos_area_region(da_in, bbox)
            if huella is not None:
                pesos = pesos * fraccion_tierra_desde_malla(da_in, huella)
            regionales[cod] = promedio_area(da_in, pesos=pesos)
        else:
            regionales[cod] = da_in

    # 2) Limpieza estructural (pandas/numpy): tipos, fechas, duplicados, relleno, límites físicos, calendario
    limpieza = limpiar_series_dte(
        {c: regionales[c].to_series() for c in ORDEN_FAMILIA_DTE}, inicio, fin
    )
    for cod, res_c in limpieza.resumen.items():
        if res_c["fuera_de_rango"] or res_c["relleno"] or res_c["no_finitos"] or res_c["duplicados_contradictorios"]:
            advertencias_globales.append(
                f"{cod}: limpieza → {res_c['relleno']} relleno, {res_c['fuera_de_rango']} fuera de rango físico, "
                f"{res_c['no_finitos']} no finitos, {res_c['duplicados_contradictorios']} duplicados contradictorios "
                "pasados a faltante (ver data_cleaning.log)."
            )

    # 3) Análisis por variable sobre la serie limpia
    for cod in ORDEN_FAMILIA_DTE:
        info = INFO_VARIABLES_DTE[cod]
        da_1d = regionales[cod]
        da_m = xr.DataArray(
            limpieza.mensual[cod].to_numpy(dtype=np.float64),
            coords={"time": limpieza.mensual.index.values},
            dims=("time",),
            attrs={**da_1d.attrs, "units": da_1d.attrs.get("units", info["unidad_mensual"])},
            name=da_1d.name,
        )
        reind_mensual[cod] = da_m

        # Anomalías mensuales estandarizadas z = (X - μ_mes) / s_mes en el periodo de referencia (§04 pasos 1 y 2)
        try:
            da_z = anomalias_estandarizadas(da_m, base=(inicio, fin), min_valores=MIN_VALORES_CLIMATOLOGIA)
        except Exception:  # noqa: BLE001
            da_z = xr.DataArray(np.full(da_m.shape, np.nan), coords=da_m.coords, dims=da_m.dims)
        series_z[cod] = da_z

        # Agregación anual (§02): suma para P y ET; media ponderada por días para T y SM.
        metodo_agg = "suma" if info["agregacion_anual"] == "suma" else "media_ponderada_dias"
        da_a = agregar_anual(da_m, metodo_agg)
        da_a = reindexar_calendario(da_a, inicio[:4], fin[:4])
        series_anuales_da[cod] = da_a
        series_anuales_tuplas[cod] = (
            np.asarray(da_a["anio"].values, dtype=int),
            np.asarray(da_a.values, dtype=np.float64),
        )

        vals_m = np.asarray(da_m.values, dtype=np.float64)
        vals_a = np.asarray(da_a.values, dtype=np.float64)
        n_m_val = int(np.isfinite(vals_m).sum())
        n_a_val = int(np.isfinite(vals_a).sum())
        cob_media = _limpiar_num(da_m.attrs.get("cobertura_area_media", 1.0))
        cob_min = _limpiar_num(da_m.attrs.get("cobertura_area_min", 1.0))
        cob_estable = bool(da_m.attrs.get("cobertura_estable", True))
        if not cob_estable:
            advertencias_globales.append(
                f"{cod}: la fracción de área válida cambia con el tiempo ({cob_min:.2f}–1): parte de la tendencia "
                "puede ser un artefacto de cobertura."
            )
        n_ceros = int(np.sum(vals_m == 0.0))
        if cod in ("P", "SM", "ET") and n_ceros:
            advertencias_globales.append(
                f"{cod}: {n_ceros} ceros exactos en el promedio regional; suelen ser faltantes disfrazados, comprobar."
            )

        calidad_por_cod[cod] = {
            "n_exact_zeros": n_ceros,
            "n_months_expected": n_meses_esperados,
            "n_months_valid": n_m_val,
            "n_months_missing": n_meses_esperados - n_m_val,
            "missing_fraction_monthly": round((n_meses_esperados - n_m_val) / max(1, n_meses_esperados), 4),
            "n_years_expected": n_anios_esperados,
            "n_years_complete": n_a_val,
            "complete_period": n_m_val == n_meses_esperados and n_a_val == n_anios_esperados,
            "area_coverage_mean": cob_media,
            "area_coverage_min": cob_min,
            "area_coverage_stable": cob_estable,
        }

    # Evaluar las 4 tendencias juntas con OLS + HAC (Newey-West) y ajuste de Holm (§03 y §03.1)
    resultados_holm = evaluar_cuatro_tendencias_holm(series_anuales_tuplas, alfa=alfa)
    tramo = next((resultados_holm[c].get("tramo_comun") for c in ORDEN_FAMILIA_DTE
                  if resultados_holm[c].get("tramo_comun")), None)
    if tramo is None:
        advertencias_globales.append("No hay ningún año completo común a las variables evaluables: sin tendencias.")
    else:
        n_tramo = tramo[1] - tramo[0] + 1
        if n_tramo < n_anios_esperados:
            advertencias_globales.append(
                f"Tendencias calculadas en el tramo común {tramo[0]}–{tramo[1]} ({n_tramo} de {n_anios_esperados} "
                "años): hay años incompletos fuera de él. Los huecos no se comprimen ni se rellenan."
            )
        if n_tramo < ANIOS_ADVERTENCIA_DTE:
            advertencias_globales.append(
                f"Solo {n_tramo} años en el tramo: la inferencia HAC es frágil con tan pocos datos."
            )
    for cod in ORDEN_FAMILIA_DTE:
        if resultados_holm[cod].get("sensible_al_rezago"):
            advertencias_globales.append(
                f"{cod}: la decisión cambia con el rezago 2 o 3 → resultado sensible al rezago (el rezago 1 sigue "
                "siendo el principal)."
            )

    # Construir salida de variables[P, T, SM, ET] (§05)
    variables_out: dict[str, dict[str, Any]] = {}
    for cod in ORDEN_FAMILIA_DTE:
        info = INFO_VARIABLES_DTE[cod]
        da_m = reind_mensual[cod]
        da_z = series_z[cod]
        da_a = series_anuales_da[cod]
        est = resultados_holm[cod]

        fechas_m = pd.DatetimeIndex(da_m["time"].values)
        lista_mensual = [
            {
                "date": f.strftime("%Y-%m"),
                "value": _limpiar_num(v),
                "z": _limpiar_num(z_val),
            }
            for f, v, z_val in zip(fechas_m, da_m.values, da_z.values)
        ]

        mapa_ajustados = dict(zip(est.get("anios_usados") or [], est.get("ajustados") or []))
        lista_anual = [
            {
                "year": int(a),
                "value": _limpiar_num(v),
                "fitted": _limpiar_num(mapa_ajustados.get(int(a))),
            }
            for a, v in zip(da_a["anio"].values, da_a.values)
        ]

        variables_out[cod] = {
            "id": info["id"],
            "code": cod,
            "name": info["nombre"],
            "question": info["pregunta"],
            "why_chosen": info["por_que_elegirla"],
            "collection": info["coleccion"],
            "short_name": info["short_name"],
            "field": info["campo"],
            "conversion_rule": info["conversion_texto"],
            "annual_aggregation": info["agregacion_anual"],
            "units": {
                "monthly": info["unidad_mensual"],
                "annual": info["unidad_anual"],
                "slope_decade": info["unidad_decada"],
            },
            "monthly": lista_mensual,
            "annual": lista_anual,
            "intercept_a": est.get("intercept_a"),
            "slope_annual": est.get("slope_annual"),
            "se_annual": est.get("se_annual"),
            "z_stat": est.get("z_stat"),
            "slope_decade": est.get("slope_decade"),
            "ci95": est.get("ci95"),
            "p_raw": est.get("p_raw"),
            "p_holm": est.get("p_holm"),
            "significant": est.get("significant"),
            "direction": est.get("direction"),
            "estimate_sign": est.get("estimate_sign"),
            "label": est.get("label"),
            "summary_text": est.get("summary_text"),
            "sensible_al_rezago": est.get("sensible_al_rezago"),
            "sensitivity": est.get("sensibilidad_rezagos"),
            "quality": {
                **calidad_por_cod[cod],
                "warnings": est.get("advertencias", []),
            },
        }

    # Construir análisis conjunto (§04 y §05): anomalías estandarizadas z y 3 pares prioritarios
    fechas_comunes = pd.DatetimeIndex(calendario)
    anomalias_z_tabla = [
        {
            "date": f.strftime("%Y-%m"),
            "P": _limpiar_num(series_z["P"].values[i]),
            "T": _limpiar_num(series_z["T"].values[i]),
            "SM": _limpiar_num(series_z["SM"].values[i]),
            "ET": _limpiar_num(series_z["ET"].values[i]),
        }
        for i, f in enumerate(fechas_comunes)
    ]

    pares_lista: list[dict[str, Any]] = []
    pares_mapa: dict[str, dict[str, Any]] = {}
    for spec_par in PARES_PRIORITARIOS_DTE:
        par_id = spec_par["pair"]
        vx = spec_par["var_x"]
        vy = spec_par["var_y"]
        corr = correlacion_exploratoria_sin_tendencia(series_z[vx], series_z[vy])
        r_val = corr["r"]
        n_val = corr["n"]
        if r_val is None:
            sentido_txt = "sin variación suficiente para calcular asociación"
            texto_par = f"{vx} y {vy}: no se pudo calcular asociación mensual (n = {n_val} meses)."
        else:
            if abs(r_val) < 0.15:
                sentido_txt = "poca asociación lineal en el mismo mes"
            elif r_val > 0:
                sentido_txt = "variación conjunta en el mismo sentido"
            else:
                sentido_txt = "variación conjunta en sentido opuesto"
            # Plantilla oficial (§03.2 y §04)
            texto_par = (
                f"{vx} y {vy} mostraron asociación mensual r = {r_val:+.2f}, con {n_val} meses, "
                f"tras quitar estación y tendencia ({sentido_txt}). Es exploratorio: describe relación, no causa."
            )
        item_par = {
            "pair": par_id,
            "var_x": vx,
            "var_y": vy,
            "question": spec_par["pregunta"],
            "interpretation_note": spec_par["cuidado"],
            "r": r_val,
            "n": n_val,
            "common_period": corr["periodo_comun"],
            "direction_description": sentido_txt,
            "summary_text": texto_par,
        }
        pares_lista.append(item_par)
        pares_mapa[par_id] = item_par

    # Construir conclusión integradora (§05 Vista Conclusión)
    con_evidencia = [
        variables_out[c]["summary_text"]
        for c in ORDEN_FAMILIA_DTE
        if variables_out[c]["significant"] is True
    ]
    no_concluyentes = [
        variables_out[c]["summary_text"]
        for c in ORDEN_FAMILIA_DTE
        if variables_out[c]["significant"] is not True
    ]
    lectura_conjunta = _redactar_lectura_conjunta(variables_out, pares_lista)

    anios_completos_comunes = int(
        min(calidad_por_cod[c]["n_years_complete"] for c in ORDEN_FAMILIA_DTE)
    )

    return {
        "metadata": {
            "project": "Down to Earth — Cuatro variables, dos formas de analizarlas",
            "region": region_meta,
            "period": [inicio, fin],
            "months_total": n_meses_esperados,
            "years_expected": n_anios_esperados,
            "years_complete_count": anios_completos_comunes,
            "trend_span": (
                {
                    "start": int(tramo[0]),
                    "end": int(tramo[1]),
                    "n_years": int(tramo[1] - tramo[0] + 1),
                    "criterion": "tramo común más largo de años completos y consecutivos (empate → el más reciente)",
                }
                if tramo
                else None
            ),
            "simulated": simulado,
            "warnings": advertencias_globales,
            "spatial_weighting": ponderacion_txt,
            "alpha": float(alfa),
            "method": {
                "ols_formula": "y = a + b * t, donde t = anio - anio_inicial",
                "cov_type": "HAC",
                "cov_kwds": {"maxlags": 1, "kernel": "bartlett", "use_correction": True},
                "use_t": False,
                "multiple_testing": "holm",
                "family": list(ORDEN_FAMILIA_DTE),
                "sensitivity_lags": [1, 2, 3],
            },
            "source": fuente_datos,
            "almacenamiento_disco": False,
        },
        "variables": variables_out,
        "data_cleaning": {
            "steps": [
                "valores a float64 y fechas normalizadas al primer día del mes",
                "fechas duplicadas: valor idéntico → se conserva uno; valores distintos → faltante",
                "±inf → faltante",
                "relleno (≤ −999 o |x| ≥ 1e15) → faltante; nunca 0 ni interpolación",
                "fuera de límites físicos (unidades finales) → faltante",
                "calendario mensual completo: meses ausentes → faltante",
                "ceros exactos en P, SM y ET: se conservan y se advierten",
            ],
            "summary": limpieza.resumen,
            "log": [*_registro_json(registro_entrada or []), *limpieza.registro_lista()],
        },
        "joint": {
            "preprocessing": {
                "seasonal_removal": (
                    f"Promedio μ_mes y desviación estándar s_mes calculados por mes calendario en {inicio} a {fin}."
                ),
                "standardization": "z = (valor - μ_mes) / s_mes (escala adimensional comparable entre P, T, SM y ET).",
                "detrending_for_correlation": (
                    "Para las correlaciones r se elimina por regresión OLS la tendencia lineal de cada serie z "
                    "usando el tiempo real. El gráfico de líneas z conserva las tendencias; las correlaciones r las eliminan."
                ),
                "note": "Estas correlaciones son exploratorias: no se les asigna p-valor ni etiqueta de significancia.",
            },
            "standardized_anomalies": anomalias_z_tabla,
            "pairs": pares_mapa,
            "pairs_list": pares_lista,
        },
        "conclusion": {
            "joint_reading": lectura_conjunta,
            "changes_with_statistical_evidence": con_evidencia,
            "inconclusive_or_insufficient_evidence": no_concluyentes,
            "exploratory_associations": [p["summary_text"] for p in pares_lista],
            "methodological_limits": [
                "La coincidencia temporal o correlación entre P, T, SM y ET describe relaciones, no demuestra causalidad.",
                "SM representa únicamente los primeros 0–10 cm del suelo, no toda la zona de raíces.",
                "ET de GLDAS es evapotranspiración real, no potencial (no usarla como PET para SPEI).",
                "SM y ET de GLDAS comparten modelo terrestre Noah y forzamientos: no son pruebas totalmente independientes.",
                "No restar P (GPCP) y ET (GLDAS) como balance hídrico cerrado: provienen de fuentes distintas y faltan escorrentía y almacenamiento.",
                "El IC95 % refleja la incertidumbre de la pendiente lineal (OLS + HAC), no la incertidumbre estructural del satélite o del modelo.",
            ],
        },
    }


def _registro_json(registro: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normaliza entradas de registro (valor_original NaN → None) para la respuesta JSON."""
    out = []
    for e in registro:
        v = e.get("valor_original")
        out.append({
            "fecha": e.get("fecha"),
            "variable": e.get("variable"),
            "valor_original": None if v is None or not np.isfinite(float(v)) else float(v),
            "accion": e.get("accion"),
            "motivo": e.get("motivo"),
        })
    return out


def _redactar_lectura_conjunta(
    variables_out: dict[str, dict[str, Any]],
    pares_lista: list[dict[str, Any]],
) -> str:
    """Genera el párrafo de lectura conjunta respaldado estrictamente por los resultados (§00 y §05)."""
    frases_sig: list[str] = []
    verbos = {
        "P": ("aumentó la precipitación", "disminuyó la precipitación"),
        "T": ("aumentó la temperatura del aire", "disminuyó la temperatura del aire"),
        "SM": ("aumentó la humedad superficial del suelo", "bajó la humedad superficial del suelo"),
        "ET": ("aumentó la evapotranspiración real", "disminuyó la evapotranspiración real"),
    }
    for cod in ORDEN_FAMILIA_DTE:
        v = variables_out[cod]
        if v.get("significant") is True and v.get("slope_decade") is not None:
            sube, baja = verbos[cod]
            accion = sube if v["slope_decade"] > 0 else baja
            frases_sig.append(f"{accion} ({v['slope_decade']:+.3g} {v['units']['slope_decade']}, p_Holm={v['p_holm']:.3f})")

    insuf = [
        f"{cod} ({variables_out[cod]['slope_decade']:+.3g} {variables_out[cod]['units']['slope_decade']}, "
        f"{variables_out[cod]['label']})"
        for cod in ORDEN_FAMILIA_DTE
        if variables_out[cod].get("significant") is False and variables_out[cod].get("slope_decade") is not None
    ]

    partes: list[str] = []
    if frases_sig:
        partes.append("En el período analizado, con evidencia estadística tras el ajuste de Holm: " + "; ".join(frases_sig) + ".")
    else:
        partes.append("En el período analizado ninguna de las cuatro variables superó el umbral α = 0.05 tras el ajuste de Holm.")

    if insuf:
        partes.append("Variables con evidencia estadística insuficiente (lo cual no implica ausencia de cambio): " + "; ".join(insuf) + ".")

    resumen_pares = [f"{p['pair']} (r={p['r']:+.2f}, n={p['n']})" for p in pares_lista if p.get("r") is not None]
    if resumen_pares:
        partes.append(
            "Asociaciones mensuales exploratorias (tras quitar estación y tendencia lineal): "
            + ", ".join(resumen_pares)
            + ". Estas coincidencias describen relación, sin demostrar causalidad."
        )
    return " ".join(partes)


def generar_csv_mensual_dte(resultado_dte: dict[str, Any]) -> str:
    """Genera el contenido CSV de las cuatro series mensuales alineadas (`fecha,P,T,SM,ET`) en memoria (§02)."""
    vars_d = resultado_dte["variables"]
    n = len(vars_d["P"]["monthly"])
    lineas = ["fecha,P_mm_mes,T_degC,SM_m3_m3,ET_mm_mes"]
    for i in range(n):
        fecha = vars_d["P"]["monthly"][i]["date"]
        vals = [
            "" if vars_d[c]["monthly"][i]["value"] is None else f"{vars_d[c]['monthly'][i]['value']:.6g}"
            for c in ORDEN_FAMILIA_DTE
        ]
        lineas.append(f"{fecha},{','.join(vals)}")
    return "\n".join(lineas) + "\n"


def generar_csv_anual_dte(resultado_dte: dict[str, Any]) -> str:
    """Genera el contenido CSV de las cuatro series anuales (`anio,P,T,SM,ET`) en memoria (§02)."""
    vars_d = resultado_dte["variables"]
    n = len(vars_d["P"]["annual"])
    lineas = ["anio,P_mm_anio,T_degC,SM_m3_m3,ET_mm_anio"]
    for i in range(n):
        anio = vars_d["P"]["annual"][i]["year"]
        vals = [
            "" if vars_d[c]["annual"][i]["value"] is None else f"{vars_d[c]['annual'][i]['value']:.6g}"
            for c in ORDEN_FAMILIA_DTE
        ]
        lineas.append(f"{anio},{','.join(vals)}")
    return "\n".join(lineas) + "\n"
