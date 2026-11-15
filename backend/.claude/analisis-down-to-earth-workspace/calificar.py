"""Califica automáticamente los casos 1 y 2 de analisis-down-to-earth (con y sin skill).

Las referencias se recalculan aquí de forma independiente (pandas + statsmodels), sin usar el script de la skill.
Uso: python calificar.py <iteration-dir>
Escribe grading.json en cada carpeta de ejecución (la que contiene outputs/).
"""
from __future__ import annotations

import calendar
import csv
import glob
import json
import math
import os
import re
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

RAIZ = os.path.dirname(os.path.abspath(__file__))
FILES = os.path.join(RAIZ, "..", "skills", "analisis-down-to-earth", "evals", "files")
VARS = ["P", "T", "SM", "ET"]
PARES = [("P", "SM"), ("T", "SM"), ("P", "ET")]


# ----------------------------------------------------------------------------- referencias
def mensual_referencia(caso: int) -> pd.DataFrame:
    if caso == 1:
        df = pd.read_csv(os.path.join(FILES, "dte_simulado_completo.csv"))
        df["fecha"] = pd.to_datetime(df["fecha"])
    else:
        df = pd.read_csv(os.path.join(FILES, "dte_simulado_originales.csv"))
        df["fecha"] = pd.to_datetime(df["time"])
        df = df.rename(columns={"sat_gauge_precip": "P", "T2M": "T", "SoilMoi0_10cm_inst": "SM", "Evap_tavg": "ET"})
        df = df.replace(-9999, np.nan)
        d = df["fecha"].dt.days_in_month
        df["P"] = df["P"] * d
        df["T"] = df["T"] - 273.15
        df["SM"] = df["SM"] / 100
        df["ET"] = df["ET"] * 86400 * d
    df = df.set_index("fecha").sort_index()[VARS]
    idx = pd.date_range("2001-01-01", "2024-12-01", freq="MS")
    return df.reindex(idx)


def anual_referencia(m: pd.DataFrame) -> pd.DataFrame:
    d = m.index.days_in_month.to_numpy()
    out = {}
    for a in range(2001, 2025):
        sel = m.index.year == a
        fila = {}
        for v in VARS:
            x = m.loc[sel, v].to_numpy()
            if np.isnan(x).any() or len(x) != 12:
                fila[v] = np.nan
            elif v in ("P", "ET"):
                fila[v] = x.sum()
            else:
                fila[v] = (x * d[sel]).sum() / d[sel].sum()
        out[a] = fila
    return pd.DataFrame(out).T


def tendencias_referencia(an: pd.DataFrame, a0: int, a1: int, lag: int = 1) -> dict:
    sub = an.loc[a0:a1]
    t = (sub.index.to_numpy() - a0).astype(float)
    res = {}
    for v in VARS:
        r = sm.OLS(sub[v].to_numpy(), sm.add_constant(t)).fit(
            cov_type="HAC", cov_kwds={"maxlags": lag, "kernel": "bartlett", "use_correction": True}, use_t=False)
        res[v] = {"slope": r.params[1] * 10, "p": r.pvalues[1]}
    ph = multipletests([res[v]["p"] for v in VARS], alpha=0.05, method="holm")[1]
    for v, p in zip(VARS, ph):
        res[v]["p_holm"] = p
    return res


def correlaciones_referencia(m: pd.DataFrame) -> dict:
    t = m.index.year + (m.index.month - 0.5) / 12
    resid = {}
    for v in VARS:
        g = m[v].groupby(m.index.month)
        z = (m[v] - g.transform("mean")) / g.transform("std")
        ok = z.notna().to_numpy()
        r = np.full(len(z), np.nan)
        b = np.polyfit(t[ok], z.to_numpy()[ok], 1)
        r[ok] = z.to_numpy()[ok] - np.polyval(b, t[ok])
        resid[v] = r
    out = {}
    for x, y in PARES:
        ok = np.isfinite(resid[x]) & np.isfinite(resid[y])
        out[(x, y)] = (float(np.corrcoef(resid[x][ok], resid[y][ok])[0, 1]), int(ok.sum()))
    return out


# ----------------------------------------------------------------------------- lectura flexible
def textos(out: str) -> str:
    t = []
    for f in glob.glob(os.path.join(out, "**", "*"), recursive=True):
        if f.lower().endswith((".md", ".json", ".txt")) and os.path.getsize(f) < 5_000_000:
            t.append(open(f, encoding="utf-8", errors="ignore").read())
    return "\n".join(t)


def md_texto(out: str) -> str:
    return "\n".join(open(f, encoding="utf-8", errors="ignore").read()
                     for f in glob.glob(os.path.join(out, "**", "*.md"), recursive=True))


def jsons(out: str) -> list:
    res = []
    for f in glob.glob(os.path.join(out, "**", "*.json"), recursive=True):
        try:
            res.append(json.load(open(f, encoding="utf-8")))
        except Exception:  # noqa: BLE001
            pass
    return res


def nums_en(obj, max_lista=30) -> list[float]:
    out = []
    if isinstance(obj, dict):
        for v in obj.values():
            out += nums_en(v, max_lista)
    elif isinstance(obj, list):
        if len(obj) <= max_lista:
            for v in obj:
                out += nums_en(v, max_lista)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        if math.isfinite(obj):
            out.append(float(obj))
    elif isinstance(obj, str):
        for s in re.findall(r"[-+−]?\d+\.?\d*(?:[eE][-+]?\d+)?", obj):
            try:
                out.append(float(s.replace("−", "-")))
            except ValueError:
                pass
    return out


ALIAS = {"P": {"p", "precip", "precipitacion", "precipitación", "lluvia", "sat_gauge_precip", "precipitation"},
         "T": {"t", "t2m", "temp", "temperatura", "temperature"},
         "SM": {"sm", "soilmoi0_10cm_inst", "humedad_suelo", "soil_moisture", "humedad"},
         "ET": {"et", "evap_tavg", "evapotranspiracion", "evapotranspiración", "evapotranspiration"}}


def subarboles_var(obj, v) -> list:
    out = []
    if isinstance(obj, dict):
        for k, val in obj.items():
            if str(k).strip().lower() in ALIAS[v] and isinstance(val, (dict, list)):
                out.append(val)
        ident = str(obj.get("id", obj.get("variable", obj.get("codigo", obj.get("var", ""))))).strip().lower()
        if ident in ALIAS[v]:
            out.append(obj)
        for val in obj.values():
            out += subarboles_var(val, v)
    elif isinstance(obj, list):
        for val in obj:
            out += subarboles_var(val, v)
    return out


def numeros_var(out: str, v: str) -> list[float]:
    ns = []
    for j in jsons(out):
        for s in subarboles_var(j, v):
            ns += nums_en(s)
    return ns


def cerca(ns, ref, tol_rel=None, tol_abs=None) -> bool:
    for x in ns:
        if tol_abs is not None and abs(x - ref) <= tol_abs:
            return True
        if tol_rel is not None and abs(x - ref) <= tol_rel * abs(ref):
            return True
    return False


def buscar_csv(out: str, patron: str) -> list[str]:
    return [f for f in glob.glob(os.path.join(out, "**", "*.csv"), recursive=True)
            if re.search(patron, os.path.basename(f).lower())]


def col_var(cols, v):
    pats = {"P": r"^(p|precip|sat_gauge|lluvia|precipitation)(_|$|\s|\()",
            "T": r"^(t|t2m|temp|temperatura|temperature)(_|$|\s|\()",
            "SM": r"^(sm|soil|humedad)(_|$|\s|\(|moi)",
            "ET": r"^(et|evap)(_|$|\s|\(|o|_tavg)"}
    for c in cols:
        cl = str(c).strip().lower()
        if re.match(pats[v], cl) and not re.search(r"(^z|anom|_z$|completo|valid|n_|flag|frac|en_tramo)", cl):
            return c
    return None


def leer_tabla(f: str) -> pd.DataFrame | None:
    try:
        return pd.read_csv(f, comment="#")
    except Exception:  # noqa: BLE001
        return None


def anual_salida(out: str) -> pd.DataFrame | None:
    cands = [f for f in buscar_csv(out, r"(anual|annual|year|anio)")
             if not re.search(r"(matriz|matrix|meses|valid|correl|tendenc|trend)", os.path.basename(f).lower())]
    for f in cands:
        df = leer_tabla(f)
        if df is None:
            continue
        ccol = next((c for c in df.columns if str(c).strip().lower() in ("anio", "año", "year", "ano", "fecha")), None)
        if ccol is None:
            continue
        df = df.copy()
        df["_anio"] = pd.to_numeric(df[ccol].astype(str).str[:4], errors="coerce")
        if all(col_var(df.columns, v) for v in VARS):
            return df.set_index("_anio")
    return None


def mensual_salida(out: str) -> pd.DataFrame | None:
    cands = buscar_csv(out, r"(mensual|monthly|mes|month|convert)")
    for f in cands:
        df = leer_tabla(f)
        if df is None:
            continue
        ccol = next((c for c in df.columns if str(c).strip().lower() in ("fecha", "date", "time", "mes_fecha")), None)
        if ccol is None or not all(col_var(df.columns, v) for v in VARS):
            continue
        df = df.copy()
        df["_f"] = df[ccol].astype(str).str[:7]
        return df.set_index("_f")
    return None


# ----------------------------------------------------------------------------- casos
def caso1(out: str) -> list[dict]:
    m = mensual_referencia(1)
    an = anual_referencia(m)
    ref = tendencias_referencia(an, 2001, 2024)
    refs = {lag: tendencias_referencia(an, 2001, 2024, lag) for lag in (2, 3)}
    cor = correlaciones_referencia(m)
    T = textos(out)
    MD = md_texto(out)
    Tl = T.lower().replace('*', '').replace('_', ' ')
    js = jsons(out)
    E = []

    def add(text, ok, ev):
        E.append({"text": text, "passed": bool(ok), "evidence": ev})

    tiene_vars = all(any(subarboles_var(j, v) for j in js) for v in VARS)
    conj = bool(re.search(r'"(joint|conjunt\w*|correl\w*|pairs|pares|relacion\w*|asociac\w*)"', T, re.I))
    add("Existe un JSON con metadata, las cuatro variables P, T, SM, ET y una sección del análisis conjunto",
        js and tiene_vars and conj, f"{len(js)} JSON; variables encontradas={tiene_vars}; sección conjunta={conj}")

    det, ok = [], True
    for v in VARS:
        ns = numeros_var(out, v) or nums_en(MD)
        hit = cerca(ns, ref[v]["slope"], tol_rel=0.01)
        ok &= hit
        det.append(f"{v}: ref {ref[v]['slope']:+.4g} {'✓' if hit else '✗'}")
    add("Las pendientes por década de P, T, SM y ET coinciden con OLS anual (tolerancia 1 %)", ok, "; ".join(det))

    det, ok = [], "holm" in Tl
    for v in VARS:
        ns = numeros_var(out, v) or nums_en(MD)
        hit = cerca(ns, ref[v]["p_holm"], tol_abs=0.005)
        ok &= hit
        det.append(f"{v}: ref p_holm {ref[v]['p_holm']:.4f} {'✓' if hit else '✗'}")
    add("Publica p ajustados por Holm sobre las cuatro variables que coinciden con HAC rezago 1 (tolerancia 0.005)",
        ok, f"menciona Holm={'holm' in Tl}; " + "; ".join(det))

    prohib = []
    for mt in re.finditer(r"(sin cambio|no cambi[óo]|no cambiaron|sin tendencia clara|no hay tendencia|no presenta tendencia|es estable)", Tl):
        previo = Tl[max(0, mt.start() - 40):mt.start()]
        if not re.search(r"(no significa|no quiere decir|no implica|no equivale|ni |no es lo mismo|\"|«|')\W*\w*\W*$", previo):
            prohib.append(mt.group(0))
    lab = {}
    for v in VARS:
        s = " ".join(json.dumps(x, ensure_ascii=False).lower() for j in js for x in subarboles_var(j, v))
        lab[v] = s
    okT = "aument" in lab["T"] and "evidencia" in lab["T"]
    okSM = ("dismin" in lab["SM"]) and "evidencia" in lab["SM"]
    okP = "insuficiente" in lab["P"]
    okET = "insuficiente" in lab["ET"]
    add("Las etiquetas siguen el p de Holm: T y SM con evidencia (aumento/disminución), P y ET 'evidencia insuficiente'; "
        "nunca 'sin cambio'/'no cambió'",
        okT and okSM and okP and okET and not prohib,
        f"T={okT} SM={okSM} P={okP} ET={okET}; frases prohibidas={sorted(set(prohib))}")

    s2 = bool(re.search(r"(maxlags|rezago|lag)\W{0,4}\D{0,12}2", T, re.I))
    s3 = bool(re.search(r"(maxlags|rezago|lag)\W{0,4}\D{0,12}3", T, re.I))
    add("Reporta la sensibilidad con rezagos 2 y 3", s2 and s3 and ("sensib" in Tl), f"rezago2={s2} rezago3={s3}")

    det, ok = [], True
    for (x, y), (r, n) in cor.items():
        hit = False
        for j in js:
            for d in _dicts(j):
                txt = json.dumps(d, ensure_ascii=False)
                if _menciona_par(d, x, y) and cerca(nums_en(d), r, tol_abs=0.02) and cerca(nums_en(d), n, tol_abs=0):
                    hit = True
        ok &= hit
        det.append(f"{x}–{y}: ref r={r:.3f}, n={n} {'✓' if hit else '✗'}")
    extra = re.findall(r'"(P[-–_ ]T|T[-–_ ]ET|SM[-–_ ]ET|T[-–_ ]P|ET[-–_ ]SM|ET[-–_ ]T)"', T)
    matriz = bool(re.search(r'"(matriz|matrix|corr_matrix|correlation_matrix)', T, re.I))
    add("Correlaciones solo de los pares P–SM, T–SM y P–ET con r (±0.02 de la referencia sin estación ni tendencia) y n = 288",
        ok and not extra and not matriz, "; ".join(det) + f"; pares extra={extra}; matriz completa={matriz}")

    pkeys = []
    for j in js:
        for d in _dicts(_seccion_conjunta(j)):
            pkeys += [k for k in d if re.match(r"^(p|p_?val\w*|p_?valor|pvalue|p_raw|p_holm|p-valor|p_value)$", str(k))]
    sig_cor = [ln for ln in MD.lower().splitlines()
               if re.search(r"(correl|asociaci|\br\s*=)", ln) and "significativ" in ln
               and not re.search(r"(sin|no|ni)\s+\w*\s*(calificar|llamar|decir|la palabra|p-valor|\"significativ)", ln)
               and "no se califican" not in ln and "sin p" not in ln]
    add("Las correlaciones no llevan p-valor ni se califican de 'significativas'", not pkeys and not sig_cor,
        f"claves p en sección conjunta={sorted(set(pkeys))}; líneas con 'significativ'={sig_cor[:2]}")

    A = anual_salida(out)
    if A is None:
        add("El CSV anual tiene T y SM como media ponderada por días (no suma) y P y ET como suma", False,
            "no encontré un CSV anual con las 4 variables")
    else:
        det, ok = [], True
        tol = {"P": ("rel", 0.002), "ET": ("rel", 0.002), "T": ("abs", 0.002), "SM": ("abs", 2e-5)}
        for v in VARS:
            c = col_var(A.columns, v)
            for a in (2004, 2015, 2023):
                x = pd.to_numeric(A.loc[a, c], errors="coerce") if a in A.index else np.nan
                rv = an.loc[a, v]
                k, tl = tol[v]
                hit = math.isfinite(x) and (abs(x - rv) <= (tl * abs(rv) if k == "rel" else tl))
                ok &= hit
                if not hit:
                    det.append(f"{v} {a}: salida {x} vs ref {rv:.5g}")
        add("El CSV anual tiene T y SM como media ponderada por días (no suma) y P y ET como suma", ok,
            "coinciden en 2004, 2015, 2023" if ok else "; ".join(det[:6]))

    js_sim = any("simulad" in json.dumps(j, ensure_ascii=False).lower() for j in js)
    add("El resumen y el JSON rotulan los datos como simulados", "simulad" in MD.lower() and js_sim,
        f"md={'simulad' in MD.lower()} json={js_sim}")

    causa = re.findall(r"(caus[óo]|provoc[óo]|provocad[oa]|debido a|se debe a|ocasion[óo]|produjo)", MD.lower())
    lim = bool(re.search(r"(límite|limite|limitaci)", MD.lower()))
    add("El resumen no afirma causas (causó/provocó/debido a) y menciona límites", not causa and lim,
        f"frases causales={causa[:4]}; menciona límites={lim}")

    g = [f for f in glob.glob(os.path.join(out, "**", "*"), recursive=True)
         if f.lower().endswith((".svg", ".png", ".html", ".jpg"))]
    add("Se generaron gráficos (serie anual y anomalías z)", len(g) >= 2, f"{len(g)} archivos de gráfico")
    return E


def _dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _dicts(v)


def _seccion_conjunta(j):
    if isinstance(j, dict):
        for k, v in j.items():
            if re.match(r"(joint|conjunt|correl|relacion|asociac|pairs|pares)", str(k), re.I):
                return v
        for v in j.values():
            r = _seccion_conjunta(v)
            if r is not None:
                return r
    return None


def _menciona_par(d, x, y) -> bool:
    s = json.dumps({k: v for k, v in d.items() if not isinstance(v, (list, dict)) or k in ("par", "pair", "vars")},
                   ensure_ascii=False)
    keys = " ".join(map(str, d.keys()))
    pat = rf"\b{x}\s*[-–_/y&]\s*{y}\b|\b{y}\s*[-–_/y&]\s*{x}\b"
    if re.search(pat, s) or re.search(pat, keys):
        return True
    vals = {str(v).strip() for v in d.values() if isinstance(v, str)}
    return {x, y} <= vals


def caso2(out: str) -> list[dict]:
    m = mensual_referencia(2)
    an = anual_referencia(m)
    ref = tendencias_referencia(an, 2002, 2012)
    T = textos(out)
    MD = md_texto(out)
    E = []

    def add(text, ok, ev):
        E.append({"text": text, "passed": bool(ok), "evidence": ev})

    M = mensual_salida(out)
    if M is None:
        for txt in ("Los valores mensuales convertidos coinciden con mm/día×días, K−273.15, kg/m²÷100 y kg/m²/s×86400×días (tolerancia 0.5 %)",
                    "El −9999 de T2M (2001-03) se trata como faltante, no como valor ni como 0",
                    "Ningún mes faltante aparece como 0 ni interpolado en la serie mensual de salida"):
            add(txt, False, "no encontré un CSV mensual con fecha y las 4 variables")
    else:
        det, ok = [], True
        for f in ("2001-02", "2004-02", "2008-07", "2016-02", "2019-10", "2024-02"):
            for v in VARS:
                c = col_var(M.columns, v)
                x = pd.to_numeric(M.loc[f, c], errors="coerce") if f in M.index else np.nan
                x = float(x.iloc[0]) if hasattr(x, "iloc") else float(x)
                rv = m.loc[pd.Timestamp(f + "-01"), v]
                hit = math.isfinite(x) and abs(x - rv) <= 0.005 * abs(rv) + 1e-9
                ok &= hit
                if not hit:
                    det.append(f"{v} {f}: {x} vs {rv:.5g}")
        add("Los valores mensuales convertidos coinciden con mm/día×días, K−273.15, kg/m²÷100 y kg/m²/s×86400×días (tolerancia 0.5 %)",
            ok, "6 meses × 4 variables coinciden (incl. febreros bisiestos)" if ok else "; ".join(det[:6]))

        def val(f, v):
            if f not in M.index:
                return None
            x = pd.to_numeric(M.loc[f, col_var(M.columns, v)], errors="coerce")
            return float(x.iloc[0]) if hasattr(x, "iloc") else float(x)

        x = val("2001-03", "T")
        add("El −9999 de T2M (2001-03) se trata como faltante, no como valor ni como 0",
            x is None or not math.isfinite(x), f"T 2001-03 en salida = {x}")
        malos = []
        for f, vs in (("2013-06", VARS), ("2024-11", ["SM"]), ("2001-03", ["T"])):
            for v in vs:
                x = val(f, v)
                if x is not None and math.isfinite(x):
                    malos.append(f"{v} {f} = {x:.4g}")
        add("Ningún mes faltante aparece como 0 ni interpolado en la serie mensual de salida", not malos,
            "2013-06 (todas), 2024-11 (SM) y 2001-03 (T) quedan vacíos" if not malos else "; ".join(malos))

    R = MD
    inc = bool(re.search(r"(incomplet|falt|hueco)", R.lower())) and all(str(a) in R for a in (2001, 2013, 2024))
    add("Identifica 2001, 2013 y 2024 como años incompletos", inc, "menciona los tres años y huecos" if inc else
        f"años mencionados: {[a for a in (2001, 2013, 2024) if str(a) in R]}")
    tr = bool(re.search(r"2002\s*(?:[–\-—]|a|al|hasta|y)\s*2012", T))
    add("Usa para las tendencias el tramo común 2002–2012 (11 años) y lo dice", tr,
        "encontrado '2002–2012'" if tr else "no aparece el tramo 2002–2012")
    det, ok = [], True
    for v in VARS:
        ns = numeros_var(out, v) or nums_en(T)
        hit = cerca(ns, ref[v]["slope"], tol_rel=0.02)
        ok &= hit
        det.append(f"{v}: ref {ref[v]['slope']:+.4g} {'✓' if hit else '✗'}")
    add("Las pendientes por década en el tramo 2002–2012 coinciden con la referencia (tolerancia 2 %)", ok, "; ".join(det))
    det, ok = [], "holm" in T.lower()
    for v in VARS:
        ns = numeros_var(out, v) or nums_en(T)
        hit = cerca(ns, ref[v]["p_holm"], tol_abs=0.01)
        ok &= hit
        det.append(f"{v}: ref {ref[v]['p_holm']:.4f} {'✓' if hit else '✗'}")
    add("Usa Holm sobre las cuatro variables (p ajustados coinciden con la referencia, tolerancia 0.01)", ok,
        f"menciona Holm={'holm' in T.lower()}; " + "; ".join(det))
    A = anual_salida(out)
    if A is None or 2010 not in A.index:
        add("El año 2010 (filas al final del archivo) queda en su lugar: valores anuales de 2010 correctos", False,
            "no encontré CSV anual con 2010")
    else:
        # Solo comprueba el orden (independiente de unidades/agregación): T anual de 2010 a ±0.05 °C de la referencia
        x = float(pd.to_numeric(A.loc[2010, col_var(A.columns, "T")], errors="coerce"))
        rv = an.loc[2010, "T"]
        otros = {a: abs(x - an.loc[a, "T"]) for a in an.index if math.isfinite(an.loc[a, "T"])}
        add("El año 2010 (filas al final del archivo) queda en su lugar: valores anuales de 2010 correctos",
            math.isfinite(x) and abs(x - rv) <= 0.05, f"T 2010 salida {x:.4g} vs ref {rv:.4g}")
    return E


def main():
    it = sys.argv[1]
    for eval_dir in sorted(glob.glob(os.path.join(it, "eval-*"))):
        meta = json.load(open(os.path.join(eval_dir, "eval_metadata.json"), encoding="utf-8"))
        caso = meta["eval_id"]
        if caso not in (1, 2):
            continue
        for run in glob.glob(os.path.join(eval_dir, "*", "run-*")):
            out = os.path.join(run, "outputs")
            E = caso1(out) if caso == 1 else caso2(out)
            n_ok = sum(e["passed"] for e in E)
            g = {"expectations": E, "summary": {"passed": n_ok, "failed": len(E) - n_ok, "total": len(E),
                                                "pass_rate": round(n_ok / len(E), 4)}}
            json.dump(g, open(os.path.join(run, "grading.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print(f"{os.path.relpath(run, it)}: {n_ok}/{len(E)}")
            for e in E:
                print(f"   [{'x' if e['passed'] else ' '}] {e['text'][:80]} — {e['evidence'][:140]}")


if __name__ == "__main__":
    main()
