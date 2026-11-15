"""Análisis de tendencias y relaciones entre P, T, SM y ET (CSV mensual simulado DtE).

Uso:
    python analisis.py <ruta_csv> <carpeta_salida>

Métodos
- Serie mensual -> climatología 2001-2024 -> anomalías mensuales (quita el ciclo estacional).
- Tendencia: MCO sobre anomalías con corrección por autocorrelación AR(1)
  (n_ef = n (1-r1)/(1+r1)), prueba t con n_ef-2 gl, IC 95 %.
  Contraste no paramétrico: Mann-Kendall modificado (Hamed & Rao 1998) + pendiente de Sen.
- Serie anual (P y ET suma, T y SM media): mismas pruebas.
- Relaciones: Pearson y Spearman entre anomalías mensuales (originales y sin tendencia),
  significancia con n efectivo de Bretherton et al. (1999); correlaciones cruzadas con
  desfase (0-3 meses); correlación entre series anuales; balance P-ET.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

VARS = {
    "P": {"nombre": "Precipitación", "unidad": "mm/mes", "unidad_anual": "mm/año", "agg": "sum"},
    "T": {"nombre": "Temperatura", "unidad": "°C", "unidad_anual": "°C", "agg": "mean"},
    "SM": {"nombre": "Humedad del suelo", "unidad": "m³/m³", "unidad_anual": "m³/m³", "agg": "mean"},
    "ET": {"nombre": "Evapotranspiración", "unidad": "mm/mes", "unidad_anual": "mm/año", "agg": "sum"},
}
ALPHA = 0.05


# ----------------------------------------------------------------------------- utilidades
def lag1(x: np.ndarray) -> float:
    x = np.asarray(x, float) - np.mean(x)
    return float(np.sum(x[1:] * x[:-1]) / np.sum(x * x))


def tendencia_mco(t: np.ndarray, y: np.ndarray) -> dict:
    """MCO con corrección del n efectivo por la autocorrelación AR(1) de los residuos."""
    n = len(y)
    res = stats.linregress(t, y)
    resid = y - (res.intercept + res.slope * t)
    r1 = lag1(resid)
    r1c = max(r1, 0.0)
    n_ef = n * (1 - r1c) / (1 + r1c)
    n_ef = float(min(max(n_ef, 3.0), n))
    s2 = np.sum(resid**2) / (n_ef - 2)
    se = float(np.sqrt(s2 / np.sum((t - t.mean()) ** 2)))
    gl = n_ef - 2
    tstat = res.slope / se
    p = float(2 * stats.t.sf(abs(tstat), gl))
    tc = stats.t.ppf(1 - ALPHA / 2, gl)
    return {
        "pendiente": float(res.slope),
        "ee": se,
        "ic95": [float(res.slope - tc * se), float(res.slope + tc * se)],
        "t": float(tstat),
        "p": p,
        "r2": float(res.rvalue**2),
        "r1_residuos": float(r1),
        "n": int(n),
        "n_efectivo": n_ef,
        "intercepto": float(res.intercept),
        "sigma_residuos": float(np.std(resid, ddof=2)),
    }


def mann_kendall_hr(y: np.ndarray) -> dict:
    """Mann-Kendall modificado de Hamed & Rao (1998) + pendiente de Sen."""
    y = np.asarray(y, float)
    n = len(y)
    i, j = np.triu_indices(n, 1)
    diffs = y[j] - y[i]
    s = float(np.sum(np.sign(diffs)))
    # varianza con empates
    _, cnt = np.unique(y, return_counts=True)
    var_s = (n * (n - 1) * (2 * n + 5) - np.sum(cnt * (cnt - 1) * (2 * cnt + 5))) / 18.0
    # Sen
    slopes = diffs / (j - i)
    sen = float(np.median(slopes))
    # Hamed-Rao: autocorrelación de rangos de la serie sin tendencia de Sen
    det = y - sen * np.arange(n)
    rk = stats.rankdata(det)
    rk = rk - rk.mean()
    denom = np.sum(rk * rk)
    z_crit = stats.norm.ppf(1 - ALPHA / 2)
    corr = 0.0
    for k in range(1, n):
        rho = np.sum(rk[k:] * rk[:-k]) / denom
        if abs(rho) > z_crit / np.sqrt(n):  # solo lags significativos
            corr += (n - k) * (n - k - 1) * (n - k - 2) * rho
    factor = 1 + 2 * corr / (n * (n - 1) * (n - 2))
    factor = max(factor, 1e-6)
    var_mod = var_s * factor
    if s > 0:
        z = (s - 1) / np.sqrt(var_mod)
    elif s < 0:
        z = (s + 1) / np.sqrt(var_mod)
    else:
        z = 0.0
    p = float(2 * stats.norm.sf(abs(z)))
    tau = s / (0.5 * n * (n - 1))
    # IC 95 % de Sen (Gilbert 1987) con varianza modificada
    m = len(slopes)
    c = z_crit * np.sqrt(var_mod)
    lo = int(np.floor((m - c) / 2))
    hi = int(np.ceil((m + c) / 2))
    ss = np.sort(slopes)
    lo = min(max(lo, 0), m - 1)
    hi = min(max(hi, 0), m - 1)
    return {
        "S": s,
        "tau": float(tau),
        "z": float(z),
        "p": p,
        "factor_hamed_rao": float(factor),
        "sen": sen,
        "sen_ic95": [float(ss[lo]), float(ss[hi])],
    }


def veredicto(p_mco: float, p_mk: float, signo_mco: float, signo_mk: float) -> str:
    sig_mco, sig_mk = p_mco < ALPHA, p_mk < ALPHA
    if sig_mco and sig_mk and np.sign(signo_mco) == np.sign(signo_mk):
        return "significativa"
    if sig_mco or sig_mk or min(p_mco, p_mk) < 0.10:
        return "indicio (no concluyente)"
    return "no significativa"


def n_ef_bretherton(x: np.ndarray, y: np.ndarray) -> float:
    n = len(x)
    r1x, r1y = lag1(x), lag1(y)
    f = (1 - r1x * r1y) / (1 + r1x * r1y)
    return float(min(max(n * f, 3.0), n))


def corr_sig(x: np.ndarray, y: np.ndarray) -> dict:
    r, _ = stats.pearsonr(x, y)
    rho, _ = stats.spearmanr(x, y)
    n_ef = n_ef_bretherton(x, y)
    gl = n_ef - 2
    tstat = r * np.sqrt(gl / max(1 - r * r, 1e-12))
    p = float(2 * stats.t.sf(abs(tstat), gl))
    # IC 95 % por Fisher con n efectivo
    zf = np.arctanh(r)
    se = 1 / np.sqrt(max(n_ef - 3, 1))
    ic = [float(np.tanh(zf - 1.96 * se)), float(np.tanh(zf + 1.96 * se))]
    tsp = rho * np.sqrt(gl / max(1 - rho * rho, 1e-12))
    p_sp = float(2 * stats.t.sf(abs(tsp), gl))
    return {
        "pearson_r": float(r),
        "pearson_ic95": ic,
        "pearson_p_ajustado": p,
        "spearman_rho": float(rho),
        "spearman_p_ajustado": p_sp,
        "n": int(len(x)),
        "n_efectivo": n_ef,
        "significativa": bool(p < ALPHA),
    }


def fuerza(r: float) -> str:
    a = abs(r)
    if a >= 0.7:
        f = "fuerte"
    elif a >= 0.4:
        f = "moderada"
    elif a >= 0.2:
        f = "débil"
    else:
        f = "muy débil / nula"
    return f + (" positiva" if r > 0 else " negativa") if a >= 0.2 else f


# ----------------------------------------------------------------------------- análisis
def main(csv: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(csv)
    df["fecha"] = pd.to_datetime(df["fecha"], format="%Y-%m")
    df = df.sort_values("fecha").set_index("fecha")
    vars_ = list(VARS)

    # --- control de calidad
    idx_completo = pd.date_range(df.index.min(), df.index.max(), freq="MS")
    calidad = {
        "n_meses": int(len(df)),
        "periodo": [df.index.min().strftime("%Y-%m"), df.index.max().strftime("%Y-%m")],
        "meses_faltantes_en_calendario": int(len(idx_completo.difference(df.index))),
        "nulos_por_variable": {v: int(df[v].isna().sum()) for v in vars_},
        "duplicados": int(df.index.duplicated().sum()),
        "rangos": {v: [float(df[v].min()), float(df[v].max())] for v in vars_},
        "chequeo_plausibilidad": {
            "P_no_negativa": bool((df["P"] >= 0).all()),
            "ET_no_negativa": bool((df["ET"] >= 0).all()),
            "SM_entre_0_y_0.6": bool(df["SM"].between(0, 0.6).all()),
            "T_entre_-60_y_60": bool(df["T"].between(-60, 60).all()),
        },
    }

    # --- climatología y anomalías mensuales
    mes = df.index.month
    clim = df.groupby(mes)[vars_].mean()
    anom = df[vars_] - clim.loc[mes].values
    t_dec = (np.arange(len(df)) / 120.0)  # tiempo en décadas

    # --- serie anual
    agg = {v: VARS[v]["agg"] for v in vars_}
    anual = df[vars_].resample("YS").agg(agg)
    anual.index = anual.index.year
    anual.index.name = "anio"
    anual["P_menos_ET"] = anual["P"] - anual["ET"]
    conteo = df[vars_].resample("YS").count()
    conteo.index = anual.index
    anual["meses_validos"] = conteo.min(axis=1).astype(int)
    anual.round(4).to_csv(out / "serie_anual.csv", encoding="utf-8")
    t_anual_dec = (anual.index.values - anual.index.values[0]) / 10.0

    resultados_tend = {}
    for v in vars_ + ["P_menos_ET"]:
        info = VARS.get(v, {"nombre": "Balance P − ET", "unidad": "mm/mes", "unidad_anual": "mm/año"})
        if v == "P_menos_ET":
            serie_m = anom["P"] - anom["ET"]
            media_m = float((df["P"] - df["ET"]).mean())
        else:
            serie_m = anom[v]
            media_m = float(df[v].mean())
        mco_m = tendencia_mco(t_dec, serie_m.values)
        mk_m = mann_kendall_hr(serie_m.values)
        # pendiente de Sen está por paso (mes) -> por década
        mk_m["sen_por_decada"] = mk_m["sen"] * 120
        mk_m["sen_ic95_por_decada"] = [x * 120 for x in mk_m["sen_ic95"]]

        ya = anual[v].values
        mco_a = tendencia_mco(t_anual_dec, ya)
        mk_a = mann_kendall_hr(ya)
        mk_a["sen_por_decada"] = mk_a["sen"] * 10
        mk_a["sen_ic95_por_decada"] = [x * 10 for x in mk_a["sen_ic95"]]

        media_a = float(np.mean(ya))
        anios = len(ya)
        cambio_total_a = mco_a["pendiente"] * (anios - 1) / 10.0
        cambio_pct = (100 * cambio_total_a / abs(media_a)) if v != "P_menos_ET" and media_a != 0 else None
        # años necesarios para detectar (Weatherhead et al. 1998) con la serie mensual
        sig_n = mco_m["sigma_residuos"]
        phi = max(mco_m["r1_residuos"], 0)
        w_dec = abs(mco_m["pendiente"])  # unidades por década
        w_anio = w_dec / 10.0
        n_det = ((3.3 * sig_n / w_anio) * np.sqrt((1 + phi) / (1 - phi))) ** (2 / 3) if w_anio > 0 else None
        snr = mco_m["pendiente"] / mco_m["ee"] if mco_m["ee"] > 0 else None

        resultados_tend[v] = {
            "nombre": info["nombre"],
            "unidad_mensual": info["unidad"],
            "unidad_anual": info["unidad_anual"],
            "media_mensual": media_m,
            "media_anual": media_a,
            "mensual_anomalias": {
                "mco": mco_m,
                "mco_unidad_pendiente": f"{info['unidad']} por década",
                "mann_kendall_hamed_rao": mk_m,
                "veredicto": veredicto(mco_m["p"], mk_m["p"], mco_m["pendiente"], mk_m["sen"]),
                "snr_pendiente_sobre_ee": snr,
                "anios_para_detectar_weatherhead": float(n_det) if n_det is not None else None,
            },
            "anual": {
                "mco": mco_a,
                "mco_unidad_pendiente": f"{info['unidad_anual']} por década",
                "mann_kendall_hamed_rao": mk_a,
                "veredicto": veredicto(mco_a["p"], mk_a["p"], mco_a["pendiente"], mk_a["sen"]),
                "cambio_total_periodo": float(cambio_total_a),
                "cambio_pct_respecto_media": float(cambio_pct) if cambio_pct is not None else None,
            },
        }

    # --- relaciones
    pares = [(a, b) for i, a in enumerate(vars_) for b in vars_[i + 1:]]
    anom_dt = anom.copy()
    for v in vars_:
        b = np.polyfit(t_dec, anom[v].values, 1)
        anom_dt[v] = anom[v].values - np.polyval(b, t_dec)
    rel = {"mensual_anomalias": {}, "mensual_anomalias_sin_tendencia": {}, "anual": {},
           "valores_brutos_con_estacionalidad": {}, "desfases": {}}
    for a, b in pares:
        k = f"{a}-{b}"
        rel["mensual_anomalias"][k] = corr_sig(anom[a].values, anom[b].values)
        rel["mensual_anomalias"][k]["descripcion"] = fuerza(rel["mensual_anomalias"][k]["pearson_r"])
        rel["mensual_anomalias_sin_tendencia"][k] = corr_sig(anom_dt[a].values, anom_dt[b].values)
        rel["anual"][k] = corr_sig(anual[a].values, anual[b].values)
        r_raw = stats.pearsonr(df[a].values, df[b].values)[0]
        rel["valores_brutos_con_estacionalidad"][k] = {
            "pearson_r": float(r_raw),
            "nota": "incluye el ciclo estacional; no usar para inferencia",
        }
    # desfases: la variable 'causa' adelanta a la 'respuesta'
    lag_pares = [("P", "SM"), ("P", "ET"), ("SM", "ET"), ("T", "SM"), ("T", "ET"), ("T", "P")]
    for a, b in lag_pares:
        lst = []
        for lag in range(0, 4):
            x = anom[a].values[: len(anom) - lag] if lag else anom[a].values
            y = anom[b].values[lag:]
            c = corr_sig(x, y)
            lst.append({"desfase_meses": lag, "pearson_r": c["pearson_r"],
                        "p_ajustado": c["pearson_p_ajustado"], "significativa": c["significativa"]})
        best = max(lst, key=lambda d: abs(d["pearson_r"]))
        rel["desfases"][f"{a}->{b}"] = {"por_desfase": lst, "desfase_optimo_meses": best["desfase_meses"],
                                         "r_optimo": best["pearson_r"]}
    # regresión múltiple: anomalías de SM explicadas por P y T
    import statsmodels.api as sm
    def ols_hac(yv: str, xs: list[str]) -> dict:
        X = sm.add_constant(anom[xs])
        m = sm.OLS(anom[yv], X).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
        return {
            "y": yv, "x": xs, "r2": float(m.rsquared),
            "coeficientes": {c: {"beta": float(m.params[c]), "p_hac": float(m.pvalues[c])} for c in xs},
            "coef_estandarizados": {c: float(m.params[c] * anom[c].std() / anom[yv].std()) for c in xs},
        }
    rel["regresiones_multiples_anomalias"] = {
        "SM~P+T": ols_hac("SM", ["P", "T"]),
        "ET~P+T+SM": ols_hac("ET", ["P", "T", "SM"]),
    }
    # balance
    bal = {
        "P_media_anual_mm": float(anual["P"].mean()),
        "ET_media_anual_mm": float(anual["ET"].mean()),
        "ET_sobre_P": float(anual["ET"].mean() / anual["P"].mean()),
        "anios_con_ET_mayor_que_P": [int(y) for y in anual.index[anual["P_menos_ET"] < 0]],
        "meses_climatologicos_con_ET_mayor_que_P": [int(m) for m in clim.index[clim["ET"] > clim["P"]]],
    }

    clim_out = clim.copy()
    clim_out.index.name = "mes"
    clim_out.round(4).to_csv(out / "climatologia_mensual.csv", encoding="utf-8")

    resultados = {
        "metadatos": {
            "fuente": str(csv.name),
            "nota": "Datos SIMULADOS para probar el flujo; no interpretar como clima real.",
            "variables": {v: {"nombre": VARS[v]["nombre"], "unidad": VARS[v]["unidad"],
                              "agregacion_anual": "suma" if VARS[v]["agg"] == "sum" else "media"} for v in vars_},
            "metodos": {
                "anomalias": "valor mensual − climatología del mes (2001-2024)",
                "tendencia_parametrica": "MCO sobre anomalías; ee corregido con n_ef = n(1−r1)/(1+r1) (AR(1) de residuos); t con n_ef−2 gl",
                "tendencia_no_parametrica": "Mann-Kendall modificado Hamed-Rao (1998) + pendiente de Sen (IC Gilbert)",
                "veredicto": "significativa si MCO y MK tienen p<0.05 con el mismo signo; indicio si solo una o p<0.10",
                "correlaciones": "Pearson/Spearman; p con n efectivo de Bretherton et al. (1999)",
                "anios_para_detectar": "Weatherhead et al. (1998): n*=[(3.3σ/|ω|)·√((1+φ)/(1−φ))]^(2/3)",
                "alpha": ALPHA,
            },
        },
        "calidad_datos": calidad,
        "climatologia_mensual": {v: {int(m): float(clim.loc[m, v]) for m in clim.index} for v in vars_},
        "tendencias": resultados_tend,
        "relaciones": rel,
        "balance_hidrico": bal,
    }
    with open(out / "resultados.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    graficas(df, anom, anual, clim, resultados_tend, rel, out)
    print(json.dumps({v: {"mensual": resultados_tend[v]["mensual_anomalias"]["veredicto"],
                          "anual": resultados_tend[v]["anual"]["veredicto"]} for v in resultados_tend},
                     ensure_ascii=False, indent=1))


# ----------------------------------------------------------------------------- gráficas
COL = {"P": "#2a6fdb", "T": "#d1495b", "SM": "#8c6d1f", "ET": "#2e9e6a", "P_menos_ET": "#6a4c93"}
LAYOUT = dict(template="plotly_white", font=dict(family="Inter, Segoe UI, sans-serif", size=13))


def _save(fig: go.Figure, path: Path) -> None:
    fig.write_html(path, include_plotlyjs="cdn", full_html=True)


def graficas(df, anom, anual, clim, tend, rel, out: Path) -> None:
    g = out / "graficas"
    g.mkdir(exist_ok=True)
    vars_ = list(VARS)

    # 1. series mensuales
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        subplot_titles=[f"{VARS[v]['nombre']} ({VARS[v]['unidad']})" for v in vars_])
    for i, v in enumerate(vars_, 1):
        fig.add_trace(go.Scatter(x=df.index, y=df[v], mode="lines", line=dict(color=COL[v], width=1.2),
                                 name=v, showlegend=False), row=i, col=1)
    fig.update_layout(title="Series mensuales 2001-2024 (datos simulados)", height=900, **LAYOUT)
    _save(fig, g / "01_series_mensuales.html")

    # 2. anomalías con tendencia
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                        subplot_titles=[
                            f"{VARS[v]['nombre']}: {tend[v]['mensual_anomalias']['mco']['pendiente']:+.3g} "
                            f"{VARS[v]['unidad']}/década (p={tend[v]['mensual_anomalias']['mco']['p']:.3f}) — "
                            f"{tend[v]['mensual_anomalias']['veredicto']}" for v in vars_])
    t_dec = np.arange(len(df)) / 120.0
    for i, v in enumerate(vars_, 1):
        m = tend[v]["mensual_anomalias"]["mco"]
        fig.add_trace(go.Bar(x=df.index, y=anom[v], marker_color=np.where(anom[v] >= 0, COL[v], "#9aa0a6"),
                             name=v, showlegend=False, opacity=0.75), row=i, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=m["intercepto"] + m["pendiente"] * t_dec, mode="lines",
                                 line=dict(color="black", width=2), showlegend=False), row=i, col=1)
    fig.update_layout(title="Anomalías mensuales (sin ciclo estacional) y tendencia MCO", height=1000,
                      bargap=0, **LAYOUT)
    _save(fig, g / "02_anomalias_tendencia.html")

    # 3. series anuales con tendencia y Sen
    fig = make_subplots(rows=2, cols=2, vertical_spacing=0.14, horizontal_spacing=0.08,
                        subplot_titles=[
                            f"{VARS[v]['nombre']} ({VARS[v]['unidad_anual']}) — {tend[v]['anual']['veredicto']}"
                            for v in vars_])
    x = anual.index.values
    td = (x - x[0]) / 10.0
    for k, v in enumerate(vars_):
        r, c = k // 2 + 1, k % 2 + 1
        a = tend[v]["anual"]
        fig.add_trace(go.Scatter(x=x, y=anual[v], mode="lines+markers", line=dict(color=COL[v]),
                                 name=v, showlegend=False), row=r, col=c)
        fig.add_trace(go.Scatter(x=x, y=a["mco"]["intercepto"] + a["mco"]["pendiente"] * td, mode="lines",
                                 line=dict(color="black", dash="solid"), name="MCO",
                                 showlegend=(k == 0)), row=r, col=c)
        sen = a["mann_kendall_hamed_rao"]["sen"]
        yv = anual[v].values
        b0 = np.median(yv - sen * np.arange(len(yv)))
        fig.add_trace(go.Scatter(x=x, y=b0 + sen * np.arange(len(yv)), mode="lines",
                                 line=dict(color="gray", dash="dash"), name="Sen",
                                 showlegend=(k == 0)), row=r, col=c)
    fig.update_layout(title="Series anuales (P y ET: suma; T y SM: media) con tendencia", height=750,
                      **LAYOUT)
    _save(fig, g / "03_series_anuales.html")

    # 4. climatología
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    fig.add_trace(go.Bar(x=meses, y=clim["P"], name="P (mm/mes)", marker_color=COL["P"]))
    fig.add_trace(go.Scatter(x=meses, y=clim["ET"], name="ET (mm/mes)", line=dict(color=COL["ET"], width=3)))
    fig.add_trace(go.Scatter(x=meses, y=clim["T"], name="T (°C)", line=dict(color=COL["T"], dash="dot")),
                  secondary_y=True)
    fig.update_yaxes(title_text="mm/mes", secondary_y=False)
    fig.update_yaxes(title_text="°C", secondary_y=True)
    fig.update_layout(title="Climatología mensual 2001-2024", height=500, **LAYOUT)
    _save(fig, g / "04_climatologia.html")

    # 5. matriz de correlación (anomalías mensuales)
    m = np.eye(4)
    txt = [["" for _ in vars_] for _ in vars_]
    for i, a in enumerate(vars_):
        for j, b in enumerate(vars_):
            if i == j:
                txt[i][j] = "1"
                continue
            k = f"{a}-{b}" if f"{a}-{b}" in rel["mensual_anomalias"] else f"{b}-{a}"
            d = rel["mensual_anomalias"][k]
            m[i, j] = d["pearson_r"]
            txt[i][j] = f"{d['pearson_r']:.2f}{'*' if d['significativa'] else ''}"
    fig = go.Figure(go.Heatmap(z=m, x=vars_, y=vars_, text=txt, texttemplate="%{text}", zmin=-1, zmax=1,
                               colorscale="RdBu", reversescale=False, colorbar=dict(title="r")))
    fig.update_layout(title="Correlación de Pearson entre anomalías mensuales (* p<0.05 con n efectivo)",
                      height=520, width=620, yaxis=dict(autorange="reversed"), **LAYOUT)
    _save(fig, g / "05_matriz_correlacion.html")

    # 6. dispersión de pares clave
    pares = [("P", "SM"), ("P", "ET"), ("T", "SM"), ("SM", "ET"), ("T", "ET"), ("T", "P")]
    fig = make_subplots(rows=2, cols=3, horizontal_spacing=0.08, vertical_spacing=0.16,
                        subplot_titles=[
                            f"{a} vs {b}: r={rel['mensual_anomalias'].get(f'{a}-{b}', rel['mensual_anomalias'].get(f'{b}-{a}'))['pearson_r']:.2f}"
                            for a, b in pares])
    for k, (a, b) in enumerate(pares):
        r, c = k // 3 + 1, k % 3 + 1
        fig.add_trace(go.Scatter(x=anom[a], y=anom[b], mode="markers",
                                 marker=dict(size=5, color=COL[b], opacity=0.55), showlegend=False),
                      row=r, col=c)
        bb = np.polyfit(anom[a], anom[b], 1)
        xs = np.linspace(anom[a].min(), anom[a].max(), 10)
        fig.add_trace(go.Scatter(x=xs, y=np.polyval(bb, xs), mode="lines", line=dict(color="black"),
                                 showlegend=False), row=r, col=c)
        fig.update_xaxes(title_text=f"anom. {a}", row=r, col=c)
        fig.update_yaxes(title_text=f"anom. {b}", row=r, col=c)
    fig.update_layout(title="Relaciones entre anomalías mensuales", height=750, **LAYOUT)
    _save(fig, g / "06_dispersion_pares.html")

    # 7. desfases
    fig = go.Figure()
    for k, d in rel["desfases"].items():
        fig.add_trace(go.Scatter(x=[e["desfase_meses"] for e in d["por_desfase"]],
                                 y=[e["pearson_r"] for e in d["por_desfase"]], mode="lines+markers", name=k))
    fig.add_hline(y=0, line_color="gray")
    fig.update_layout(title="Correlación cruzada con desfase (la 1.ª variable adelanta a la 2.ª)",
                      xaxis_title="desfase (meses)", yaxis_title="r de Pearson", height=480, **LAYOUT)
    _save(fig, g / "07_desfases.html")

    # 8. balance anual
    fig = go.Figure(go.Bar(x=anual.index, y=anual["P_menos_ET"],
                           marker_color=np.where(anual["P_menos_ET"] >= 0, COL["P"], COL["T"])))
    a = tend["P_menos_ET"]["anual"]["mco"]
    fig.add_trace(go.Scatter(x=anual.index, y=a["intercepto"] + a["pendiente"] * td, mode="lines",
                             line=dict(color="black"), name="tendencia"))
    fig.update_layout(title="Balance anual P − ET (mm/año)", yaxis_title="mm/año", showlegend=False,
                      height=450, **LAYOUT)
    _save(fig, g / "08_balance_P_menos_ET.html")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
