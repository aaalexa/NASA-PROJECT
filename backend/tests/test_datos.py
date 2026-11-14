"""Tests de motor/datos.py: OPeNDAP en memoria RAM sin almacenar archivos NetCDF/HDF en disco."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from core.config import DIR_RECURSOS
from motor.catalogo import cargar_catalogo
from motor.datos import (
    DatosNoDisponibles,
    abrir_bytes_netcdf_en_memoria,
    buscar_en_memoria,
    clave_cache_memoria,
    construir_url_opendap_subset,
    extraer_url_opendap,
    guardar_en_memoria,
    indices_bbox_grilla,
    leer_granulo_opendap,
    limpiar_cache_memoria,
    meses_por_anio,
    normalizar_coordenadas,
    normalizar_tiempo,
    obtener_variable,
    recortar_bbox,
    serializar_netcdf_en_memoria,
)


def test_clave_cache_memoria_y_extraccion_url_opendap():
    assert clave_cache_memoria("lluvia_gpcp", "Noreste Mexico", "1983-01", "2024-12") == (
        "lluvia_gpcp_noreste_mexico_1983-01_2024-12"
    )
    granulo_umm = {
        "umm": {
            "RelatedUrls": [
                {
                    "Type": "USE SERVICE API",
                    "Subtype": "OPENDAP DATA",
                    "URL": "https://data.gesdisc.earthdata.nasa.gov/opendap/GPCP/GPCPMON.3.3/2020/GPCPMON_L3_202001_V3.3.nc4.html",
                }
            ]
        }
    }
    assert extraer_url_opendap(granulo_umm) == (
        "https://data.gesdisc.earthdata.nasa.gov/opendap/GPCP/GPCPMON.3.3/2020/GPCPMON_L3_202001_V3.3.nc4"
    )
    assert extraer_url_opendap(
        "https://goldsmr4.gesdisc.eosdis.nasa.gov/data/MERRA2_MONTHLY/M2TMNXFLX.5.12.4/2020/MERRA2.nc4"
    ) == "https://goldsmr4.gesdisc.eosdis.nasa.gov/opendap/MERRA2_MONTHLY/M2TMNXFLX.5.12.4/2020/MERRA2.nc4"


def test_construir_url_opendap_subset_gpcp_merra2_e_imerg():
    cat = cargar_catalogo(DIR_RECURSOS / "catalogo.yaml")
    bbox = (-20.0, 10.0, 40.0, 20.0)  # Sahel

    # 1. GPCP (malla 0.5°, variable en raíz, orden time, lat, lon)
    u_gpcp = construir_url_opendap_subset(
        "https://data.gesdisc.earthdata.nasa.gov/opendap/GPCP/GPCPMON.3.3/2020/GPCP.nc4",
        cat["lluvia_gpcp"],
        bbox,
        protocolo="dap4",
    )
    assert ".dap.nc4?dap4.ce=/sat_gauge_precip[0:1:0][200:1:219][320:1:439]" in u_gpcp

    # 2. IMERG mensual (grupo Grid y orden time, lon, lat)
    u_imerg_dap4 = construir_url_opendap_subset(
        "https://gpm1.gesdisc.eosdis.nasa.gov/opendap/GPM_L3/GPM_3IMERGM.07/2020/IMERG.HDF5",
        cat["lluvia_imerg_mes"],
        bbox,
        protocolo="dap4",
    )
    assert "/Grid/precipitation[0:1:0][1600:1:2199][1000:1:1099]" in u_imerg_dap4

    u_imerg_dap2 = construir_url_opendap_subset(
        "https://gpm1.gesdisc.eosdis.nasa.gov/opendap/GPM_L3/GPM_3IMERGM.07/2020/IMERG.HDF5",
        cat["lluvia_imerg_mes"],
        bbox,
        protocolo="dap2",
    )
    assert ".nc4?Grid_precipitation[0:1:0][1600:1:2199][1000:1:1099]" in u_imerg_dap2

    lat_s, lon_s = indices_bbox_grilla(cat["lluvia_merra2"]["grilla"], bbox)
    assert lat_s == (200, 220)
    assert lon_s == (256, 352)


def test_abrir_bytes_netcdf_en_memoria_y_leer_granulo_opendap(dir_datos_temporal):
    cat = cargar_catalogo(DIR_RECURSOS / "catalogo.yaml")
    fechas = pd.to_datetime(["2020-01-01"])
    da_orig = xr.DataArray(
        np.full((1, 4, 3), 0.5, dtype=np.float32),
        coords={"time": fechas, "lon": [0.0, 5.0, 10.0, 15.0], "lat": [18.0, 14.0, 10.0]},
        dims=("time", "lon", "lat"),
        name="precipitation",
        attrs={"units": "mm/hr"},
    )
    # Serializar en memoria con grupo HDF5 "Grid" (0 archivos en disco)
    payload_bytes = serializar_netcdf_en_memoria(da_orig, grupo="Grid")
    assert len(list(dir_datos_temporal.glob("*"))) == 0

    class _RespuestaMock:
        status_code = 200
        content = payload_bytes

    class _SesionMock:
        def __init__(self):
            self.urls_pedidas: list[str] = []

        def get(self, url: str, timeout: int = 60):
            self.urls_pedidas.append(url)
            return _RespuestaMock()

    sesion = _SesionMock()
    da_leido = leer_granulo_opendap(
        "https://gpm1.gesdisc.eosdis.nasa.gov/opendap/GPM_L3/GPM_3IMERGM.07/2020/IMERG.HDF5",
        cat["lluvia_imerg_mes"],
        (-5.0, 10.0, 20.0, 20.0),
        sesion=sesion,
    )
    assert len(sesion.urls_pedidas) == 1
    assert ".dap.nc4?dap4.ce=/Grid/precipitation" in sesion.urls_pedidas[0]
    assert da_leido.dims == ("time", "lat", "lon")
    np.testing.assert_allclose(da_leido["lat"].values, [10.0, 14.0, 18.0])
    assert float(da_leido.mean()) == pytest.approx(0.5)
    # Ningún archivo escrito en disco
    assert len(list(dir_datos_temporal.glob("*"))) == 0


def test_normalizar_coordenadas_lon_360_lat_desc_y_orden_dims():
    t = pd.to_datetime(["2001-01-01", "2001-02-01"])
    datos = np.arange(2 * 4 * 3, dtype=float).reshape((2, 4, 3))
    da = xr.DataArray(
        datos,
        dims=("time", "longitude", "latitude"),
        coords={"time": t, "longitude": [0.0, 90.0, 180.0, 270.0], "latitude": [10.0, 0.0, -10.0]},
        attrs={"units": "mm/dia"},
    )
    norm = normalizar_coordenadas(da)
    assert norm.dims == ("time", "lat", "lon")
    np.testing.assert_allclose(norm["lat"].values, [-10.0, 0.0, 10.0])
    np.testing.assert_allclose(norm["lon"].values, [-180.0, -90.0, 0.0, 90.0])
    assert float(norm.sel(lon=-90.0, lat=10.0).isel(time=0)) == float(
        da.sel(longitude=270.0, latitude=10.0).isel(time=0)
    )


def test_normalizar_tiempo_mensual_con_offset_merra2():
    fechas = pd.to_datetime(["2020-01-01 00:30:00", "2020-02-01 00:30:00"])
    da = xr.DataArray([1.0, 2.0], coords={"time": fechas}, dims=("time",))
    norm = normalizar_tiempo(da, "mensual")
    assert list(pd.DatetimeIndex(norm["time"].values).strftime("%Y-%m-%d")) == ["2020-01-01", "2020-02-01"]


def test_recortar_bbox_normal_antimeridiano_y_celda_cercana():
    da = xr.DataArray(
        np.ones((3, 4)),
        coords={"lat": [-10.0, 0.0, 10.0], "lon": [-170.0, -10.0, 10.0, 170.0]},
        dims=("lat", "lon"),
    )
    sub = recortar_bbox(da, (-20.0, -5.0, 20.0, 15.0))
    assert list(sub["lat"].values) == [0.0, 10.0]
    assert list(sub["lon"].values) == [-10.0, 10.0]

    anti = recortar_bbox(da, (160.0, -15.0, -160.0, 15.0))
    assert list(anti["lon"].values) == [170.0, -170.0]

    puntual = recortar_bbox(da, (1.0, 1.0, 2.0, 2.0), minimo_una_celda=True)
    assert puntual.sizes == {"lat": 1, "lon": 1}
    with pytest.raises(ValueError, match="ningún centro"):
        recortar_bbox(da, (1.0, 1.0, 2.0, 2.0), minimo_una_celda=False)


def test_cache_memoria_exige_units_reutiliza_subrango_y_no_toca_la_red(dir_datos_temporal, monkeypatch):
    import earthaccess

    def _prohibido(*_a, **_kw):
        raise AssertionError("No debe llamarse a earthaccess cuando el cubo ya está en memoria RAM")

    monkeypatch.setattr(earthaccess, "search_data", _prohibido)

    cat = cargar_catalogo(DIR_RECURSOS / "catalogo.yaml")
    tiempos = pd.date_range("2020-01-01", "2021-12-01", freq="MS")
    da_sin_unidad = xr.DataArray(
        np.ones((24, 2, 2)),
        coords={"time": tiempos, "lat": [10.0, 11.0], "lon": [0.0, 1.0]},
        dims=("time", "lat", "lon"),
    )
    with pytest.raises(ValueError, match="units"):
        guardar_en_memoria(da_sin_unidad, "lluvia_gpcp", "sahel", "2020-01", "2021-12")

    da = da_sin_unidad.copy()
    da.attrs["units"] = "mm/mes"
    guardar_en_memoria(da, "lluvia_gpcp", "sahel", "2020-01", "2021-12")

    # Lectura exacta y lectura de subperiodo (2020-06..2020-12) directamente desde RAM
    leido = obtener_variable("lluvia_gpcp", "sahel", (-20.0, 10.0, 40.0, 20.0), "2020-06", "2020-12", cat)
    assert leido.attrs["units"] == "mm/mes"
    assert leido.sizes["time"] == 7

    with pytest.raises(DatosNoDisponibles):
        obtener_variable("lluvia_gpcp", "amazonia", (-75.0, -15.0, -45.0, 5.0), "2020-01", "2020-12", cat)

    assert limpiar_cache_memoria("lluvia_gpcp") == 1
    assert buscar_en_memoria("lluvia_gpcp", "sahel", "2020-01", "2021-12") is None


def test_meses_por_anio():
    assert meses_por_anio("2001-03", "2003-08") == [
        ("2001-03", "2001-12"),
        ("2002-01", "2002-12"),
        ("2003-01", "2003-08"),
    ]


def test_hilos_concurrentes_no_emiten_hdf5_diag_en_stderr(capfd):
    """Verifica que abrir_bytes_netcdf_en_memoria en hilos trabajadores no imprima HDF5-DIAG en stderr (fd 2)."""
    from concurrent.futures import ThreadPoolExecutor

    cat = cargar_catalogo(DIR_RECURSOS / "catalogo.yaml")
    da = xr.DataArray(
        np.ones((1, 4, 4), dtype=np.float32),
        coords={
            "time": pd.to_datetime(["2020-01-01"]),
            "lat": [10.0, 12.0, 14.0, 16.0],
            "lon": [0.0, 2.0, 4.0, 6.0],
        },
        dims=("time", "lat", "lon"),
        name="sat_gauge_precip",
    )
    payload = serializar_netcdf_en_memoria(da)

    # Limpiar buffer previo de stderr C
    capfd.readouterr()

    with ThreadPoolExecutor(max_workers=6) as pool:
        futuros = [
            pool.submit(abrir_bytes_netcdf_en_memoria, payload, cat["lluvia_gpcp"], (-5.0, 9.0, 10.0, 18.0))
            for _ in range(18)
        ]
        resultados = [f.result() for f in futuros]

    capturado = capfd.readouterr()
    assert "HDF5-DIAG" not in capturado.err
    assert "opendap_response.nc" not in capturado.err
    assert len(resultados) == 18
    assert resultados[0].dims == ("time", "lat", "lon")


def test_rechaza_html_o_error_opendap_y_soporta_netcdf3_classic(capfd):
    """Rechaza respuestas HTML/DAP inválidas sin tocar HDF5 y abre binarios NetCDF-3 classic en memoria."""
    import io
    from scipy.io import netcdf_file

    cat = cargar_catalogo(DIR_RECURSOS / "catalogo.yaml")
    capfd.readouterr()

    with pytest.raises(RuntimeError, match="no devolvió un binario NetCDF/HDF5 válido"):
        abrir_bytes_netcdf_en_memoria(
            b"<!DOCTYPE html><html><body>Earthdata Login Redirect</body></html>",
            cat["lluvia_gpcp"],
        )

    with pytest.raises(RuntimeError, match="vacía o truncada"):
        abrir_bytes_netcdf_en_memoria(b"", cat["lluvia_gpcp"])

    # Verificar también apertura de NetCDF-3 classic (CDF\x01) en memoria
    buf = io.BytesIO()
    nc3 = netcdf_file(buf, "w", version=1)
    nc3.createDimension("time", 1)
    nc3.createDimension("lat", 2)
    nc3.createDimension("lon", 2)
    vt = nc3.createVariable("time", "d", ("time",))
    vt.units = "days since 1970-01-01 00:00:00"
    vt[:] = [18262.0]  # 2020-01-01
    vlat = nc3.createVariable("lat", "d", ("lat",))
    vlat[:] = [10.0, 12.0]
    vlon = nc3.createVariable("lon", "d", ("lon",))
    vlon[:] = [0.0, 2.0]
    vp = nc3.createVariable("sat_gauge_precip", "f", ("time", "lat", "lon"))
    vp[:] = np.full((1, 2, 2), 3.5, dtype=np.float32)
    nc3.flush()
    bytes_cdf1 = buf.getvalue()
    nc3.close()

    da_nc3 = abrir_bytes_netcdf_en_memoria(bytes_cdf1, cat["lluvia_gpcp"])
    assert da_nc3.dims == ("time", "lat", "lon")
    assert float(da_nc3.mean()) == pytest.approx(3.5)

    capturado = capfd.readouterr()
    assert "HDF5-DIAG" not in capturado.err


def test_autodescubrimiento_coordenadas_gpcp_lat_descendente_y_lon_0_360():
    """Simula un servidor OPeNDAP con lat descendente (89.75 → -89.75) y lon en 0..360 (0.25 → 359.75).

    Verifica que para Sahel (-20, 10, 40, 20):
    1. El intento inicial con índices estáticos [200:219][320:439] es rechazado por caer fuera del bbox.
    2. `leer_granulo_opendap` consulta `/lat;/lon`, descubre la orientación real del servidor y divide la
       consulta de longitud en 2 segmentos contiguos [(0, 79), (680, 719)] con lat_slice=(140, 159).
    3. Devuelve el cubo (1, 20, 120) con lat=[10.25..19.75] y lon=[-19.75..39.75] listo para `series.recortar_bbox`.
    """
    import re
    from motor.datos import _CACHE_COORDENADAS_OPENDAP
    from motor.series import recortar_bbox as recortar_bbox_series

    _CACHE_COORDENADAS_OPENDAP.clear()
    cat = cargar_catalogo(DIR_RECURSOS / "catalogo.yaml")
    bbox_sahel = (-20.0, 10.0, 40.0, 20.0)

    lat_servidor = np.linspace(89.75, -89.75, 360)  # descendente (Norte → Sur)
    lon_servidor = np.linspace(0.25, 359.75, 720)   # 0..360
    fechas = pd.to_datetime(["2020-01-01"])

    class _RespMock:
        def __init__(self, content: bytes, status_code: int = 200):
            self.content = content
            self.status_code = status_code

    class _ServidorOPeNDAPRealista:
        def __init__(self):
            self.urls: list[str] = []

        def get(self, url: str, timeout: int = 60):
            self.urls.append(url)
            if "dap4.ce=/lat;/lon" in url:
                # Devuelve únicamente vectores 1-D lat y lon del servidor
                da_dummy = xr.DataArray(
                    np.zeros((1, 360, 720), dtype=np.float32),
                    coords={"time": fechas, "lat": lat_servidor, "lon": lon_servidor},
                    dims=("time", "lat", "lon"),
                    name="sat_gauge_precip",
                )
                return _RespMock(serializar_netcdf_en_memoria(da_dummy))

            m = re.search(r"sat_gauge_precip\[0:1:0\]\[(\d+):1:(\d+)\]\[(\d+):1:(\d+)\]", url)
            assert m is not None, f"URL inesperada: {url}"
            la0, la1, lo0, lo1 = (int(g) for g in m.groups())
            sub_lat = lat_servidor[la0 : la1 + 1]
            sub_lon = lon_servidor[lo0 : lo1 + 1]
            da_sub = xr.DataArray(
                np.full((1, sub_lat.size, sub_lon.size), 2.5, dtype=np.float32),
                coords={"time": fechas, "lat": sub_lat, "lon": sub_lon},
                dims=("time", "lat", "lon"),
                name="sat_gauge_precip",
                attrs={"units": "mm/day"},
            )
            return _RespMock(serializar_netcdf_en_memoria(da_sub))

    servidor = _ServidorOPeNDAPRealista()
    da = leer_granulo_opendap(
        "https://data.gesdisc.earthdata.nasa.gov/opendap/GPCP/GPCPMON.3.3/2020/GPCPMON_L3_202001_V3.3.nc4",
        cat["lluvia_gpcp"],
        bbox_sahel,
        sesion=servidor,
    )
    # Comprobar que el cubo devuelto cubre exactamente Sahel y pasa `series.recortar_bbox` sin error
    recortado = recortar_bbox_series(da, bbox_sahel)
    assert recortado.shape == (1, 20, 120)
    assert float(recortado["lat"].min()) == pytest.approx(10.25)
    assert float(recortado["lat"].max()) == pytest.approx(19.75)
    assert float(recortado["lon"].min()) == pytest.approx(-19.75)
    assert float(recortado["lon"].max()) == pytest.approx(39.75)
    _CACHE_COORDENADAS_OPENDAP.clear()


@pytest.mark.red
def test_colecciones_en_cmr():
    import earthaccess

    cat = cargar_catalogo(DIR_RECURSOS / "catalogo.yaml")
    vistos = set()
    for e in cat.values():
        sn = e.get("short_name")
        if not sn or sn in vistos:
            continue
        vistos.add(sn)
        cols = earthaccess.search_datasets(short_name=sn, version=e.get("version"))
        assert len(cols) >= 1, f"{sn} v{e.get('version')} no encontrado en CMR"
