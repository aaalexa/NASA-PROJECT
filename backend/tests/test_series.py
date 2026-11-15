"""Tests de motor/series.py (skills preprocesamiento-series y validacion-y-pruebas)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from motor.series import (
    SerieRechazada,
    agregar_anual,
    anomalias,
    climatologia,
    control_calidad,
    preparar_para_motor,
    promedio_area,
    recortar_poligono,
    serie_region,
)
from motor.tendencias import calcular_tendencia


def test_promedio_ponderado_por_cos_latitud():
    """Valor 1 en el ecuador (lat=0°) y 0 en lat=60° → cos(0)/(cos(0)+cos(60°)) = 1 / 1.5 = 2/3, no 0.5."""
    t = pd.date_range("2020-01-01", periods=2, freq="MS")
    datos = np.zeros((2, 2, 3))
    datos[:, 0, :] = 1.0  # lat = 0°
    datos[:, 1, :] = 0.0  # lat = 60°
    da = xr.DataArray(
        datos,
        coords={"time": t, "lat": [0.0, 60.0], "lon": [-10.0, 0.0, 10.0]},
        dims=("time", "lat", "lon"),
        attrs={"units": "mm/mes"},
    )
    s = promedio_area(da)
    assert s.attrs["units"] == "mm/mes"
    np.testing.assert_allclose(s.values, [2.0 / 3.0, 2.0 / 3.0], rtol=1e-12)


def test_promedio_area_excluye_nan_y_aplica_min_area_valida():
    t = pd.date_range("2020-01-01", periods=2, freq="MS")
    datos = np.array([
        [[10.0, 20.0], [30.0, 40.0]],
        [[10.0, np.nan], [np.nan, np.nan]],  # solo 1 de 4 celdas válida (25 % < 90 %)
    ])
    da = xr.DataArray(
        datos,
        coords={"time": t, "lat": [0.0, 0.5], "lon": [0.0, 0.5]},
        dims=("time", "lat", "lon"),
        attrs={"units": "degC"},
    )
    s = promedio_area(da, min_area_valida=0.9)
    assert np.isfinite(s.values[0])
    assert np.isnan(s.values[1])  # rechazado por cobertura espacial < 90 %


def test_recortar_poligono_grande_y_pequeno():
    t = pd.date_range("2020-01-01", periods=1, freq="MS")
    lats = np.arange(0.0, 5.0, 1.0)
    lons = np.arange(0.0, 5.0, 1.0)
    da = xr.DataArray(
        np.ones((1, lats.size, lons.size)) * 5.0,
        coords={"time": t, "lat": lats, "lon": lons},
        dims=("time", "lat", "lon"),
        attrs={"units": "mm/mes"},
    )
    # Polígono que cubre varios centros (1..3)
    geo_grande = {
        "type": "Polygon",
        "coordinates": [[[0.5, 0.5], [3.5, 0.5], [3.5, 3.5], [0.5, 3.5], [0.5, 0.5]]],
    }
    sub = recortar_poligono(da, geo_grande)
    assert sub.attrs["units"] == "mm/mes"
    assert float(promedio_area(sub).values[0]) == pytest.approx(5.0)

    # Polígono pequeño entre centros (0.2..0.8, ningún centro entero cae dentro) → usa mask_3D_frac_approx
    geo_pequeno = {
        "type": "Polygon",
        "coordinates": [[[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8], [0.2, 0.2]]],
    }
    sub_peq = recortar_poligono(da, geo_pequeno)
    assert "_fraccion_poligono" in sub_peq.coords
    assert float(promedio_area(sub_peq).values[0]) == pytest.approx(5.0)


def test_climatologia_y_anomalias_eliminan_ciclo_estacional():
    fechas = pd.date_range("2001-01-01", "2020-12-01", freq="MS")
    t = np.arange(len(fechas), dtype=float)
    ciclo = 15.0 * np.sin(2.0 * np.pi * fechas.month.values / 12.0)
    valores = 80.0 + ciclo + 0.05 * t
    serie = xr.DataArray(valores, coords={"time": fechas}, dims=("time",), attrs={"units": "mm/mes"})

    clim = climatologia(serie, base=("2001-01", "2020-12"))
    anom = anomalias(serie, clim=clim)
    assert anom.attrs["units"] == "mm/mes"
    assert float(anom.mean().values) == pytest.approx(0.0, abs=1e-10)
    assert anom.attrs["media_climatologia"] == pytest.approx(float(serie.mean().values), rel=1e-6)
    # Las anomalías solo conservan la recta 0.05·(t - t̄_mes), sin la onda estacional de amplitud 15.
    assert float(anom.std().values) < 4.0


def test_agregar_anual_suma_media_y_validacion_unidades():
    fechas = pd.date_range("2020-01-01", "2021-12-01", freq="MS")
    vals = np.full(24, 10.0)
    serie_mes = xr.DataArray(vals, coords={"time": fechas}, dims=("time",), attrs={"units": "mm/mes"})
    anual = agregar_anual(serie_mes, "suma")
    assert anual.dims == ("anio",)
    assert anual.attrs["units"] == "mm/anio"
    np.testing.assert_allclose(anual.values, [120.0, 120.0])

    # Un mes NaN hace que ese año sea NaN
    vals_hueco = vals.copy()
    vals_hueco[5] = np.nan
    anual_hueco = agregar_anual(
        xr.DataArray(vals_hueco, coords={"time": fechas}, dims=("time",), attrs={"units": "mm/mes"}),
        "suma",
    )
    assert np.isnan(anual_hueco.values[0]) and anual_hueco.values[1] == pytest.approx(120.0)

    # Sumar directamente mm/dia lanza ValueError
    serie_tasa = xr.DataArray(vals, coords={"time": fechas}, dims=("time",), attrs={"units": "mm/dia"})
    with pytest.raises(ValueError, match="mm/mes"):
        agregar_anual(serie_tasa, "suma")


def test_control_calidad_umbral_10_pct_y_fechas_omitidas():
    fechas = pd.date_range("2015-01-01", "2022-12-01", freq="MS")  # 96 meses (pero probemos con 100 meses)
    fechas_100 = pd.date_range("2015-01-01", periods=100, freq="MS")
    fin_str = fechas_100[-1].strftime("%Y-%m")

    # 9 % faltantes (eliminando 9 fechas del DataArray para probar que reindexar las detecta) → aceptada
    serie_9 = xr.DataArray(
        np.ones(91),
        coords={"time": fechas_100[9:]},
        dims=("time",),
        name="lluvia_gpcp",
        attrs={"units": "mm/mes"},
    )
    rep = control_calidad(serie_9, "2015-01", fin_str)
    assert rep["aceptada"] is True
    assert rep["n_esperados"] == 100
    assert rep["n_faltantes"] == 9
    assert rep["fraccion_faltante"] == pytest.approx(0.09)

    # 11 % faltantes → SerieRechazada con .reporte
    serie_11 = xr.DataArray(
        np.ones(89),
        coords={"time": fechas_100[11:]},
        dims=("time",),
        name="lluvia_gpcp",
        attrs={"units": "mm/mes"},
    )
    with pytest.raises(SerieRechazada) as exc_info:
        control_calidad(serie_11, "2015-01", fin_str)
    assert exc_info.value.reporte["aceptada"] is False
    assert exc_info.value.reporte["n_faltantes"] == 11


def test_serie_region_y_preparar_para_motor(serie_ar1):
    fechas = pd.date_range("2005-01-01", "2024-12-01", freq="MS")
    _, y = serie_ar1(len(fechas), 0.03, 0.3, semilla=42)
    cubo = xr.DataArray(
        np.broadcast_to((80.0 + y)[:, None, None], (len(fechas), 2, 2)).copy(),
        coords={"time": fechas, "lat": [10.0, 12.0], "lon": [0.0, 2.0]},
        dims=("time", "lat", "lon"),
        name="lluvia_gpcp",
        attrs={"units": "mm/mes"},
    )
    serie, rep = serie_region(cubo, (-5.0, 8.0, 5.0, 15.0), "2005-01", "2024-12")
    assert rep["aceptada"] is True
    em = preparar_para_motor(serie)
    res = calcular_tendencia(
        em["y"],
        em["t"],
        unidad_tiempo=em["unidad_tiempo"],
        variable="lluvia_gpcp",
        region="sahel",
        periodo=em["periodo"],
        media_climatologia=em["media_climatologia"],
    )
    assert res["veredicto"] == "significativo"
    assert res["cambio_pct_decada"] is not None



def test_serie_region_anual_rechaza_si_faltan_anios():
    """10 % de meses faltantes (aceptado en mensual) repartidos uno por año anulan todos los años.

    La serie anual tiene 10/10 años NaN: debe rechazarse aunque el control mensual la acepte.
    """
    tiempo = pd.date_range("2001-01-01", "2010-12-01", freq="MS")
    valores = np.full(tiempo.size, 50.0)
    valores[[a * 12 + 5 for a in range(10)] + [3, 15]] = np.nan  # 12/120 = 10 % exacto
    cubo = xr.DataArray(
        valores[:, None, None] * np.ones((1, 2, 2)),
        dims=("time", "lat", "lon"),
        coords={"time": tiempo, "lat": [10.0, 10.5], "lon": [0.0, 0.5]},
        attrs={"units": "mm/mes"},
    )
    _, reporte_mensual = serie_region(cubo, None, "2001-01", "2010-12")
    assert reporte_mensual["aceptada"]

    with pytest.raises(SerieRechazada) as exc:
        serie_region(cubo, None, "2001-01", "2010-12", anual="suma")
    assert exc.value.reporte["n_faltantes"] == 10


def test_serie_region_anual_aceptada_incluye_reporte_anual():
    tiempo = pd.date_range("2001-01-01", "2010-12-01", freq="MS")
    cubo = xr.DataArray(
        np.full((tiempo.size, 1, 1), 2.0),
        dims=("time", "lat", "lon"),
        coords={"time": tiempo, "lat": [10.0], "lon": [0.0]},
        attrs={"units": "mm/dia"},
    )
    serie, reporte = serie_region(cubo, None, "2001-01", "2010-12", anual="suma")
    assert reporte["anual"]["aceptada"] and reporte["anual"]["n_faltantes"] == 0
    assert serie.attrs["units"] == "mm/anio"
    assert float(serie.sel(anio=2004)) == pytest.approx(2.0 * 366)
