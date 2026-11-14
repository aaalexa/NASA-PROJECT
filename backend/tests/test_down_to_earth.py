"""Tests de la guía práctica 'Down to Earth: Cuatro variables, dos formas de analizarlas' (§01–§06)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from fastapi.testclient import TestClient

from core.api.app import crear_app
from core.config import DIR_RECURSOS
from motor.catalogo import cargar_catalogo, convertir
from motor.down_to_earth import (
    ajustar_ols_hac_anual,
    analizar_cuatro_variables_dte,
    correlacion_exploratoria_sin_tendencia,
    evaluar_cuatro_tendencias_holm,
    generar_csv_anual_dte,
    generar_csv_mensual_dte,
    tramo_anios_completos_consecutivos,
)
from motor.series import agregar_anual, anomalias_estandarizadas, promedio_area

RUTA_CATALOGO = DIR_RECURSOS / "catalogo.yaml"


def test_conversiones_exactas_seccion_01():
    """Verifica los 4 ejemplos numéricos de la sección 01 del documento Down to Earth."""
    cat = cargar_catalogo(RUTA_CATALOGO)
    # Abril de 2024 tiene 30 días
    t_30d = pd.to_datetime(["2024-04-01"])

    # P: 2 mm/día durante 30 días → 60 mm/mes
    da_p = xr.DataArray([2.0], coords={"time": t_30d}, dims=("time",), attrs={"units": "mm/day"})
    out_p = convertir(da_p, cat["lluvia_gpcp"])
    assert float(out_p.values[0]) == pytest.approx(60.0, rel=1e-12)
    assert out_p.attrs["units"] == "mm/mes"

    # T: 300 K → 26.85 °C
    da_t = xr.DataArray([300.0], coords={"time": t_30d}, dims=("time",), attrs={"units": "K"})
    out_t = convertir(da_t, cat["temp_aire"])
    assert float(out_t.values[0]) == pytest.approx(26.85, rel=1e-12)
    assert out_t.attrs["units"] == "degC"

    # SM: 20 kg/m² ÷ 100 → 0.20 m³/m³
    da_sm = xr.DataArray([20.0], coords={"time": t_30d}, dims=("time",), attrs={"units": "kg m-2"})
    out_sm = convertir(da_sm, cat["humedad_suelo"])
    assert float(out_sm.values[0]) == pytest.approx(0.20, rel=1e-12)
    assert out_sm.attrs["units"] == "m3/m3"

    # ET: 0.00001 kg/m²/s × 86 400 × 30 días → 25.92 mm/mes
    da_et = xr.DataArray([0.00001], coords={"time": t_30d}, dims=("time",), attrs={"units": "kg m-2 s-1"})
    out_et = convertir(da_et, cat["evapotranspiracion"])
    assert float(out_et.values[0]) == pytest.approx(25.92, rel=1e-12)
    assert out_et.attrs["units"] == "mm/mes"


def test_agregacion_anual_suma_vs_media_ponderada_dias_y_mes_faltante():
    """§02 y §06: P y ET se suman por año; T y SM se promedian ponderando por días del mes; un mes NaN invalida el año."""
    fechas = pd.date_range("2023-01-01", "2024-12-01", freq="MS")
    dias = fechas.days_in_month.values.astype(float)

    # Serie mensual donde cada mes vale igual a su número de días (28, 29, 30, 31)
    da = xr.DataArray(dias, coords={"time": fechas}, dims=("time",), attrs={"units": "degC"})

    # Media simple vs media ponderada por días en 2023 (365 días): Σ(d_i^2) / 365
    anual_pond = agregar_anual(da, "media_ponderada_dias")
    esperado_2023 = float(np.sum(dias[:12] ** 2) / np.sum(dias[:12]))
    esperado_2024 = float(np.sum(dias[12:] ** 2) / np.sum(dias[12:]))
    assert float(anual_pond.sel(anio=2023)) == pytest.approx(esperado_2023, rel=1e-12)
    assert float(anual_pond.sel(anio=2024)) == pytest.approx(esperado_2024, rel=1e-12)
    # La media ponderada por días difiere de la media aritmética simple de los 12 meses
    assert float(anual_pond.sel(anio=2023)) != pytest.approx(float(np.mean(dias[:12])), rel=1e-5)

    # Suma anual para P y ET: en 2023 la suma de días es 365 y en 2024 (bisiesto) es 366
    da_p = xr.DataArray(dias, coords={"time": fechas}, dims=("time",), attrs={"units": "mm/mes"})
    anual_suma = agregar_anual(da_p, "suma")
    assert float(anual_suma.sel(anio=2023)) == pytest.approx(365.0, rel=1e-12)
    assert float(anual_suma.sel(anio=2024)) == pytest.approx(366.0, rel=1e-12)
    assert anual_suma.attrs["units"] == "mm/anio"

    # Si falta 1 mes en 2023, el año 2023 queda como NaN en ambas agregaciones
    vals_con_hueco = dias.copy()
    vals_con_hueco[5] = np.nan
    da_hueco_t = xr.DataArray(vals_con_hueco, coords={"time": fechas}, dims=("time",), attrs={"units": "degC"})
    da_hueco_p = xr.DataArray(vals_con_hueco, coords={"time": fechas}, dims=("time",), attrs={"units": "mm/mes"})
    assert np.isnan(float(agregar_anual(da_hueco_t, "media_ponderada_dias").sel(anio=2023)))
    assert np.isnan(float(agregar_anual(da_hueco_p, "suma").sel(anio=2023)))
    assert np.isfinite(float(agregar_anual(da_hueco_t, "media_ponderada_dias").sel(anio=2024)))


def test_pendiente_por_decada_y_se_cero_seccion_06():
    """§03.1 y §06: una serie que sube +2 por año debe dar +20 por década; si SE=0 no emite p ni IC."""
    anios = np.arange(2001, 2025, dtype=int)
    # Recta exacta sin ruido: sube +2 unidades cada año -> +20 por década, pero SE == 0
    y_exacta = 100.0 + 2.0 * (anios - 2001)
    res_exacta = ajustar_ols_hac_anual(anios, y_exacta)
    assert res_exacta["slope_annual"] == pytest.approx(2.0, rel=1e-9)
    assert res_exacta["slope_decade"] == pytest.approx(20.0, rel=1e-9)
    assert res_exacta["inferencia_disponible"] is False
    assert res_exacta["p_raw"] is None
    assert res_exacta["ci95"] is None

    # Serie con ruido pequeño de media cero ortogonal a t: pendiente exacta +2/año (+20/década) y SE > 0
    t = (anios - anios[0]).astype(float)
    ruido = np.sin(np.linspace(0.0, 6.0 * np.pi, len(anios)))
    # Ortogonalizar ruido respecto a [1, t] para conservar b = 2.0 exacto
    X = np.column_stack([np.ones_like(t), t])
    ruido_ort = ruido - X @ np.linalg.lstsq(X, ruido, rcond=None)[0]
    y_ruido = 100.0 + 2.0 * t + 0.5 * ruido_ort

    res = ajustar_ols_hac_anual(anios, y_ruido)
    assert res["slope_annual"] == pytest.approx(2.0, rel=1e-9)
    assert res["slope_decade"] == pytest.approx(20.0, rel=1e-9)
    assert res["inferencia_disponible"] is True
    assert res["p_raw"] is not None and res["p_raw"] < 1e-6
    assert res["ci95"] is not None
    assert res["ci95"][0] < 20.0 < res["ci95"][1]


def test_familia_holm_cuatro_variables_y_placeholder_p1():
    """§03.2: Holm sobre [P, T, SM, ET]; si una variable no es evaluable usa p=1 internamente y publica null."""
    anios = np.arange(2001, 2025, dtype=int)
    t = (anios - anios[0]).astype(float)
    rng = np.random.default_rng(42)

    series = {
        "P": (anios, 800.0 - 4.5 * t + rng.normal(0.0, 8.0, size=len(anios))),
        "T": (anios, 25.0 + 0.05 * t + rng.normal(0.0, 0.12, size=len(anios))),
        "SM": (anios, np.full_like(t, 0.22)),  # constante -> SE = 0 -> no evaluable
        "ET": (anios, 500.0 + 0.1 * t + rng.normal(0.0, 15.0, size=len(anios))),
    }
    res = evaluar_cuatro_tendencias_holm(series, alfa=0.05)
    assert set(res.keys()) == {"P", "T", "SM", "ET"}

    # SM tenía varianza cero -> inferencia_disponible False y p_holm None
    assert res["SM"]["p_raw"] is None
    assert res["SM"]["p_holm"] is None
    assert "sin inferencia" in res["SM"]["label"]

    # P y T tienen tendencia fuerte -> significativos tras Holm
    assert res["P"]["p_holm"] is not None and res["P"]["p_holm"] < 0.05
    assert res["P"]["significant"] is True
    assert res["P"]["label"] == "Disminución con evidencia estadística."

    assert res["T"]["p_holm"] is not None and res["T"]["p_holm"] < 0.05
    assert res["T"]["significant"] is True
    assert res["T"]["label"] == "Aumento con evidencia estadística."

    # Todos incluyen sensibilidad para rezagos 1, 2 y 3
    assert set(res["P"]["sensibilidad_rezagos"].keys()) == {"lag_1", "lag_2", "lag_3"}


def test_anomalias_estandarizadas_y_correlacion_sin_tendencia():
    """§04: z mensual por mes calendario y Pearson r sobre residuos sin tendencia lineal."""
    fechas = pd.date_range("2001-01-01", "2024-12-01", freq="MS")
    rng = np.random.default_rng(123)
    pulso = rng.normal(0.0, 1.0, size=len(fechas))
    t = np.arange(len(fechas), dtype=float)
    est = 20.0 * np.sin(2.0 * np.pi * fechas.month.values / 12.0)

    # Dos series con tendencias opuestas fuertes pero anomalías intermensuales positivamente correlacionadas
    p_vals = 100.0 + est + 0.4 * t + 5.0 * pulso
    sm_vals = 0.25 + 0.05 * np.sin(2.0 * np.pi * fechas.month.values / 12.0) - 0.002 * t + 0.02 * pulso

    da_p = xr.DataArray(p_vals, coords={"time": fechas}, dims=("time",), attrs={"units": "mm/mes"})
    da_sm = xr.DataArray(sm_vals, coords={"time": fechas}, dims=("time",), attrs={"units": "m3/m3"})

    z_p = anomalias_estandarizadas(da_p)
    z_sm = anomalias_estandarizadas(da_sm)

    # Cada mes calendario en z_p tiene media ~0 y desviación estándar muestral (ddof=1) ~1
    for mes in range(1, 13):
        vals_mes = z_p.sel(time=z_p["time"].dt.month == mes).values
        assert float(np.mean(vals_mes)) == pytest.approx(0.0, abs=1e-10)
        assert float(np.std(vals_mes, ddof=1)) == pytest.approx(1.0, rel=1e-6)

    # Sin quitar tendencia, las pendientes opuestas dominan (r crudo < -0.5); al quitar tendencia se recupera r > 0.75
    r_crudo = float(np.corrcoef(z_p.values, z_sm.values)[0, 1])
    assert r_crudo < -0.50
    corr = correlacion_exploratoria_sin_tendencia(z_p, z_sm)
    assert corr["n"] == 288
    assert corr["r"] is not None and corr["r"] > 0.75


def test_cobertura_area_y_tramo_consecutivo():
    """§02: promedio_area registra cobertura de área válida y seleccionar_tramo_anios_consecutivos no comprime huecos."""
    fechas = pd.date_range("2020-01-01", "2020-03-01", freq="MS")
    datos = np.ones((3, 2, 2), dtype=float)
    datos[:, 0, 0] = np.nan  # 1 de 4 celdas siempre NaN
    cubo = xr.DataArray(
        datos,
        coords={"time": fechas, "lat": [0.0, 10.0], "lon": [0.0, 10.0]},
        dims=("time", "lat", "lon"),
        attrs={"units": "mm/mes"},
    )
    serie = promedio_area(cubo)
    assert 0.70 < serie.attrs["cobertura_area_media"] < 0.80
    assert serie.attrs["cobertura_estable"] is True

    # Tramo consecutivo más largo cuando el año 2005 está incompleto en un rango 2001..2010
    anios = np.arange(2001, 2011, dtype=int)
    vals = np.where(anios == 2005, np.nan, 10.0)
    tramo_a, _, advs = tramo_anios_completos_consecutivos(anios, vals)
    assert list(tramo_a) == [2006, 2007, 2008, 2009, 2010]
    assert any("2005" in a for a in advs)


def test_endpoints_down_to_earth_catalog_demo_result_y_csv(dir_datos_temporal):
    """§05 y §06: prueba GET /catalog, GET /demo/result y GET /demo/csv/{mensual,anual} sin archivos en disco."""
    c = TestClient(crear_app())

    r_cat = c.get("/catalog")
    assert r_cat.status_code == 200
    cat_json = r_cat.json()
    assert [v["code"] for v in cat_json["variables"]] == ["P", "T", "SM", "ET"]
    assert cat_json["period_default"] == ["2001-01", "2024-12"]
    assert cat_json["months_expected"] == 288
    assert cat_json["years_expected"] == 24

    r_demo = c.get("/demo/result", params={"region": "sahel", "sintetico": True})
    assert r_demo.status_code == 200
    demo = r_demo.json()
    json.dumps(demo, allow_nan=False)

    assert demo["metadata"]["months_total"] == 288
    assert demo["metadata"]["years_complete_count"] == 24
    assert demo["metadata"]["DiskStorageUsed"] is False if "DiskStorageUsed" in demo["metadata"] else True
    assert set(demo["variables"].keys()) == {"P", "T", "SM", "ET"}

    for cod in ("P", "T", "SM", "ET"):
        var_obj = demo["variables"][cod]
        assert len(var_obj["monthly"]) == 288
        assert len(var_obj["annual"]) == 24
        assert var_obj["slope_decade"] is not None
        assert var_obj["ci95"] is not None and len(var_obj["ci95"]) == 2
        assert var_obj["p_raw"] is not None
        assert var_obj["p_holm"] is not None

    # Pares prioritarios exactos de la sección 04: P-SM, T-SM y P-ET
    assert set(demo["joint"]["pairs"].keys()) == {"P-SM", "T-SM", "P-ET"}
    for par, info_par in demo["joint"]["pairs"].items():
        assert info_par["n"] == 288
        assert info_par["r"] is not None and -1.0 <= info_par["r"] <= 1.0
        assert "p_value" not in info_par  # descriptivo sin p-valor

    # Exportación CSV mensual (encabezado + 288 filas) y anual (encabezado + 24 filas) en RAM
    r_csv_m = c.get("/demo/csv/mensual", params={"region": "sahel", "sintetico": True})
    assert r_csv_m.status_code == 200
    lineas_m = r_csv_m.text.strip().splitlines()
    assert lineas_m[0] == "fecha,P_mm_mes,T_degC,SM_m3_m3,ET_mm_mes"
    assert len(lineas_m) == 289

    r_csv_a = c.get("/demo/csv/anual", params={"region": "sahel", "sintetico": True})
    assert r_csv_a.status_code == 200
    lineas_a = r_csv_a.text.strip().splitlines()
    assert lineas_a[0] == "anio,P_mm_anio,T_degC,SM_m3_m3,ET_mm_anio"
    assert len(lineas_a) == 25

    # 0 archivos creados en disco
    assert len(list(dir_datos_temporal.glob("*"))) == 0
