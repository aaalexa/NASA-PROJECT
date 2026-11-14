"""Tests de integración de la API FastAPI (OPeNDAP en memoria RAM sin archivos en disco)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import xarray as xr
from fastapi.testclient import TestClient

from core.api.app import crear_app
from motor.datos import guardar_en_memoria
from motor.tendencias import CLAVES_SALIDA


def _cliente() -> TestClient:
    return TestClient(crear_app())


def test_salud_catalogo_y_consulta_opendap(dir_datos_temporal):
    c = _cliente()
    r_raiz = c.get("/")
    assert r_raiz.status_code == 200
    assert r_raiz.json()["modo_acceso"] == "opendap_memoria_sin_archivos"
    assert set(r_raiz.json()["datasets"]) == {"gpcp", "merra2", "gldas", "imerg"}

    r_salud = c.get("/api/v1/salud")
    assert r_salud.status_code == 200
    datos_salud = r_salud.json()
    assert datos_salud["estado"] == "ok"
    assert datos_salud["almacenamiento_disco"] is False
    assert datos_salud["n_datasets"] == 4

    r_cat = c.get("/api/v1/catalogo")
    assert r_cat.status_code == 200
    cat = r_cat.json()
    assert len(cat["datasets"]) == 4
    assert any(v["id"] == "lluvia_gpcp" for v in cat["variables"])
    assert "down_to_earth" in cat

    # Inspección de consulta OPeNDAP (índices espaciales y expresiones DAP4/DAP2)
    r_dap = c.get("/api/v1/opendap/consulta", params={"variable": "lluvia_imerg_mes", "region": "sahel"})
    assert r_dap.status_code == 200
    dap_json = r_dap.json()
    assert dap_json["almacenamiento_disco"] is False
    assert "/Grid/precipitation[0:1:0]" in dap_json["ejemplo_url_dap4"]
    assert "Grid_precipitation[0:1:0]" in dap_json["ejemplo_url_dap2"]


def test_endpoints_datasets_variables_y_regiones(dir_datos_temporal):
    c = _cliente()
    for did, sn in (("gpcp", "GPCPMON"), ("merra2", "M2TMNXFLX"), ("imerg", "GPM_3IMERGM")):
        r = c.get(f"/api/v1/datasets/{did}")
        assert r.status_code == 200
        assert sn in r.json()["short_names"]
        assert r.json()["protocolo_acceso"] == "opendap"

    assert c.get("/api/v1/datasets/inexistente").status_code == 404

    r_vars = c.get("/api/v1/variables", params={"fuente": "merra2", "solo_analizables": True})
    assert r_vars.status_code == 200
    ids_merra = {v["id"] for v in r_vars.json()["variables"]}
    assert ids_merra == {"lluvia_merra2", "temp_aire", "vapor_agua"}

    r_det = c.get("/api/v1/variables/lluvia_imerg_mes")
    assert r_det.status_code == 200
    assert r_det.json()["unidad_final"] == "mm/dia"
    assert r_det.json()["conversion"] == {"op": "factor", "valor": 24}

    r_reg = c.get("/api/v1/regiones/noreste_mexico")
    assert r_reg.status_code == 200
    reg_json = r_reg.json()
    assert len(reg_json["bbox"]) == 4
    assert reg_json["zona"] == "mexico"
    assert reg_json["es_latinoamerica"] is True
    assert reg_json["coordenadas"]["centro"] == {"lat": 26.0, "lon": -101.5}
    assert "gpcp" in reg_json["mallas_reales"]
    assert "gldas" in reg_json["mallas_reales"]
    assert reg_json["shortcut"]["query_region"] == "?region=noreste_mexico"

    r_mex = c.get("/api/v1/regiones", params={"zona": "mexico"})
    assert r_mex.status_code == 200
    assert r_mex.json()["total"] >= 8
    assert all(r["zona"] == "mexico" for r in r_mex.json()["regiones"])

    r_ca = c.get("/api/v1/regiones", params={"zona": "centroamerica"})
    assert r_ca.status_code == 200
    assert r_ca.json()["total"] >= 6
    assert any(r["id"] == "corredor_seco_centroamericano" for r in r_ca.json()["regiones"])

    r_bbox_calc = c.get(
        "/api/v1/regiones/calcular-bbox",
        params={"oeste": -92.2, "sur": 11.5, "este": -85.0, "norte": 16.0, "nombre": "Corredor Seco"},
    )
    assert r_bbox_calc.status_code == 200
    assert r_bbox_calc.json()["coordenadas"]["centro"] == {"lat": 13.75, "lon": -88.6}


def test_series_y_tendencias_desde_memoria_ram(dir_datos_temporal, serie_ar1):
    """Guarda un cubo en la caché en memoria RAM (0 archivos en disco) y verifica /series, /tendencias y /cache."""
    fechas = pd.date_range("2005-01-01", "2024-12-01", freq="MS")
    _, y = serie_ar1(len(fechas), -0.025, 0.3, sigma=1.0, semilla=99)
    ciclo = 10.0 * np.sin(2.0 * np.pi * fechas.month.values / 12.0)
    serie_base = 80.0 + ciclo + y
    cubo = xr.DataArray(
        np.broadcast_to(serie_base[:, None, None], (len(fechas), 2, 2)).copy(),
        coords={"time": fechas, "lat": [12.0, 16.0], "lon": [0.0, 10.0]},
        dims=("time", "lat", "lon"),
        name="lluvia_gpcp",
        attrs={"units": "mm/mes"},
    )
    guardar_en_memoria(cubo, "lluvia_gpcp", "sahel", "2005-01", "2024-12")
    assert len(list(dir_datos_temporal.glob("*"))) == 0  # 0 archivos en disco

    c = _cliente()
    r_cache = c.get("/api/v1/cache")
    assert r_cache.status_code == 200
    assert r_cache.json()["almacenamiento_disco"] is False
    assert r_cache.json()["total"] == 1

    r_serie = c.get(
        "/api/v1/series/lluvia_gpcp",
        params={"region": "sahel", "inicio": "2005-01", "fin": "2024-12"},
    )
    assert r_serie.status_code == 200
    s_json = r_serie.json()
    assert s_json["fuente_datos"] == "opendap_memoria"
    assert s_json["unidad"] == "mm/mes"
    assert len(s_json["puntos"]) == 240
    assert len(s_json["climatologia_mensual"]) == 12
    json.dumps(s_json, allow_nan=False)

    r_tend = c.get(
        "/api/v1/tendencias/lluvia_gpcp",
        params={"region": "sahel", "inicio": "2005-01", "fin": "2024-12"},
    )
    assert r_tend.status_code == 200
    t_json = r_tend.json()
    assert tuple(t_json["tendencia"].keys()) == CLAVES_SALIDA
    assert t_json["tendencia"]["veredicto"] == "significativo"
    assert t_json["tendencia"]["direccion"] == "baja"
    json.dumps(t_json, allow_nan=False)

    # Si se consulta una región no cargada en RAM con descargar=false, devuelve 404 con sugerencia OPeNDAP
    r_404 = c.get(
        "/api/v1/tendencias/lluvia_gpcp",
        params={"region": "amazonia", "inicio": "2005-01", "fin": "2024-12"},
    )
    assert r_404.status_code == 404
    assert r_404.json()["error"] == "datos_no_disponibles_en_memoria"

    r_del = c.delete("/api/v1/cache")
    assert r_del.status_code == 200
    assert r_del.json()["eliminadas_cubos"] == 1


def test_indicadores_escaner_dos_caras_y_mapa_modo_sintetico(dir_datos_temporal):
    c = _cliente()

    r_ind = c.get(
        "/api/v1/indicadores",
        params={"region": "sahel", "inicio": "2015-01", "fin": "2024-12", "sintetico": True},
    )
    assert r_ind.status_code == 200
    ind_json = r_ind.json()
    assert set(ind_json["indicadores"].keys()) == {
        "cdd_imerg",
        "r20mm_imerg",
        "dias_humedos_imerg",
        "prcptot_imerg",
        "sdii_imerg",
    }
    assert "dos_caras_extremos" in ind_json
    json.dumps(ind_json, allow_nan=False)

    r_esc = c.post(
        "/api/v1/escaner",
        json={
            "region": "sahel",
            "inicio": "2005-01",
            "fin": "2024-12",
            "variables": ["lluvia_gpcp", "lluvia_merra2", "temp_aire", "lluvia_imerg_mes"],
            "sintetico": True,
        },
    )
    assert r_esc.status_code == 200
    esc_json = r_esc.json()
    assert len(esc_json["resultados"]) == 4
    json.dumps(esc_json, allow_nan=False)

    r_dc = c.post(
        "/api/v1/dos-caras",
        json={
            "variable": "lluvia_gpcp",
            "region_a": "sahel",
            "region_b": "sureste_mexico",
            "inicio": "2005-01",
            "fin": "2024-12",
            "sintetico": True,
        },
    )
    assert r_dc.status_code == 200
    dc_json = r_dc.json()
    assert dc_json["signo_opuesto"] is True
    assert "dos_caras" in dc_json
    json.dumps(dc_json, allow_nan=False)

    r_mapa = c.get(
        "/api/v1/mapas/lluvia_gpcp",
        params={"region": "noreste_mexico", "inicio": "2010-01", "fin": "2024-12", "sintetico": True},
    )
    assert r_mapa.status_code == 200
    mapa_json = r_mapa.json()
    assert len(mapa_json["lat"]) == len(mapa_json["pendiente_decada"])
    assert len(mapa_json["lon"]) == len(mapa_json["pendiente_decada"][0])
    json.dumps(mapa_json, allow_nan=False)
