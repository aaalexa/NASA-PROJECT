"""Tests de motor/catalogo.py (skills catalogo-variables y validacion-y-pruebas)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from core.config import DIR_RECURSOS
from motor.catalogo import (
    aplicar_rango_valido,
    cambiar_unidad,
    cargar_catalogo,
    cargar_datasets,
    convertir,
    variables_por_grupo,
)

RUTA_CATALOGO = DIR_RECURSOS / "catalogo.yaml"


def test_cargar_catalogo_y_datasets_oficiales():
    cat = cargar_catalogo(RUTA_CATALOGO)
    ds = cargar_datasets(RUTA_CATALOGO)
    assert set(ds.keys()) == {"gpcp", "merra2", "imerg"}
    esperadas = {
        "lluvia_gpcp",
        "lluvia_merra2",
        "temp_aire",
        "vapor_agua",
        "lluvia_imerg_mes",
        "lluvia_imerg_dia",
        "cdd_imerg",
        "r20mm_imerg",
        "dias_humedos_imerg",
        "prcptot_imerg",
        "sdii_imerg",
    }
    assert esperadas.issubset(cat.keys())
    assert "lluvia_gpcp" in variables_por_grupo(cat, "lluvia")
    assert "temp_aire" in variables_por_grupo(cat, "causa")
    assert "cdd_imerg" in variables_por_grupo(cat, "calculada")


def test_validacion_acumula_todos_los_errores(tmp_path: Path):
    """Un YAML con campo faltante, unidad desconocida, op desconocida e id repetido enumera los 4 problemas."""
    yaml_malo = tmp_path / "malo.yaml"
    yaml_malo.write_text(
        """
variables:
  - id: lluvia_gpcp
    grupo: lluvia
    nombre_simple: Lluvia
    definicion_simple: Def
    dataset: GPCP
    short_name: GPCPMON
    variable: sat_gauge_precip
    unidad_original: mm/dia
    conversion: {op: dias_del_mes}
    desde: "1983-01"
    resolucion: 0.5°
    frecuencia: mensual
  - id: temp_aire
    grupo: causa
    nombre_simple: Temp
    definicion_simple: Def
    dataset: MERRA2
    short_name: M2TMNXSLV
    variable: T2M
    unidad_original: Kelvin
    conversion: {op: magia}
    unidad_final: degC
    desde: "1980-01"
    resolucion: 0.5°
    frecuencia: mensual
  - id: lluvia_gpcp
    grupo: lluvia
    nombre_simple: Repetida
    definicion_simple: Def
    dataset: GPCP
    short_name: GPCPMON
    variable: sat_gauge_precip
    unidad_original: mm/dia
    conversion: {op: ninguna}
    unidad_final: mm/dia
    desde: "1983-01"
    resolucion: 0.5°
    frecuencia: mensual
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as info:
        cargar_catalogo(yaml_malo)
    msg = str(info.value)
    assert "falta 'unidad_final'" in msg
    assert "Kelvin" in msg
    assert "magia" in msg
    assert "id repetido" in msg


def test_conversion_dias_del_mes_bisiesto_y_normal():
    """2.0 mm/dia en 2023-02 (28d), 2024-02 (29d bisiesto) y 2024-01 (31d) → 56, 58 y 62 mm/mes."""
    cat = cargar_catalogo(RUTA_CATALOGO)
    tiempos = pd.to_datetime(["2023-02-01", "2024-02-01", "2024-01-01"])
    da = xr.DataArray([2.0, 2.0, 2.0], coords={"time": tiempos}, dims=("time",), attrs={"units": "mm/day"})
    conv = convertir(da, cat["lluvia_gpcp"])
    np.testing.assert_allclose(conv.values, [56.0, 58.0, 62.0], rtol=1e-12)
    assert conv.attrs["units"] == "mm/mes"
    assert conv.attrs["units_archivo"] == "mm/day"
    assert da.attrs["units"] == "mm/day"  # no modifica la entrada


@pytest.mark.parametrize(
    ("entrada_spec", "valor_in", "valor_esperado", "unidad_esperada"),
    [
        # Valores de referencia de .claude/skills/catalogo-variables/referencia.md §3
        ({"id": "lluvia_merra2", "conversion": {"op": "factor", "valor": 86400}, "unidad_final": "mm/dia"}, 1e-4, 8.64, "mm/dia"),
        ({"id": "lluvia_imerg_mes", "conversion": {"op": "factor", "valor": 24}, "unidad_final": "mm/dia"}, 0.5, 12.0, "mm/dia"),
        ({"id": "lluvia_imerg_dia", "conversion": {"op": "ninguna"}, "unidad_final": "mm/dia"}, 7.3, 7.3, "mm/dia"),
        ({"id": "temp_aire", "conversion": {"op": "suma", "valor": -273.15}, "unidad_final": "degC"}, 300.0, 26.85, "degC"),
        ({"id": "vapor_agua", "conversion": {"op": "ninguna"}, "unidad_final": "mm"}, 25.0, 25.0, "mm"),
        ({"id": "humedad_suelo", "conversion": {"op": "ninguna"}, "unidad_final": "mm"}, 30.0, 30.0, "mm"),
        ({"id": "evaporacion", "conversion": {"op": "factor", "valor": 86400}, "unidad_final": "mm/dia"}, 2e-5, 1.728, "mm/dia"),
        ({"id": "escorrentia", "conversion": {"op": "factor", "valor": 8}, "unidad_final": "mm/dia"}, 1.5, 12.0, "mm/dia"),
        ({"id": "ndvi", "conversion": {"op": "factor", "valor": 0.0001}, "unidad_final": "1"}, 5000.0, 0.5, "1"),
        ({"id": "poblacion", "conversion": {"op": "ninguna"}, "unidad_final": "personas"}, 1234.0, 1234.0, "personas"),
    ],
)
def test_conversiones_tabla_referencia(entrada_spec, valor_in, valor_esperado, unidad_esperada):
    da = xr.DataArray([valor_in], dims=("x",), attrs={"units": "raw"})
    out = convertir(da, entrada_spec)
    assert float(out.values[0]) == pytest.approx(valor_esperado, rel=1e-9)
    assert out.attrs["units"] == unidad_esperada


def test_conversion_clases_con_nan():
    entrada = {"id": "cultivos", "conversion": {"op": "clases", "valores": [12, 14]}, "unidad_final": "booleano"}
    da = xr.DataArray([10.0, 12.0, 14.0, 16.0, np.nan], dims=("x",))
    out = convertir(da, entrada)
    np.testing.assert_allclose(out.values[:4], [0.0, 1.0, 1.0, 0.0], rtol=1e-12)
    assert np.isnan(out.values[4])
    assert out.attrs["units"] == "booleano"


def test_rango_valido_y_cambiar_unidad():
    cat = cargar_catalogo(RUTA_CATALOGO)
    tiempos = pd.to_datetime(["2024-01-01", "2024-02-01"])
    da = xr.DataArray([-5.0, 2.0], coords={"time": tiempos}, dims=("time",), attrs={"units": "mm/dia"})
    filtrado = aplicar_rango_valido(da, cat["lluvia_gpcp"])
    assert np.isnan(filtrado.values[0]) and filtrado.values[1] == pytest.approx(2.0)

    en_mes = cambiar_unidad(filtrado, "mm/mes")
    assert en_mes.attrs["units"] == "mm/mes"
    assert en_mes.values[1] == pytest.approx(58.0)
    de_vuelta = cambiar_unidad(en_mes, "mm/dia")
    assert de_vuelta.attrs["units"] == "mm/dia"
    assert de_vuelta.values[1] == pytest.approx(2.0)
