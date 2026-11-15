"""Limpieza estructural de las series regionales Down to Earth (motor/limpieza_dte.py) y tablas con formato."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from core.motor.down_to_earth import analizar_cuatro_variables_dte
from core.motor.limpieza_dte import (
    LIMITES_FISICOS,
    diccionario_datos,
    limpiar_series_dte,
    tabla_anual_formateada,
    tabla_mensual_formateada,
)
from core.servicios.dte_cli import analizar_desde_csv, escribir_salidas


def _serie(valores, fechas):
    return pd.Series(np.asarray(valores, dtype="float64"), index=pd.DatetimeIndex(fechas))


def test_cada_regla_de_limpieza_queda_registrada():
    fechas = pd.date_range("2001-01-01", "2001-12-01", freq="MS")
    p = _serie(np.full(12, 50.0), fechas)
    p.iloc[1] = -9999.0          # relleno
    p.iloc[2] = np.inf           # no finito
    p.iloc[3] = 5000.0           # fuera de rango físico
    p.iloc[4] = 0.0              # cero exacto (se conserva y se advierte)
    p = p.drop(fechas[5])        # mes ausente
    # Fecha con hora y día distintos de 1 → se normaliza al inicio de mes
    t = _serie(np.full(12, 20.0), fechas + pd.Timedelta(hours=12) + pd.Timedelta(days=14))
    # Duplicados: uno idéntico y uno contradictorio
    sm = pd.concat([_serie(np.full(12, 0.2), fechas),
                    _serie([0.2], [fechas[0]]), _serie([0.3], [fechas[6]])])
    et = _serie(np.full(12, 40.0), fechas)

    r = limpiar_series_dte({"P": p, "T": t, "SM": sm, "ET": et}, "2001-01", "2001-12")

    assert list(r.mensual.columns) == ["P", "T", "SM", "ET"]
    assert r.mensual.index.equals(fechas) and (r.mensual.dtypes == "float64").all()
    P = r.mensual["P"]
    assert np.isnan(P.iloc[1]) and np.isnan(P.iloc[2]) and np.isnan(P.iloc[3]) and np.isnan(P.iloc[5])
    assert P.iloc[4] == 0.0 and not (P.fillna(-1) == 0).iloc[[1, 2, 3, 5]].any()  # nada se rellenó con 0
    assert r.mensual["T"].notna().all()
    assert r.mensual["SM"].iloc[0] == 0.2 and np.isnan(r.mensual["SM"].iloc[6])

    res = r.resumen
    assert (res["P"]["relleno"], res["P"]["no_finitos"], res["P"]["fuera_de_rango"], res["P"]["meses_ausentes"],
            res["P"]["ceros_exactos"]) == (1, 1, 1, 1, 1)
    assert res["SM"]["duplicados_identicos"] == 1 and res["SM"]["duplicados_contradictorios"] == 1
    assert res["P"]["anios_incompletos"] == [2001] and res["T"]["anios_incompletos"] == []
    motivos = set(r.registro["motivo"])
    assert any("relleno" in m for m in motivos) and any("límite físico" in m for m in motivos)
    assert any("mes ausente" in m for m in motivos) and any("cero exacto" in m for m in motivos)


def test_limites_fisicos_no_tocan_valores_validos():
    fechas = pd.date_range("2001-01-01", "2001-12-01", freq="MS")
    entradas = {v: _serie(np.linspace(lo, hi, 12), fechas) for v, (lo, hi) in LIMITES_FISICOS.items()}
    r = limpiar_series_dte(entradas, "2001-01", "2001-12")
    assert r.mensual.notna().all().all()
    assert all(r.resumen[v]["fuera_de_rango"] == 0 for v in LIMITES_FISICOS)


def _resultado_simulado():
    fechas = pd.date_range("2001-01-01", "2024-12-01", freq="MS")
    rng = np.random.default_rng(9)
    datos = {
        "P": (60 + 20 * rng.random(fechas.size), "mm/mes"),
        "T": (20 + rng.normal(size=fechas.size), "degC"),
        "SM": (0.2 + 0.01 * rng.normal(size=fechas.size), "m3/m3"),
        "ET": (40 + rng.normal(size=fechas.size), "mm/mes"),
    }
    datos["P"][0][100] = 9999.0  # fuera de rango físico → faltante
    entradas = {c: xr.DataArray(v, coords={"time": fechas}, dims=("time",), attrs={"units": u})
                for c, (v, u) in datos.items()}
    return analizar_cuatro_variables_dte(entradas, fuente_datos="sintetico")


def test_analisis_usa_la_serie_limpia_y_tablas_con_formato():
    res = _resultado_simulado()
    assert res["variables"]["P"]["monthly"][100]["value"] is None
    assert res["data_cleaning"]["summary"]["P"]["fuera_de_rango"] == 1
    assert any("fuera de rango físico" in w for w in res["metadata"]["warnings"])
    # 2009 queda incompleto para P → el tramo común es el más largo sin 2009 (2010–2024)
    assert res["metadata"]["trend_span"]["start"] == 2010

    m = tabla_mensual_formateada(res)
    assert list(m.columns[:8]) == ["fecha", "anio", "mes", "dias_mes", "P_mm_mes", "T_C", "SM_m3_m3", "ET_mm_mes"]
    assert m.loc[100, "P_mm_mes"] == "" and m.loc[0, "SM_m3_m3"].count(".") == 1
    assert len(m.loc[0, "SM_m3_m3"].split(".")[1]) == 5 and len(m.loc[0, "P_mm_mes"].split(".")[1]) == 2
    assert int(m.loc[1, "dias_mes"]) == 28 and int(m.loc[37, "dias_mes"]) == 29  # feb-2001 y feb-2004
    a = tabla_anual_formateada(res)
    fila_2009 = a[a["anio"] == 2009].iloc[0]
    assert fila_2009["P_mm_anio"] == "" and fila_2009["completo_P"] == 0 and fila_2009["en_tramo_tendencias"] == 0
    d = diccionario_datos()
    assert {"P_mm_mes", "T_C", "SM_m3_m3", "ET_mm_mes", "P_mm_anio", "ET_mm_anio"} <= set(d["columna"])


def test_escribir_salidas_y_reanalizar_desde_csv_da_lo_mismo(tmp_path):
    res = _resultado_simulado()
    escritas = {p.name for p in escribir_salidas(res, tmp_path)}
    assert escritas == {"resultados.json", "serie_regional.csv", "mensual.csv", "anual.csv",
                        "registro_limpieza.csv", "diccionario_datos.csv"}
    reg = pd.read_csv(tmp_path / "registro_limpieza.csv")
    assert list(reg.columns) == ["fecha", "variable", "valor_original", "accion", "motivo"]
    assert (reg["fecha"] == "2009-05").any()

    res2 = analizar_desde_csv(tmp_path / "serie_regional.csv")
    for c in ("P", "T", "SM", "ET"):
        assert res2["variables"][c]["slope_decade"] == pytest.approx(res["variables"][c]["slope_decade"], rel=1e-12)
        assert res2["variables"][c]["p_holm"] == pytest.approx(res["variables"][c]["p_holm"], rel=1e-12)
    assert res2["metadata"]["simulated"] is False and res2["metadata"]["source"] == "csv_regional"


def test_limites_fisicos_iguales_en_backend_y_script_de_la_skill():
    script = Path(__file__).resolve().parents[1] / ".claude/skills/analisis-down-to-earth/scripts/analisis_dte.py"
    if not script.exists():
        pytest.skip("skill no disponible")
    spec = importlib.util.spec_from_file_location("analisis_dte_skill_lim", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.LIMITES_FISICOS == LIMITES_FISICOS
