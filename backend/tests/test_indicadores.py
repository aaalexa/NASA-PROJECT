"""Tests de motor/indicadores.py con los casos A–E calculados a mano (skill indicadores-lluvia)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from motor.indicadores import indicadores_anuales, racha_seca_maxima, serie_indicador_region


def _serie_diaria(inicio: str, fin: str, valor_base: float = 0.0) -> xr.DataArray:
    fechas = pd.date_range(inicio, fin, freq="D")
    return xr.DataArray(
        np.full(len(fechas), valor_base, dtype=float),
        coords={"time": fechas},
        dims=("time",),
        name="lluvia_imerg_dia",
        attrs={"units": "mm/dia"},
    )


def test_racha_seca_maxima_ejemplo_referencia():
    # Ejemplo de referencia.md §2: [T, T, F, T, T, T, F] → 3
    seco = np.array([True, True, False, True, True, True, False])
    assert int(racha_seca_maxima(seco)) == 3
    assert int(racha_seca_maxima(np.array([], dtype=bool))) == 0


def test_caso_a_anio_normal_a_mano():
    """Caso A (referencia §3): 2001 todo 0 salvo 5 fechas → CDD=169, R20mm=3, W=4, PRCPTOT=75, SDII=18.75."""
    pr = _serie_diaria("2001-01-01", "2001-12-31", 0.0)
    pr.loc[{"time": "2001-01-06"}] = 5.0
    pr.loc[{"time": "2001-01-07"}] = 25.0
    pr.loc[{"time": "2001-01-08"}] = 0.5
    pr.loc[{"time": "2001-03-01"}] = 20.0
    pr.loc[{"time": "2001-07-15"}] = 25.0

    ds = indicadores_anuales(pr)
    assert list(ds["anio"].values) == [2001]
    assert float(ds["cdd"].sel(anio=2001)) == pytest.approx(169.0)
    assert float(ds["r20mm"].sel(anio=2001)) == pytest.approx(3.0)
    assert float(ds["dias_humedos"].sel(anio=2001)) == pytest.approx(4.0)
    assert float(ds["prcptot"].sel(anio=2001)) == pytest.approx(75.0)
    assert float(ds["sdii"].sel(anio=2001)) == pytest.approx(18.75)
    assert ds["cdd"].attrs["units"] == "dias"
    assert ds["prcptot"].attrs["units"] == "mm/anio"
    assert ds["sdii"].attrs["units"] == "mm/dia"


def test_caso_b_umbrales_exactos():
    """Caso B: [1.0, 0.99, 20.0, 19.99] y resto 0 → W=3, R20mm=1, PRCPTOT=40.99."""
    pr = _serie_diaria("2001-01-01", "2001-12-31", 0.0)
    pr.values[:4] = [1.0, 0.99, 20.0, 19.99]
    ds = indicadores_anuales(pr)
    assert float(ds["dias_humedos"].sel(anio=2001)) == pytest.approx(3.0)
    assert float(ds["r20mm"].sel(anio=2001)) == pytest.approx(1.0)
    assert float(ds["prcptot"].sel(anio=2001)) == pytest.approx(40.99, rel=1e-9)


def test_caso_c_anio_sin_lluvia_normal_y_bisiesto():
    """Caso C: 2001 todo 0 → CDD=365, W=0, PRCPTOT=0, SDII=NaN; 2004 (bisiesto) → CDD=366."""
    pr_2001 = _serie_diaria("2001-01-01", "2001-12-31", 0.0)
    ds_2001 = indicadores_anuales(pr_2001)
    assert float(ds_2001["cdd"].sel(anio=2001)) == pytest.approx(365.0)
    assert float(ds_2001["r20mm"].sel(anio=2001)) == pytest.approx(0.0)
    assert float(ds_2001["dias_humedos"].sel(anio=2001)) == pytest.approx(0.0)
    assert float(ds_2001["prcptot"].sel(anio=2001)) == pytest.approx(0.0)
    assert np.isnan(float(ds_2001["sdii"].sel(anio=2001)))

    pr_2004 = _serie_diaria("2004-01-01", "2004-12-31", 0.0)
    ds_2004 = indicadores_anuales(pr_2004)
    assert float(ds_2004["cdd"].sel(anio=2004)) == pytest.approx(366.0)


def test_caso_d_racha_que_cruza_el_anio():
    """Caso D: 2001 y 2002 con P=5 salvo 2001-12-22..2002-01-05 con 0 → CDD(2001)=10, CDD(2002)=5; sin cortar → 15 en 2002."""
    pr = _serie_diaria("2001-01-01", "2002-12-31", 5.0)
    pr.loc[{"time": slice("2001-12-22", "2002-01-05")}] = 0.0

    ds_cortado = indicadores_anuales(pr, cortar_en_anio=True)
    assert float(ds_cortado["cdd"].sel(anio=2001)) == pytest.approx(10.0)
    assert float(ds_cortado["cdd"].sel(anio=2002)) == pytest.approx(5.0)

    ds_continuo = indicadores_anuales(pr, cortar_en_anio=False)
    assert float(ds_continuo["cdd"].sel(anio=2001)) == pytest.approx(0.0)
    assert float(ds_continuo["cdd"].sel(anio=2002)) == pytest.approx(15.0)


def test_caso_e_faltantes_corte_y_rechazo():
    """Caso E: 37 días NaN (10.1 %) → todo NaN; 1 NaN el 2001-07-01 en año seco → CDD = max(181, 183) = 183."""
    pr_malo = _serie_diaria("2001-01-01", "2001-12-31", 0.0)
    pr_malo.values[:37] = np.nan
    ds_malo = indicadores_anuales(pr_malo)
    for var in ("cdd", "r20mm", "dias_humedos", "prcptot", "sdii"):
        assert np.isnan(float(ds_malo[var].sel(anio=2001)))

    pr_un_nan = _serie_diaria("2001-01-01", "2001-12-31", 0.0)
    pr_un_nan.loc[{"time": "2001-07-01"}] = np.nan
    ds_ok = indicadores_anuales(pr_un_nan)
    assert float(ds_ok["cdd"].sel(anio=2001)) == pytest.approx(183.0)
    assert float(ds_ok["dias_humedos"].sel(anio=2001)) == pytest.approx(0.0)


def test_vectorizacion_cubo_2x2_y_serie_region():
    """Cubo 3-D de 2×2 píxeles con series distintas por píxel: cada píxel da su resultado exacto."""
    fechas = pd.date_range("2001-01-01", "2001-12-31", freq="D")
    cubo = np.zeros((len(fechas), 2, 2), dtype=float)
    # Píxel (0,0): todo 0 → CDD = 365
    # Píxel (0,1): todo 25 mm → CDD = 0, R20mm = 365
    cubo[:, 0, 1] = 25.0
    # Píxel (1,0): primeros 10 días con 5 mm y resto 0 → CDD = 355, W = 10
    cubo[:10, 1, 0] = 5.0
    # Píxel (1,1): 50 NaN (> 10 %) → todo NaN
    cubo[:50, 1, 1] = np.nan

    da = xr.DataArray(
        cubo,
        coords={"time": fechas, "lat": [0.0, 10.0], "lon": [0.0, 10.0]},
        dims=("time", "lat", "lon"),
        attrs={"units": "mm/dia"},
    )
    ds = indicadores_anuales(da)
    assert float(ds["cdd"].sel(anio=2001).values[0, 0]) == pytest.approx(365.0)
    assert float(ds["cdd"].sel(anio=2001).values[0, 1]) == pytest.approx(0.0)
    assert float(ds["r20mm"].sel(anio=2001).values[0, 1]) == pytest.approx(365.0)
    assert float(ds["cdd"].sel(anio=2001).values[1, 0]) == pytest.approx(355.0)
    assert float(ds["dias_humedos"].sel(anio=2001).values[1, 0]) == pytest.approx(10.0)
    assert np.isnan(float(ds["cdd"].sel(anio=2001).values[1, 1]))

    # Promedio regional (con min_area_valida=0.5 para aceptar 3 de 4 celdas)
    s_reg = serie_indicador_region(da, "cdd", min_area_valida=0.5)
    assert s_reg.attrs["units"] == "dias"
    assert np.isfinite(float(s_reg.sel(anio=2001)))


def test_validacion_unidades_y_frecuencia():
    pr_mal_unidad = _serie_diaria("2001-01-01", "2001-01-10", 1.0)
    pr_mal_unidad.attrs["units"] = "mm/h"
    with pytest.raises(ValueError, match="mm/dia"):
        indicadores_anuales(pr_mal_unidad)

    fechas_mes = pd.date_range("2001-01-01", "2001-12-01", freq="MS")
    pr_mensual = xr.DataArray(np.ones(12), coords={"time": fechas_mes}, dims=("time",), attrs={"units": "mm/dia"})
    with pytest.raises(ValueError, match="diaria"):
        indicadores_anuales(pr_mensual)

