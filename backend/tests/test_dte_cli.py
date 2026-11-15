"""Comando `nasa-project dte` sin red: descarga simulada, archivos de salida y nunca datos sintéticos."""
from __future__ import annotations

import json
import os

import pytest

from core.motor.datos import DatosNoDisponibles
from core.servicios import calculo_dte, consultas, dte_cli
from core.servicios.regiones import resolver_region


def _cubo_falso(variable, region, bbox, inicio, fin, catalogo, descargar=False):
    reg = resolver_region(region, None)
    return consultas._cubo_sintetico(variable, catalogo[variable], reg, inicio, fin)


def test_dte_real_escribe_salidas_sin_usar_sinteticos(tmp_path, monkeypatch, dir_datos_temporal):
    descargadas: list[str] = []
    monkeypatch.setattr(calculo_dte, "descargar_variable", lambda vid, *a, **k: descargadas.append(vid))
    monkeypatch.setattr(consultas, "obtener_variable", _cubo_falso)

    res = dte_cli.ejecutar_dte_real(region="sahel", bbox=None, salida=tmp_path, avisar=lambda _m: None)

    assert descargadas == ["lluvia_gpcp", "temp_aire", "humedad_suelo", "evapotranspiracion"]
    assert res["metadata"]["source"] == "opendap_memoria" and res["metadata"]["simulated"] is False
    for nombre in ("resultados.json", "mensual.csv", "anual.csv", "serie_regional.csv"):
        assert (tmp_path / nombre).is_file()
    json.loads((tmp_path / "resultados.json").read_text(encoding="utf-8"))
    lineas = (tmp_path / "serie_regional.csv").read_text(encoding="utf-8").strip().splitlines()
    assert lineas[0] == "fecha,P,T,SM,ET" and len(lineas) == 289
    assert res["metadata"]["trend_span"]["n_years"] == 24


def test_dte_real_no_rellena_con_sinteticos_si_falta_un_cubo(tmp_path, monkeypatch, dir_datos_temporal):
    monkeypatch.setattr(calculo_dte, "descargar_variable", lambda *a, **k: None)

    def _falla(variable, region, bbox, inicio, fin, catalogo, descargar=False):
        raise DatosNoDisponibles(variable, region, inicio, fin)

    monkeypatch.setattr(consultas, "obtener_variable", _falla)
    with pytest.raises(DatosNoDisponibles):
        dte_cli.ejecutar_dte_real(region="sahel", bbox=None, salida=tmp_path, avisar=lambda _m: None)
    assert not any(tmp_path.iterdir())


@pytest.mark.red
def test_dte_real_con_opendap(tmp_path, dir_datos_temporal):
    """Corrida real corta (3 años, caja pequeña). Requiere red y EARTHDATA_* (o backend/.env): `pytest -m red`."""
    dte_cli.cargar_env()
    if not (os.environ.get("EARTHDATA_USERNAME") and os.environ.get("EARTHDATA_PASSWORD")):
        pytest.skip("sin credenciales de Earthdata")
    res = dte_cli.ejecutar_dte_real(
        region=None, bbox=[-89.5, 13.5, -88.5, 14.5], inicio="2019-01", fin="2021-12", salida=tmp_path,
        avisar=lambda _m: None,
    )
    assert res["metadata"]["source"] == "opendap_memoria"
    for cod in ("P", "T", "SM", "ET"):
        assert res["variables"][cod]["quality"]["n_months_valid"] > 0
    assert (tmp_path / "serie_regional.csv").is_file()


def test_cargar_env_no_sobrescribe_y_no_devuelve_valores(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comentario\nDTE_PRUEBA_A=u$no!&\nDTE_PRUEBA_B='dos'\nDTE_PRUEBA_C=tres\n", encoding="utf-8")
    monkeypatch.setenv("DTE_PRUEBA_C", "ya_definida")
    monkeypatch.delenv("DTE_PRUEBA_A", raising=False)
    monkeypatch.delenv("DTE_PRUEBA_B", raising=False)
    cargadas = dte_cli.cargar_env(env)
    assert cargadas == ["DTE_PRUEBA_A", "DTE_PRUEBA_B"]
    assert os.environ["DTE_PRUEBA_A"] == "u$no!&"  # literal: sin expandir $ (contraseñas con caracteres especiales)
    assert os.environ["DTE_PRUEBA_B"] == "dos" and os.environ["DTE_PRUEBA_C"] == "ya_definida"
    monkeypatch.delenv("DTE_PRUEBA_A")
    monkeypatch.delenv("DTE_PRUEBA_B")
