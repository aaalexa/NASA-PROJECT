"""Paridad entre el motor del backend (motor/down_to_earth.py) y el script de referencia de la skill.

El script `.claude/skills/analisis-down-to-earth/scripts/analisis_dte.py` es la especificación ejecutable del método
Down to Earth. Con las mismas series mensuales, el backend debe dar exactamente los mismos valores anuales, tramo,
pendientes, IC, p, p de Holm, etiquetas y correlaciones. Datos SIMULADOS (evals/files).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from motor.down_to_earth import analizar_cuatro_variables_dte

SKILL = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "analisis-down-to-earth"
SCRIPT = SKILL / "scripts" / "analisis_dte.py"
FILES = SKILL / "evals" / "files"

pytestmark = pytest.mark.skipif(not SCRIPT.exists(), reason="skill analisis-down-to-earth no disponible")

UNIDADES = {"P": "mm/mes", "T": "degC", "SM": "m3/m3", "ET": "mm/mes"}


def _cargar_script():
    spec = importlib.util.spec_from_file_location("analisis_dte_skill", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize(
    ("archivo", "unidades", "tramo_esperado"),
    [("dte_simulado_completo.csv", "finales", (2001, 2024)), ("dte_simulado_originales.csv", "originales", (2002, 2012))],
)
def test_backend_igual_al_script_de_la_skill(archivo, unidades, tramo_esperado):
    skill = _cargar_script()
    filas, campos = skill.leer_csv(str(FILES / archivo))
    ref = skill.analizar(filas, campos, unidades=unidades, simulado=True, usar_statsmodels=True)
    ref_vars = {v["id"]: v for v in ref["variables"]}

    # Mismas series mensuales (ya convertidas por el script) como entrada 1-D del backend
    fechas = pd.to_datetime([m["fecha"] + "-01" for m in ref_vars["P"]["monthly"]])
    entradas = {
        c: xr.DataArray(
            np.array([np.nan if m["valor"] is None else m["valor"] for m in ref_vars[c]["monthly"]], dtype=float),
            coords={"time": fechas}, dims=("time",), attrs={"units": UNIDADES[c]},
        )
        for c in ("P", "T", "SM", "ET")
    }
    res = analizar_cuatro_variables_dte(entradas, fuente_datos="sintetico")

    tr = res["metadata"]["trend_span"]
    assert (tr["start"], tr["end"]) == tramo_esperado
    assert (ref["metadata"]["tramo_tendencias"]["inicio"], ref["metadata"]["tramo_tendencias"]["fin"]) == tramo_esperado

    for c in ("P", "T", "SM", "ET"):
        b, s = res["variables"][c], ref_vars[c]
        # Valores anuales (suma / media ponderada por días; años incompletos = null)
        anual_b = [a["value"] for a in b["annual"]]
        anual_s = [a["valor"] for a in s["annual"]]
        for x, y in zip(anual_b, anual_s):
            assert (x is None and y is None) or x == pytest.approx(y, rel=1e-10, abs=1e-12)
        assert b["slope_decade"] == pytest.approx(s["slope_decade"], rel=1e-9)
        assert b["ci95"][0] == pytest.approx(s["ci95"][0], rel=1e-9)
        assert b["ci95"][1] == pytest.approx(s["ci95"][1], rel=1e-9)
        assert b["p_raw"] == pytest.approx(s["p_raw"], rel=1e-9, abs=1e-300)
        assert b["p_holm"] == pytest.approx(s["p_holm"], rel=1e-9, abs=1e-300)
        assert b["label"] == s["label"]
        for lag_b, lag_s in zip((b["sensitivity"]["lag_2"], b["sensitivity"]["lag_3"]), s["sensibilidad"]["rezagos"]):
            assert lag_b["p_holm"] == pytest.approx(lag_s["p_holm"], rel=1e-9, abs=1e-300)

    ref_pares = {p["par"].replace("–", "-"): p for p in ref["joint"]["pairs"]}
    for par, info in res["joint"]["pairs"].items():
        assert info["n"] == ref_pares[par]["n"]
        assert info["r"] == pytest.approx(ref_pares[par]["r"], abs=1e-12)

    # Anomalías z idénticas mes a mes
    for zb, zs in zip(res["joint"]["standardized_anomalies"], ref["joint"]["standardized_anomalies"]):
        for c in ("P", "T", "SM", "ET"):
            assert (zb[c] is None and zs[c] is None) or zb[c] == pytest.approx(zs[c], rel=1e-10, abs=1e-12)
