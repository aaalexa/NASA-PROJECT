"""Tests de motor/escaner.py (skills escaner-y-mapas y validacion-y-pruebas)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from motor.escaner import (
    CODIGO_VEREDICTO,
    comparar_dos_caras,
    escanear_region,
    mapa_tendencias,
    poblacion_afectada,
    regrillar_poblacion,
)
from motor.tendencias import calcular_tendencia


def test_escanear_region_orden_y_rechazadas(serie_ar1):
    fechas = pd.date_range("2005-01-01", periods=240, freq="MS")
    _, y_fuerte = serie_ar1(240, 0.03, 0.2, sigma=0.5, semilla=10)
    _, y_moderada = serie_ar1(240, -0.015, 0.2, sigma=0.8, semilla=20)
    _, y_ruido = serie_ar1(240, 0.0, 0.3, sigma=1.0, semilla=30)
    y_huecos = y_ruido.copy()
    y_huecos[:50] = np.nan  # > 20 % NaN → rechazada

    series = {
        "ruido": xr.DataArray(y_ruido, coords={"time": fechas}, dims=("time",), attrs={"units": "mm/dia"}),
        "fuerte": xr.DataArray(y_fuerte, coords={"time": fechas}, dims=("time",), attrs={"units": "mm/dia"}),
        "moderada": xr.DataArray(y_moderada, coords={"time": fechas}, dims=("time",), attrs={"units": "mm/dia"}),
        "con_huecos": xr.DataArray(y_huecos, coords={"time": fechas}, dims=("time",), attrs={"units": "mm/dia"}),
    }
    res = escanear_region(series, "sahel", medias_climatologia={"fuerte": 80.0, "moderada": 80.0, "ruido": 80.0})
    ids_ordenados = [r["variable"] for r in res["resultados"]]
    assert ids_ordenados[0] == "fuerte"
    assert ids_ordenados[-1] == "ruido"
    assert res["resultados"][0]["veredicto"] == "significativo"
    assert abs(res["resultados"][0]["snr"]) >= abs(res["resultados"][1]["snr"])
    assert [r["variable"] for r in res["rechazadas"]] == ["con_huecos"]


def test_mapa_tendencias_coincide_pixel_a_pixel_con_calcular_tendencia(serie_ar1):
    """Cubo 3×3 con tendencias conocidas por píxel: mapa_tendencias coincide exactamente con calcular_tendencia."""
    fechas = pd.date_range("2010-01-01", periods=120, freq="MS")
    t = np.arange(120, dtype=float)
    cubo = np.zeros((120, 3, 3), dtype=float)
    pendientes = [[-0.04, 0.0, 0.04], [-0.02, 0.01, 0.03], [0.0, -0.03, 0.02]]
    for i in range(3):
        for j in range(3):
            _, y = serie_ar1(120, pendientes[i][j], 0.2, sigma=0.5, semilla=100 + i * 3 + j)
            cubo[:, i, j] = y
    # Píxel (2, 2) con 20 % de NaN → debe quedar NaN en el mapa
    cubo[:25, 2, 2] = np.nan

    da = xr.DataArray(
        cubo,
        coords={"time": fechas, "lat": [10.0, 11.0, 12.0], "lon": [0.0, 1.0, 2.0]},
        dims=("time", "lat", "lon"),
        name="lluvia_gpcp",
        attrs={"units": "mm/mes"},
    )
    ds = mapa_tendencias(da, unidad_tiempo="mes")
    assert ds["pendiente_decada"].attrs["units"] == "mm/mes/decada"

    for i in range(3):
        for j in range(3):
            if (i, j) == (2, 2):
                assert np.isnan(float(ds["pendiente_decada"].values[i, j]))
                assert np.isnan(float(ds["veredicto"].values[i, j]))
                continue
            ref = calcular_tendencia(
                cubo[:, i, j],
                t,
                unidad_tiempo="mes",
                variable="pixel",
                region="pixel",
                periodo=("0", "1"),
            )
            assert float(ds["pendiente_decada"].values[i, j]) == pytest.approx(ref["pendiente_ols_decada"], rel=1e-12)
            assert float(ds["p_t"].values[i, j]) == pytest.approx(ref["p_t"], rel=1e-12)
            assert float(ds["p_mk"].values[i, j]) == pytest.approx(ref["p_mk"], rel=1e-12)
            assert float(ds["veredicto"].values[i, j]) == pytest.approx(CODIGO_VEREDICTO[ref["veredicto"]])


def test_comparar_dos_caras():
    seca_sig = {"veredicto": "significativo", "direccion": "baja"}
    hum_sig = {"veredicto": "significativo", "direccion": "sube"}
    hum_ind = {"veredicto": "indicio", "direccion": "sube"}

    r1 = comparar_dos_caras(seca_sig, hum_sig)
    assert r1["signo_opuesto"] is True and r1["ambas_significativas"] is True and r1["dos_caras"] is True

    r2 = comparar_dos_caras(seca_sig, hum_ind)
    assert r2["signo_opuesto"] is True and r2["ambas_significativas"] is False and r2["dos_caras"] is False

    r3 = comparar_dos_caras(seca_sig, seca_sig)
    assert r3["signo_opuesto"] is False and r3["ambas_significativas"] is True and r3["dos_caras"] is False


def test_regrillar_poblacion_conserva_el_total():
    """Población aleatoria a 0.25° regrillada a 1.0° conserva el total (rel=1e-6) y cada celda gruesa suma sus 16 finas."""
    rng = np.random.default_rng(2026)
    lat_f = np.arange(0.125, 4.0, 0.25)   # 16 celdas entre 0 y 4
    lon_f = np.arange(0.125, 4.0, 0.25)   # 16 celdas entre 0 y 4
    valores_finos = rng.uniform(100.0, 5000.0, size=(lat_f.size, lon_f.size))
    pob_fina = xr.DataArray(
        valores_finos,
        coords={"lat": lat_f, "lon": lon_f},
        dims=("lat", "lon"),
        attrs={"units": "personas"},
    )
    malla_gruesa = xr.DataArray(
        np.zeros((4, 4)),
        coords={"lat": [0.5, 1.5, 2.5, 3.5], "lon": [0.5, 1.5, 2.5, 3.5]},
        dims=("lat", "lon"),
    )
    regrillada = regrillar_poblacion(pob_fina, malla_gruesa)
    assert regrillada.attrs["units"] == "personas"
    assert float(regrillada.sum()) == pytest.approx(float(pob_fina.sum()), rel=1e-6)
    # La primera celda gruesa (0..1 × 0..1) es la suma exacta del bloque 4×4 superior izquierdo
    assert float(regrillada.values[0, 0]) == pytest.approx(float(valores_finos[:4, :4].sum()), rel=1e-12)


def test_poblacion_afectada_y_mascara_agricola():
    """Dos celdas secas significativas (100 y 50 personas) y una húmeda 'indicio' → pob_seca=150, pob_humeda=0."""
    lat = [10.0, 11.0]
    lon = [0.0, 1.0]
    mapa = xr.Dataset(
        {
            "pendiente_decada": (("lat", "lon"), [[-5.0, -3.0], [4.0, 0.5]]),
            "veredicto": (("lat", "lon"), [[2.0, 2.0], [1.0, 0.0]]),
            "p_t": (("lat", "lon"), [[0.01, 0.02], [0.03, 0.50]]),
            "p_mk": (("lat", "lon"), [[0.01, 0.01], [0.20, 0.60]]),
        },
        coords={"lat": lat, "lon": lon},
    )
    pob = xr.DataArray(
        [[100.0, 50.0], [200.0, 300.0]],
        coords={"lat": lat, "lon": lon},
        dims=("lat", "lon"),
        attrs={"units": "personas"},
    )
    cultivo = xr.DataArray(
        [[0.8, 0.2], [0.9, 0.1]],
        coords={"lat": lat, "lon": lon},
        dims=("lat", "lon"),
    )
    impacto = poblacion_afectada(mapa, pob, mascara_cultivo=cultivo, umbral_cultivo=0.5)
    assert impacto["pob_seca"] == 150
    assert impacto["pob_humeda"] == 0
    assert impacto["pob_humeda_indicio"] == 200
    assert impacto["pob_total_region"] == 650
    assert impacto["pob_seca_agricola"] == 100
    assert impacto["pob_humeda_agricola"] == 0

