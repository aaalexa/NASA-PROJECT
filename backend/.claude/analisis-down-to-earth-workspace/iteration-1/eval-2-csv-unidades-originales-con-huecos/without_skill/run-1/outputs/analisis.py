"""Conversión de unidades, control de huecos, tendencias por década y correlaciones.
Uso: python analisis.py <csv_entrada> <carpeta_salida>
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats

src, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)

raw = pd.read_csv(src, parse_dates=["time"])
VARS = ["sat_gauge_precip", "T2M", "SoilMoi0_10cm_inst", "Evap_tavg"]

# ---------- 1. Huecos ----------
huecos = []
full = pd.date_range(raw.time.min(), raw.time.max(), freq="MS")
for d in full.difference(raw.time):
    huecos.append({"fecha": d.date().isoformat(), "variable": "TODAS", "tipo": "mes ausente (fila faltante)"})
raw_i = raw.set_index("time")
df = raw_i.reindex(full)
df.index.name = "time"
for c in VARS:
    sent = df[c].isin([-9999, -999, 9.999e20, 1e20, -1e20])
    for d in df.index[sent]:
        huecos.append({"fecha": d.date().isoformat(), "variable": c, "tipo": f"valor centinela {df.at[d, c]:g}"})
    df.loc[sent, c] = np.nan
    for d in raw_i.index[raw_i[c].isna()]:
        huecos.append({"fecha": d.date().isoformat(), "variable": c, "tipo": "celda vacía (NaN)"})
huecos = pd.DataFrame(huecos).sort_values("fecha")
huecos.to_csv(out / "huecos_detectados.csv", index=False)

# ---------- 2. Conversión ----------
conv = pd.DataFrame(index=df.index)
conv["precip_mm_dia"] = df["sat_gauge_precip"]                         # GPCP ya viene en mm/día
conv["t2m_C"] = df["T2M"] - 273.15                                      # K -> °C
conv["humedad_suelo_0_10cm_kg_m2"] = df["SoilMoi0_10cm_inst"]          # kg/m² == mm de agua en 0-10 cm
conv["humedad_suelo_0_10cm_m3_m3"] = df["SoilMoi0_10cm_inst"] / 100.0  # /(1000 kg/m³ * 0.1 m)
conv["evap_mm_dia"] = df["Evap_tavg"] * 86400.0                         # kg m-2 s-1 -> mm/día
conv.to_csv(out / "series_mensuales_convertidas.csv", float_format="%.5f")

MAIN = {"precip_mm_dia": "Precipitación (GPCP) [mm/día]",
        "t2m_C": "Temperatura 2 m (MERRA-2) [°C]",
        "humedad_suelo_0_10cm_kg_m2": "Humedad del suelo 0-10 cm (GLDAS) [kg/m²]",
        "evap_mm_dia": "Evapotranspiración (GLDAS) [mm/día]"}
UNIT = {"precip_mm_dia": "mm/día", "t2m_C": "°C", "humedad_suelo_0_10cm_kg_m2": "kg/m²", "evap_mm_dia": "mm/día"}

rangos = conv[list(MAIN)].describe().T
rangos.to_csv(out / "rangos_tras_conversion.csv", float_format="%.4f")

# ---------- 3. Medias anuales (solo años con 12 meses válidos, sin rellenar) ----------
yr = conv.index.year
n_valid = conv[list(MAIN)].notna().groupby(yr).sum()
anual = conv[list(MAIN)].groupby(yr).mean()
anual = anual.where(n_valid == 12)
anual.index.name = "anio"
anual.to_csv(out / "series_anuales.csv", float_format="%.5f")
n_valid.index.name = "anio"
n_valid.to_csv(out / "meses_validos_por_anio.csv")


# ---------- 4. Tendencias ----------
def r1_gap_aware(years, resid):
    s = pd.Series(resid, index=years)
    pairs = [(s[y], s[y + 1]) for y in s.index if (y + 1) in s.index]
    a, b = np.array(pairs).T
    return np.corrcoef(a, b)[0, 1]


def tendencia(years, y):
    years = np.asarray(years, float); y = np.asarray(y, float)
    n = len(y)
    res = stats.linregress(years, y)
    resid = y - (res.intercept + res.slope * years)
    r1 = r1_gap_aware(years.astype(int), resid)
    neff = n * (1 - r1) / (1 + r1) if r1 > 0 else n
    neff = min(max(neff, 3.0), n)
    sxx = np.sum((years - years.mean()) ** 2)
    se = np.sqrt(np.sum(resid ** 2) / (n - 2) / sxx) * np.sqrt((n - 2) / (neff - 2))
    t = res.slope / se
    p = 2 * stats.t.sf(abs(t), neff - 2)
    tcrit = stats.t.ppf(0.975, neff - 2)
    sen = stats.theilslopes(y, years)
    tau, p_mk = stats.kendalltau(years, y)
    return dict(n_anios=n, pendiente_por_decada=res.slope * 10,
                ic95_inf=(res.slope - tcrit * se) * 10, ic95_sup=(res.slope + tcrit * se) * 10,
                p_valor=p, p_valor_ols_sin_corregir=res.pvalue, r1_residuos=r1, n_efectivo=neff,
                sen_por_decada=sen.slope * 10, mann_kendall_tau=tau, mann_kendall_p=p_mk,
                media=y.mean(), cambio_pct_por_decada=100 * res.slope * 10 / y.mean())


rows = []
for c, lab in MAIN.items():
    s = anual[c].dropna()
    d = tendencia(s.index.values, s.values)
    excl = sorted(set(anual.index) - set(s.index))
    rows.append({"variable": lab, "unidad_por_decada": UNIT[c] + "/década", **d,
                 "anios_usados": f"{s.index.min()}-{s.index.max()}", "anios_excluidos": ",".join(map(str, excl))})
tend = pd.DataFrame(rows)
tend.to_csv(out / "tendencias_por_decada.csv", index=False, float_format="%.6g")

# Sensibilidad: mismo periodo común para las 4 variables
comun = anual.dropna()
rows = []
for c, lab in MAIN.items():
    d = tendencia(comun.index.values, comun[c].values)
    rows.append({"variable": lab, **d})
pd.DataFrame(rows).to_csv(out / "tendencias_periodo_comun.csv", index=False, float_format="%.6g")

# Robustez: tendencia de anomalías mensuales (admite meses sueltos faltantes)
rows = []
for c, lab in MAIN.items():
    s = conv[c]
    anom = (s - s.groupby(s.index.month).transform("mean")).dropna()
    tt = anom.index.year + (anom.index.month - 0.5) / 12
    res = stats.linregress(tt, anom.values)
    resid = anom.values - (res.intercept + res.slope * tt)
    r1 = np.corrcoef(resid[:-1], resid[1:])[0, 1]
    n = len(anom); neff = n * (1 - r1) / (1 + r1) if r1 > 0 else n
    se = res.stderr * np.sqrt((n - 2) / (neff - 2))
    p = 2 * stats.t.sf(abs(res.slope / se), neff - 2)
    rows.append({"variable": lab, "n_meses": n, "pendiente_por_decada": res.slope * 10, "p_valor": p,
                 "r1": r1, "n_efectivo": neff})
pd.DataFrame(rows).to_csv(out / "tendencias_anomalias_mensuales.csv", index=False, float_format="%.6g")

# ---------- 5. Correlaciones (periodo común) ----------
short = {"precip_mm_dia": "precip", "t2m_C": "t2m", "humedad_suelo_0_10cm_kg_m2": "suelo", "evap_mm_dia": "evap"}


def detrend(x):
    yrs = x.index.values.astype(float); r = stats.linregress(yrs, x.values)
    return x - (r.intercept + r.slope * yrs)


crow = []
cols = list(MAIN)
for i in range(4):
    for j in range(i + 1, 4):
        a, b = comun[cols[i]], comun[cols[j]]
        r, p = stats.pearsonr(a, b)
        rd, pdt = stats.pearsonr(detrend(a), detrend(b))
        rs, ps = stats.spearmanr(a, b)
        ma = conv[cols[i]] - conv[cols[i]].groupby(conv.index.month).transform("mean")
        mb = conv[cols[j]] - conv[cols[j]].groupby(conv.index.month).transform("mean")
        m = pd.concat([ma, mb], axis=1).dropna()
        rm, pm = stats.pearsonr(m.iloc[:, 0], m.iloc[:, 1])
        crow.append({"par": f"{short[cols[i]]} vs {short[cols[j]]}", "n_anios": len(a),
                     "pearson_r_anual": r, "p": p, "pearson_r_anual_sin_tendencia": rd, "p_sin_tendencia": pdt,
                     "spearman_rho_anual": rs, "p_spearman": ps,
                     "pearson_r_anom_mensual": rm, "p_anom_mensual": pm, "n_meses": len(m)})
corr = pd.DataFrame(crow)
corr.to_csv(out / "correlaciones.csv", index=False, float_format="%.4g")
comun.rename(columns=short).corr().to_csv(out / "matriz_correlacion_anual.csv", float_format="%.3f")

meta = {"anios_periodo_comun": [int(x) for x in comun.index], "n_comun": int(len(comun))}
(out / "metadatos.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print(huecos.to_string(index=False)); print(rangos)
print(n_valid[(n_valid < 12).any(axis=1)])
print(tend.T); print(pd.read_csv(out / "tendencias_periodo_comun.csv").T)
print(pd.read_csv(out / "tendencias_anomalias_mensuales.csv"))
print(corr.T); print(meta)
