"""Acceso a NASA Earthdata mediante OPeNDAP en memoria RAM sin almacenar archivos NetCDF/HDF en disco.

Flujo OPeNDAP + RAM:
    1. Busca los gránulos en el catálogo público CMR con `earthaccess.search_data`.
    2. Extrae el endpoint OPeNDAP (`https://.../opendap/...`) de cada gránulo.
    3. Construye la expresión de recorte en el servidor (OPeNDAP Constraint Expression DAP4 `.dap.nc4?dap4.ce=...`
       o DAP2 `.nc4?...`) solicitando únicamente la variable y los índices `[lat_i0:1:lat_i1]` y `[lon_i0:1:lon1]`
       del bounding box de la región.
    4. Descarga el subconjunto binario (unos pocos KB por paso de tiempo) directamente en un buffer de RAM y lo
       abre con `netCDF4.Dataset("mem.nc", mode="r", memory=bytes)` + `NetCDF4DataStore`, sin tocar el disco.
    5. Normaliza coordenadas `(time, lat, lon)`, convierte unidades a las finales del catálogo (`attrs["units"]`)
       y guarda el `xr.DataArray` recortado en una caché LRU en memoria RAM (`CACHE_MEMORIA`).
"""
from __future__ import annotations

import calendar
from collections import OrderedDict
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
import ctypes
from dataclasses import dataclass
from datetime import datetime, timezone
import io
import re
import threading
from typing import Any, Literal

import netCDF4
import numpy as np
import pandas as pd
import xarray as xr
from xarray.backends import NetCDF4DataStore

from core.config import obtener_ajustes
from core.motor.catalogo import aplicar_rango_valido, convertir

BBox = tuple[float, float, float, float]  # (oeste, sur, este, norte) en grados, lon en [-180, 180)
Progreso = Callable[[int, int, str], None]

_NOMBRES_LAT = ("lat", "latitude", "y", "Latitude", "nlat")
_NOMBRES_LON = ("lon", "longitude", "x", "Longitude", "nlon")
_RE_MES = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

_MAGIC_HDF5 = b"\x89HDF\r\n\x1a\n"
_MAGIC_CDF = (b"CDF\x01", b"CDF\x02", b"CDF\x05")
_LOCK_HDF5 = threading.Lock()
_TLS_HDF5 = threading.local()
_LOCK_COORDS = threading.Lock()
_CACHE_COORDENADAS_OPENDAP: dict[str, tuple[np.ndarray, np.ndarray]] = {}


def _silenciar_hdf5_hilo_actual() -> None:
    """Desactiva el volcado automático `HDF5-DIAG` en la pila de errores thread-local de HDF5.

    Cuando `netCDF4.Dataset("opendap_response.nc", mode="r", memory=...)` abre un buffer en RAM,
    `libnetcdf` invoca internamente `H5Fis_accessible("opendap_response.nc")` antes de leer la imagen
    en memoria. En el hilo principal `import netCDF4` silencia la pila de errores de HDF5, pero en
    HDF5 >= 2.0 la pila `H5E_DEFAULT` es local a cada hilo (`ThreadPoolExecutor` o hilos de FastAPI),
    por lo que es necesario llamar a `H5Eset_auto2(0, NULL, NULL)` en cada hilo trabajador.
    """
    if getattr(_TLS_HDF5, "silenciado", False):
        return
    try:
        proc = ctypes.CDLL(None)
        h5e_set_auto2 = getattr(proc, "H5Eset_auto2", None)
        if h5e_set_auto2 is not None:
            h5e_set_auto2.argtypes = [ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p]
            h5e_set_auto2.restype = ctypes.c_int
            h5e_set_auto2(0, None, None)
        _TLS_HDF5.silenciado = True
    except Exception:  # noqa: BLE001
        pass


def _validar_firma_netcdf(datos_bytes: bytes) -> Literal["hdf5", "cdf"]:
    """Verifica que el buffer binario tenga cabecera HDF5/NetCDF-4 o NetCDF-3/CDF5 válida."""
    if not datos_bytes or len(datos_bytes) < 8:
        raise RuntimeError(f"Respuesta OPeNDAP vacía o truncada ({len(datos_bytes or b'')} bytes).")
    if datos_bytes[:8] == _MAGIC_HDF5:
        return "hdf5"
    if datos_bytes[:4] in _MAGIC_CDF:
        return "cdf"
    muestra = datos_bytes[:400].decode("utf-8", errors="replace").strip()
    muestra = re.sub(r"\s+", " ", muestra)
    raise RuntimeError(
        "El servidor OPeNDAP no devolvió un binario NetCDF/HDF5 válido "
        f"(posible redirección HTML de Earthdata Login o error DAP): {muestra[:220]!r}"
    )


class DatosNoDisponibles(LookupError):
    """La variable no está en la caché en memoria (y se consultó con opendap/descargar=False)."""

    def __init__(self, variable: str, region: str, inicio: str, fin: str):
        self.variable, self.region, self.inicio, self.fin = variable, region, inicio, fin
        super().__init__(
            f"{variable} en '{region}' ({inicio} → {fin}) no está en la caché en memoria RAM. "
            "Pasa descargar=true para consultarla en vivo por OPeNDAP, envía POST /api/v1/descargas "
            "para precargarla en RAM, o usa ?sintetico=true en modo demo."
        )


# ----------------------------------------------------------------------------------------------- Validación
def validar_mes(valor: str, nombre: str = "fecha") -> str:
    """Comprueba el formato 'AAAA-MM' y lo devuelve."""
    if not isinstance(valor, str) or not _RE_MES.match(valor):
        raise ValueError(f"{nombre} debe tener formato AAAA-MM, no {valor!r}")
    return valor


def validar_periodo(inicio: str, fin: str) -> tuple[str, str]:
    validar_mes(inicio, "inicio")
    validar_mes(fin, "fin")
    if inicio > fin:
        raise ValueError(f"inicio ({inicio}) es posterior a fin ({fin})")
    return inicio, fin


def validar_bbox(bbox: Sequence[float]) -> BBox:
    """(oeste, sur, este, norte) con lon en [-180, 180] y sur < norte. oeste > este cruza el antimeridiano."""
    if len(bbox) != 4:
        raise ValueError("bbox debe tener 4 números: oeste, sur, este, norte")
    oeste, sur, este, norte = (float(v) for v in bbox)
    if not all(np.isfinite([oeste, sur, este, norte])):
        raise ValueError("bbox contiene valores no finitos")
    if not (-180 <= oeste <= 180 and -180 <= este <= 180):
        raise ValueError("las longitudes del bbox deben estar entre -180 y 180")
    if not (-90 <= sur < norte <= 90):
        raise ValueError("las latitudes del bbox deben cumplir -90 ≤ sur < norte ≤ 90")
    if oeste == este:
        raise ValueError("oeste y este no pueden ser iguales")
    return oeste, sur, este, norte


def slug_region(region: str) -> str:
    """Slug en minúsculas sin espacios ('Noreste México' → 'noreste_méxico')."""
    slug = re.sub(r"\s+", "_", region.strip().lower())
    if not slug or "/" in slug or "\\" in slug or slug.startswith("."):
        raise ValueError(f"nombre de región inválido: {region!r}")
    return slug


def slug_bbox(bbox: BBox) -> str:
    """Slug estable para una caja ad hoc: bbox_-10_10_20_20."""
    return "bbox_" + "_".join(f"{v:g}" for v in bbox)


def meses_por_anio(inicio: str, fin: str) -> list[tuple[str, str]]:
    """Parte [inicio, fin] en tramos de un año natural: [('2001-03','2001-12'), ('2002-01','2002-12'), ...]."""
    validar_periodo(inicio, fin)
    a0, a1 = int(inicio[:4]), int(fin[:4])
    tramos = []
    for anio in range(a0, a1 + 1):
        ini = inicio if anio == a0 else f"{anio}-01"
        fn = fin if anio == a1 else f"{anio}-12"
        tramos.append((ini, fn))
    return tramos


def _fin_de_mes(mes: str) -> str:
    anio, m = int(mes[:4]), int(mes[5:7])
    return f"{mes}-{calendar.monthrange(anio, m)[1]:02d}"


# ----------------------------------------------------------------------------------------------- Credenciales
def iniciar_sesion():
    """Inicia sesión en Earthdata con variables de entorno o .netrc. Nunca pide la contraseña ni la muestra."""
    import earthaccess

    for estrategia in ("environment", "netrc"):
        try:
            auth = earthaccess.login(strategy=estrategia)
        except Exception:  # noqa: BLE001 — una estrategia que falla no es un error todavía
            continue
        if auth is not None and getattr(auth, "authenticated", False):
            return auth
    raise RuntimeError(
        "No hay credenciales de Earthdata para conectar con OPeNDAP. "
        "Define EARTHDATA_USERNAME y EARTHDATA_PASSWORD o crea ~/.netrc con "
        "'machine urs.earthdata.nasa.gov login <usuario> password <clave>'."
    )


# ----------------------------------------------------------------------------------------------- Normalización
def normalizar_coordenadas(obj: xr.DataArray | xr.Dataset) -> xr.DataArray | xr.Dataset:
    """Deja dims (time, lat, lon), lat ascendente y lon en [-180, 180) ordenada. No cambia valores ni unidades."""
    renombres = {}
    for n in _NOMBRES_LAT:
        if n in obj.dims and n != "lat" and "lat" not in obj.dims:
            renombres[n] = "lat"
    for n in _NOMBRES_LON:
        if n in obj.dims and n != "lon" and "lon" not in obj.dims:
            renombres[n] = "lon"
    obj = obj.rename(renombres)
    if "lon" in obj.dims:
        lon = ((obj["lon"] + 180.0) % 360.0) - 180.0
        obj = obj.assign_coords(lon=lon).sortby("lon")
    if "lat" in obj.dims:
        obj = obj.sortby("lat")
    orden = [d for d in ("time", "lat", "lon") if d in obj.dims]
    resto = [d for d in obj.dims if d not in orden]
    if isinstance(obj, xr.Dataset):
        return obj.transpose(*orden, *resto, missing_dims="ignore")
    return obj.transpose(*orden, *resto)


def normalizar_tiempo(obj: xr.DataArray | xr.Dataset, frecuencia: str) -> xr.DataArray | xr.Dataset:
    """Fechas datetime64: día 1 de cada mes (mensual) o medianoche (diaria)."""
    if "time" not in obj.dims or frecuencia == "anual":
        return obj
    idx = obj.indexes["time"]
    if isinstance(idx, xr.CFTimeIndex):
        fechas = pd.DatetimeIndex([pd.Timestamp(t.year, t.month, t.day) for t in idx])
    else:
        fechas = pd.DatetimeIndex(idx)
    if fechas.tz is not None:
        fechas = fechas.tz_convert(None)
    fechas = fechas.to_period("M").to_timestamp() if frecuencia == "mensual" else fechas.normalize()
    obj = obj.assign_coords(time=fechas.astype("datetime64[ns]"))
    _, unicos = np.unique(obj["time"].values, return_index=True)
    if unicos.size != obj.sizes["time"]:
        obj = obj.isel(time=np.sort(unicos))
    return obj.sortby("time")


def _distancia_a_intervalo(valores: np.ndarray, minimo: float, maximo: float) -> float:
    """Distancia mínima en grados desde cualquier valor de `valores` al intervalo [minimo, maximo]."""
    arr = np.asarray(valores, dtype=np.float64)
    if arr.size == 0:
        return float("inf")
    if np.any((arr >= minimo) & (arr <= maximo)):
        return 0.0
    return float(np.min(np.minimum(np.abs(arr - minimo), np.abs(arr - maximo))))


def recortar_bbox(da: xr.DataArray | xr.Dataset, bbox: BBox, minimo_una_celda: bool = True):
    """Recorta a (oeste, sur, este, norte). Requiere coordenadas normalizadas. Soporta cruzar el antimeridiano."""
    oeste, sur, este, norte = bbox
    sub = da.sel(lat=slice(sur, norte))
    if oeste <= este:
        sub = sub.sel(lon=slice(oeste, este))
    else:
        sub = xr.concat([sub.sel(lon=slice(oeste, 180)), sub.sel(lon=slice(-180, este))], dim="lon")
    if sub.sizes.get("lat", 0) > 0 and sub.sizes.get("lon", 0) > 0:
        return sub
    if not minimo_una_celda:
        raise ValueError(f"la caja {bbox} no contiene ningún centro de celda de la malla")

    lats = np.asarray(da["lat"].values, dtype=np.float64)
    lons = np.asarray(da["lon"].values, dtype=np.float64)
    paso_lat = float(np.abs(np.diff(lats)).max()) if lats.size > 1 else 2.5
    paso_lon = float(np.abs(np.diff(lons)).max()) if lons.size > 1 else 2.5
    tol_lat = max(paso_lat * 1.5, 1.5)
    tol_lon = max(paso_lon * 1.5, 1.5)

    dist_lat = _distancia_a_intervalo(lats, sur, norte)
    if oeste <= este:
        dist_lon = _distancia_a_intervalo(lons, oeste, este)
    else:
        dist_lon = min(_distancia_a_intervalo(lons, oeste, 180.0), _distancia_a_intervalo(lons, -180.0, este))

    if dist_lat > tol_lat or dist_lon > tol_lon:
        raise ValueError(
            f"la caja {bbox} no contiene ningún centro de celda de la malla "
            f"(rango recibido: lat=[{lats.min():.2f}, {lats.max():.2f}], lon=[{lons.min():.2f}, {lons.max():.2f}])"
        )

    clat = (sur + norte) / 2.0
    clon = (oeste + este) / 2.0 if oeste <= este else ((oeste + este + 360.0) / 2.0 + 180.0) % 360.0 - 180.0
    ilat = int(np.abs(lats - clat).argmin())
    ilon = int(np.abs(lons - clon).argmin())
    return da.isel(lat=slice(ilat, ilat + 1), lon=slice(ilon, ilon + 1))


# ----------------------------------------------------------------------------------------------- OPeNDAP en memoria
def extraer_url_opendap(granulo: Any) -> str:
    """Obtiene la URL base de OPeNDAP de un gránulo CMR (o convierte un enlace HTTPS de GES DISC a /opendap/)."""
    if isinstance(granulo, str):
        url = granulo
        if "/data/" in url and "/opendap/" not in url and "gesdisc" in url:
            url = url.replace("/data/", "/opendap/", 1)
        return re.sub(r"\.html$", "", url)

    umm = granulo.get("umm", {}) if isinstance(granulo, dict) else {}
    for rel in umm.get("RelatedUrls", []):
        u = str(rel.get("URL", ""))
        subtipo = str(rel.get("Subtype", "")).upper()
        tipo = str(rel.get("Type", "")).upper()
        if ("OPENDAP" in subtipo or "/opendap/" in u.lower()) and u.startswith("http"):
            return re.sub(r"\.html$", "", u)
        if tipo == "USE SERVICE API" and "/opendap/" in u.lower():
            return re.sub(r"\.html$", "", u)

    enlaces = granulo.data_links(access="external") if hasattr(granulo, "data_links") else []
    for u in enlaces:
        if "/opendap/" in u:
            return re.sub(r"\.html$", "", u)
        if "/data/" in u and "gesdisc" in u:
            return u.replace("/data/", "/opendap/", 1)
    if enlaces:
        return str(enlaces[0])
    raise RuntimeError(f"El gránulo {umm.get('GranuleUR', granulo)} no expone una URL OPeNDAP ni HTTPS.")


def segmentos_indices_bbox_opendap(
    lat_1d: np.ndarray,
    lon_1d: np.ndarray,
    bbox: BBox,
) -> tuple[tuple[int, int], list[tuple[int, int]]]:
    """Calcula el slice de latitud y la lista de slices contiguos de longitud para OPeNDAP.

    Soporta mallas con latitud ascendente o descendente (`89.75 → -89.75` en GPCP) y longitudes tanto en
    `[-180, 180)` como en `[0, 360)` (dividiendo automáticamente en 2 segmentos contiguos cuando el bbox
    cruza la costura `0°/360°` o `-180°/180°` de la malla nativa del servidor).
    """
    oeste, sur, este, norte = validar_bbox(bbox)
    lat_arr = np.asarray(lat_1d, dtype=np.float64)
    lon_arr = np.asarray(lon_1d, dtype=np.float64)
    lon_norm = ((lon_arr + 180.0) % 360.0) - 180.0

    en_lat = np.flatnonzero((lat_arr >= sur) & (lat_arr <= norte))
    if en_lat.size == 0:
        cercano_lat = int(np.abs(lat_arr - (sur + norte) / 2.0).argmin())
        lat_slice = (cercano_lat, cercano_lat)
    else:
        lat_slice = (int(en_lat.min()), int(en_lat.max()))

    if oeste <= este:
        en_lon = np.flatnonzero((lon_norm >= oeste) & (lon_norm <= este))
    else:
        en_lon = np.flatnonzero((lon_norm >= oeste) | (lon_norm <= este))

    if en_lon.size == 0:
        clon = (oeste + este) / 2.0 if oeste <= este else ((oeste + este + 360.0) / 2.0 + 180.0) % 360.0 - 180.0
        cercano_lon = int(np.abs(lon_norm - clon).argmin())
        return lat_slice, [(cercano_lon, cercano_lon)]

    cortes = np.flatnonzero(np.diff(en_lon) > 1) + 1
    bloques = np.split(en_lon, cortes)
    lon_slices = [(int(b[0]), int(b[-1])) for b in bloques if b.size > 0]
    return lat_slice, lon_slices


def indices_bbox_opendap(
    lat_1d: np.ndarray,
    lon_1d: np.ndarray,
    bbox: BBox,
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Calcula los rangos de índices inclusivos ((lat_i0, lat_i1), (lon_i0, lon_i1)) para OPeNDAP [i0:1:i1]."""
    lat_slice, lon_slices = segmentos_indices_bbox_opendap(lat_1d, lon_1d, bbox)
    if len(lon_slices) == 1:
        return lat_slice, lon_slices[0]
    return lat_slice, (min(s[0] for s in lon_slices), max(s[1] for s in lon_slices))


def indices_bbox_grilla(grilla: dict[str, Any], bbox: BBox) -> tuple[tuple[int, int], tuple[int, int]]:
    """Calcula los índices OPeNDAP ((lat_i0, lat_i1), (lon_i0, lon_i1)) a partir de la grilla del catálogo."""
    n_lat = int(round((float(grilla["lat_max"]) - float(grilla["lat_min"])) / float(grilla["dlat"]))) + 1
    n_lon = int(round((float(grilla["lon_max"]) - float(grilla["lon_min"])) / float(grilla["dlon"]))) + 1
    lat_1d = np.linspace(float(grilla["lat_min"]), float(grilla["lat_max"]), n_lat)
    if grilla.get("lat_invertida"):
        lat_1d = lat_1d[::-1]
    lon_1d = np.linspace(float(grilla["lon_min"]), float(grilla["lon_max"]), n_lon)
    return indices_bbox_opendap(lat_1d, lon_1d, bbox)


def construir_url_opendap_subset(
    url_opendap: str,
    entrada: dict[str, Any],
    bbox: BBox | None = None,
    *,
    protocolo: Literal["dap4", "dap2"] = "dap4",
    lat_slice: tuple[int, int] | None = None,
    lon_slice: tuple[int, int] | None = None,
) -> str:
    """Construye la URL OPeNDAP con Constraint Expression (DAP4 `.dap.nc4?dap4.ce=...` o DAP2 `.nc4?...`).

    Recorta en el servidor la variable y las coordenadas `time`, `lat` y `lon` al bounding box indicado,
    respetando tanto el grupo HDF5 (`grupo_hdf: Grid` en IMERG mensual) como el orden de dimensiones
    (`(time, lon, lat)` en IMERG frente a `(time, lat, lon)` en GPCP y MERRA-2).
    """
    base = re.sub(r"\.(dap\.nc4|nc4|dods|dds|das|dmr|html)$", "", url_opendap)
    if url_opendap.endswith((".nc4", ".HDF5", ".hdf5", ".nc")):
        base = url_opendap

    grilla = entrada.get("grilla")
    if (lat_slice is None or lon_slice is None) and bbox is not None and grilla:
        lat_slice, lon_slice = indices_bbox_grilla(grilla, bbox)

    var = entrada["variable"]
    grupo = entrada.get("grupo_hdf")
    orden_dims = (grilla or {}).get("orden_dims", ["time", "lat", "lon"])

    s_lat = f"[{lat_slice[0]}:1:{lat_slice[1]}]" if lat_slice is not None else ""
    s_lon = f"[{lon_slice[0]}:1:{lon_slice[1]}]" if lon_slice is not None else ""
    s_time = "[0:1:0]"

    mapa_slices = {"time": s_time, "lat": s_lat, "lon": s_lon}
    slices_var = "".join(mapa_slices.get(d, "") for d in orden_dims)

    if protocolo == "dap4":
        pref = f"/{grupo}/" if grupo else "/"
        partes = [
            f"{pref}{var}{slices_var}",
            f"{pref}time",
            f"{pref}lat{s_lat}",
            f"{pref}lon{s_lon}",
        ]
        return f"{base}.dap.nc4?dap4.ce={';'.join(partes)}"

    # DAP2 (.nc4?...)
    var_dap2 = f"{grupo}_{var}" if grupo else var
    time_dap2 = f"{grupo}_time" if grupo else "time"
    lat_dap2 = f"{grupo}_lat" if grupo else "lat"
    lon_dap2 = f"{grupo}_lon" if grupo else "lon"
    partes_dap2 = [
        f"{var_dap2}{slices_var}",
        time_dap2,
        f"{lat_dap2}{s_lat}",
        f"{lon_dap2}{s_lon}",
    ]
    return f"{base}.nc4?{','.join(partes_dap2)}"


def _extraer_lat_lon_1d_de_bytes(datos_bytes: bytes, grupo: str | None = None) -> tuple[np.ndarray, np.ndarray] | None:
    """Extrae los vectores 1-D `lat` y `lon` en el orden exacto del servidor desde un binario NetCDF/HDF5 en RAM."""
    formato = _validar_firma_netcdf(datos_bytes)
    if formato == "cdf" and datos_bytes[:4] in (b"CDF\x01", b"CDF\x02"):
        with xr.open_dataset(io.BytesIO(datos_bytes), engine="scipy") as ds:
            ds_mem = ds.load()
        vars_map = {k: np.asarray(ds_mem[k].values, dtype=np.float64) for k in ds_mem.variables}
    else:
        with _LOCK_HDF5:
            _silenciar_hdf5_hilo_actual()
            nc_mem = netCDF4.Dataset("coords_opendap.nc", mode="r", memory=datos_bytes)
            try:
                origen = nc_mem.groups[grupo] if (grupo and grupo in nc_mem.groups) else nc_mem
                vars_map = {k: np.asarray(origen.variables[k][:], dtype=np.float64) for k in origen.variables}
            finally:
                if nc_mem.isopen():
                    nc_mem.close()

    pref = f"{grupo}_" if grupo else ""
    lat_1d: np.ndarray | None = None
    lon_1d: np.ndarray | None = None
    for cand in (*_NOMBRES_LAT, *(f"{pref}{n}" for n in _NOMBRES_LAT if pref)):
        if cand in vars_map and vars_map[cand].ndim == 1 and vars_map[cand].size >= 2:
            lat_1d = vars_map[cand]
            break
    for cand in (*_NOMBRES_LON, *(f"{pref}{n}" for n in _NOMBRES_LON if pref)):
        if cand in vars_map and vars_map[cand].ndim == 1 and vars_map[cand].size >= 2:
            lon_1d = vars_map[cand]
            break
    if lat_1d is not None and lon_1d is not None:
        return lat_1d, lon_1d
    return None


def _descubrir_coordenadas_opendap(
    url_opendap: str,
    entrada: dict[str, Any],
    sesion: Any,
    timeout: int,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Consulta únicamente los vectores 1-D `lat` y `lon` reales del servidor OPeNDAP (~4 KB) y los cachea en RAM."""
    clave = str(entrada.get("short_name") or entrada.get("variable") or url_opendap)
    with _LOCK_COORDS:
        if clave in _CACHE_COORDENADAS_OPENDAP:
            return _CACHE_COORDENADAS_OPENDAP[clave]

    base = re.sub(r"\.(dap\.nc4|nc4|dods|dds|das|dmr|html)$", "", url_opendap)
    if url_opendap.endswith((".nc4", ".HDF5", ".hdf5", ".nc")):
        base = url_opendap
    grupo = entrada.get("grupo_hdf")
    pref = f"/{grupo}/" if grupo else "/"
    lat_dap2 = f"{grupo}_lat" if grupo else "lat"
    lon_dap2 = f"{grupo}_lon" if grupo else "lon"

    urls_coords = [
        f"{base}.dap.nc4?dap4.ce={pref}lat;{pref}lon",
        f"{base}.nc4?{lat_dap2},{lon_dap2}",
    ]
    for u in urls_coords:
        try:
            resp = sesion.get(u, timeout=timeout)
            if resp.status_code == 200 and resp.content:
                par = _extraer_lat_lon_1d_de_bytes(resp.content, grupo=grupo)
                if par is not None:
                    with _LOCK_COORDS:
                        _CACHE_COORDENADAS_OPENDAP[clave] = par
                    return par
        except Exception:  # noqa: BLE001
            continue
    return None


def serializar_netcdf_en_memoria(da: xr.DataArray, grupo: str | None = None) -> bytes:
    """Serializa un DataArray a bytes NetCDF4/HDF5 íntegramente en memoria RAM (útil para tests y mocks OPeNDAP)."""
    nombre = str(da.name or "valor")
    with _LOCK_HDF5:
        _silenciar_hdf5_hilo_actual()
        nc = netCDF4.Dataset("memoria.nc", mode="w", memory=max(4096, int(da.nbytes) * 2))
        destino = nc.createGroup(grupo) if grupo else nc

        for dim in da.dims:
            destino.createDimension(str(dim), int(da.sizes[dim]))
            if dim in da.coords:
                c = da.coords[dim]
                if np.issubdtype(c.dtype, np.datetime64):
                    dias = (pd.DatetimeIndex(c.values) - pd.Timestamp("1970-01-01")) / pd.Timedelta(days=1)
                    vc = destino.createVariable(str(dim), "f8", (str(dim),))
                    vc.units = "days since 1970-01-01 00:00:00"
                    vc.calendar = "proleptic_gregorian"
                    vc[:] = dias.values
                else:
                    vc = destino.createVariable(str(dim), "f8", (str(dim),))
                    vc[:] = np.asarray(c.values, dtype=np.float64)

        v = destino.createVariable(nombre, "f4", tuple(str(d) for d in da.dims))
        for k, val in da.attrs.items():
            if isinstance(val, (str, int, float)):
                setattr(v, k, val)
        v[:] = np.asarray(da.values, dtype=np.float32)
        mem = nc.close()
        return bytes(mem)


def _vincular_coordenadas_opendap(
    ds: xr.Dataset,
    nombre: str,
    entrada: dict[str, Any],
    coords_esperadas: tuple[np.ndarray, np.ndarray] | None = None,
) -> xr.DataArray:
    """Garantiza que la variable extraída de OPeNDAP tenga las dimensiones y coordenadas `time`, `lat`, `lon`."""
    da_var = ds[nombre]
    orden_dims = (entrada.get("grilla") or {}).get("orden_dims", ["time", "lat", "lon"])

    # Si DAP4 generó dimensiones anónimas (ej. dim0, dim1, dim2), renombrarlas según orden_dims.
    if da_var.ndim == len(orden_dims) and any(d not in ("time", *_NOMBRES_LAT, *_NOMBRES_LON) for d in da_var.dims):
        renombres_dims = {dim_actual: dim_esp for dim_actual, dim_esp in zip(da_var.dims, orden_dims)}
        da_var = da_var.rename(renombres_dims)

    # Asociar variables 1-D de coordenadas presentes en `ds` si no quedaron enlazadas como coords.
    nuevas_coords: dict[str, Any] = {}
    for eje, candidatos in (("time", ("time",)), ("lat", _NOMBRES_LAT), ("lon", _NOMBRES_LON)):
        dim_eje = next((d for d in da_var.dims if d == eje or d in candidatos), None)
        if dim_eje is None:
            continue
        if dim_eje not in da_var.coords:
            for c_var in candidatos:
                if c_var in ds.variables and ds[c_var].ndim == 1 and ds[c_var].size == da_var.sizes[dim_eje]:
                    nuevas_coords[dim_eje] = (dim_eje, ds[c_var].values)
                    break

    if coords_esperadas is not None:
        lat_esp, lon_esp = coords_esperadas
        for dim_lat in (d for d in da_var.dims if d in _NOMBRES_LAT):
            if dim_lat not in da_var.coords and dim_lat not in nuevas_coords and lat_esp.size == da_var.sizes[dim_lat]:
                nuevas_coords[dim_lat] = (dim_lat, lat_esp)
        for dim_lon in (d for d in da_var.dims if d in _NOMBRES_LON):
            if dim_lon not in da_var.coords and dim_lon not in nuevas_coords and lon_esp.size == da_var.sizes[dim_lon]:
                nuevas_coords[dim_lon] = (dim_lon, lon_esp)

    if nuevas_coords:
        da_var = da_var.assign_coords(nuevas_coords)
    return da_var


def abrir_bytes_netcdf_en_memoria(
    datos_bytes: bytes,
    entrada: dict[str, Any],
    bbox: BBox | None = None,
    *,
    coords_esperadas: tuple[np.ndarray, np.ndarray] | None = None,
) -> xr.DataArray:
    """Abre un buffer binario NetCDF4/HDF5 o NetCDF3 (respuesta de OPeNDAP) en memoria RAM sin escribir a disco.

    Soporta tanto variables dentro de grupos HDF5 (`group="Grid"`) como variables aplanadas en la raíz por
    el servidor OPeNDAP (`Grid_precipitation` o `precipitation`). Valida la firma mágica del binario antes
    de invocar `libnetcdf`/`libhdf5` y silencia la pila `HDF5-DIAG` thread-local en hilos trabajadores.
    """
    formato = _validar_firma_netcdf(datos_bytes)
    nombre = entrada["variable"]
    grupo = entrada.get("grupo_hdf")
    frecuencia = entrada["frecuencia"]

    usar_grupo: str | None = None
    if formato == "cdf" and datos_bytes[:4] in (b"CDF\x01", b"CDF\x02"):
        with xr.open_dataset(io.BytesIO(datos_bytes), engine="scipy") as ds_remoto:
            ds = ds_remoto.load()
    else:
        with _LOCK_HDF5:
            _silenciar_hdf5_hilo_actual()
            nc_mem = netCDF4.Dataset("opendap_response.nc", mode="r", memory=datos_bytes)
            try:
                usar_grupo = grupo if (grupo and grupo in nc_mem.groups) else None
                store = NetCDF4DataStore(nc_mem, group=usar_grupo)
                with xr.open_dataset(store) as ds_remoto:
                    ds = ds_remoto.load()
            finally:
                if nc_mem.isopen():
                    nc_mem.close()

    # Si OPeNDAP aplanó los nombres del grupo (ej. Grid_precipitation, Grid_lat, Grid_lon), normalizarlos.
    if grupo and usar_grupo is None:
        renombres_grupo = {}
        pref = f"{grupo}_"
        for k in list(ds.variables):
            if k.startswith(pref):
                renombres_grupo[k] = k[len(pref):]
        if renombres_grupo:
            ds = ds.rename(renombres_grupo)

    if nombre not in ds.data_vars:
        raise KeyError(
            f"'{nombre}' no está en la respuesta OPeNDAP (variables recibidas: {sorted(ds.data_vars)})"
        )
    da_var = _vincular_coordenadas_opendap(ds, nombre, entrada, coords_esperadas=coords_esperadas)
    da_norm = normalizar_coordenadas(da_var)
    if bbox is not None and ("lat" in da_norm.dims and "lon" in da_norm.dims):
        da_norm = recortar_bbox(da_norm, bbox)
    da = normalizar_tiempo(da_norm, frecuencia)
    return da


def _descargar_subset_con_slices(
    url_base: str,
    entrada: dict[str, Any],
    bbox: BBox,
    sesion: Any,
    timeout: int,
    lat_slice: tuple[int, int] | None,
    lon_slices: list[tuple[int, int]] | tuple[None, ...],
    coords_srv: tuple[np.ndarray, np.ndarray] | None,
    errores: list[str],
) -> xr.DataArray | None:
    """Intenta descargar uno o dos segmentos contiguos de longitud por DAP4 o DAP2 y unirlos en RAM."""
    for protocolo in ("dap4", "dap2"):
        try:
            segmentos_da: list[xr.DataArray] = []
            exito_protocolo = True
            for lon_s in lon_slices:
                url_sub = construir_url_opendap_subset(
                    url_base,
                    entrada,
                    bbox,
                    protocolo=protocolo,
                    lat_slice=lat_slice,
                    lon_slice=lon_s,
                )
                resp = sesion.get(url_sub, timeout=timeout)
                if resp.status_code != 200 or not resp.content:
                    errores.append(f"{protocolo} HTTP {resp.status_code}")
                    exito_protocolo = False
                    break
                coords_esp = None
                if coords_srv is not None and lat_slice is not None and lon_s is not None:
                    coords_esp = (
                        coords_srv[0][lat_slice[0] : lat_slice[1] + 1],
                        coords_srv[1][lon_s[0] : lon_s[1] + 1],
                    )
                bbox_seg = bbox if len(lon_slices) == 1 else None
                seg = abrir_bytes_netcdf_en_memoria(
                    resp.content,
                    entrada,
                    bbox=bbox_seg,
                    coords_esperadas=coords_esp,
                )
                segmentos_da.append(seg)

            if exito_protocolo and segmentos_da:
                if len(segmentos_da) == 1:
                    return segmentos_da[0]
                unido = normalizar_coordenadas(xr.concat(segmentos_da, dim="lon"))
                return recortar_bbox(unido, bbox)
        except Exception as exc:  # noqa: BLE001
            errores.append(f"{protocolo}: {exc}")
    return None


def leer_granulo_opendap(
    granulo_o_url: Any,
    entrada: dict[str, Any],
    bbox: BBox,
    sesion: Any | None = None,
) -> xr.DataArray:
    """Lee un gránulo vía OPeNDAP recortando en el servidor y abriendo el resultado en memoria RAM (0 disco)."""
    url_base = extraer_url_opendap(granulo_o_url)
    timeout = obtener_ajustes().opendap_timeout

    if sesion is None:
        import earthaccess

        sesion = earthaccess.get_requests_https_session()

    errores: list[str] = []
    clave_col = str(entrada.get("short_name") or entrada.get("variable") or url_base)
    with _LOCK_COORDS:
        coords_cacheadas = _CACHE_COORDENADAS_OPENDAP.get(clave_col)

    # 1. Si ya descubrimos la grilla real del servidor para esta colección, usar sus índices exactos.
    if coords_cacheadas is not None:
        lat_s, lon_ss = segmentos_indices_bbox_opendap(coords_cacheadas[0], coords_cacheadas[1], bbox)
        da = _descargar_subset_con_slices(
            url_base, entrada, bbox, sesion, timeout, lat_s, lon_ss, coords_cacheadas, errores
        )
        if da is not None:
            return da

    # 2. Intentar con los índices de la grilla declarada en el catálogo.
    da = _descargar_subset_con_slices(
        url_base, entrada, bbox, sesion, timeout, None, (None,), None, errores
    )
    if da is not None:
        return da

    # 3. Si los índices estáticos fallaron (p. ej. lat descendente 89.75 → -89.75 o lon 0..360 en el servidor),
    #    descubrir los vectores 1-D `lat` y `lon` reales del servidor OPeNDAP y reintentar con índices exactos.
    if coords_cacheadas is None:
        coords_descubiertas = _descubrir_coordenadas_opendap(url_base, entrada, sesion, timeout)
        if coords_descubiertas is not None:
            lat_s, lon_ss = segmentos_indices_bbox_opendap(coords_descubiertas[0], coords_descubiertas[1], bbox)
            da = _descargar_subset_con_slices(
                url_base, entrada, bbox, sesion, timeout, lat_s, lon_ss, coords_descubiertas, errores
            )
            if da is not None:
                return da

    # 4. Alternativa sin disco: descarga del gránulo por HTTPS directamente en memoria RAM
    enlaces_https = (
        granulo_o_url.data_links(access="external")
        if not isinstance(granulo_o_url, str) and hasattr(granulo_o_url, "data_links")
        else []
    )
    for url_https in enlaces_https:
        if "/opendap/" in str(url_https):
            continue
        try:
            resp = sesion.get(str(url_https), timeout=timeout)
            if resp.status_code == 200 and resp.content:
                return abrir_bytes_netcdf_en_memoria(resp.content, entrada, bbox=bbox)
            errores.append(f"https HTTP {resp.status_code}")
        except Exception as exc:  # noqa: BLE001
            errores.append(f"https: {exc}")

    raise RuntimeError(f"No se pudo leer {url_base} por OPeNDAP en memoria ({'; '.join(errores)})")


def _motor_netcdf() -> str:
    try:
        import h5netcdf.core as _hc

        if not (_hc.no_h5py and _hc.no_pyfive):
            return "h5netcdf"
    except Exception:  # noqa: BLE001
        pass
    return "netcdf4"


def _kwargs_apertura(entrada: dict) -> dict[str, Any]:
    kw: dict[str, Any] = {"engine": _motor_netcdf()}
    if entrada.get("grupo_hdf"):
        kw["group"] = entrada["grupo_hdf"]
    return kw


def abrir_y_recortar(fuentes: Iterable[Any], entrada: dict, bbox: BBox, inicio: str, fin: str) -> xr.DataArray:
    """Abre objetos o buffers en memoria (bytes, file-like o rutas), normaliza y recorta en RAM."""
    nombre = entrada["variable"]
    frecuencia = entrada["frecuencia"]
    lista_fuentes = list(fuentes)

    if lista_fuentes and all(isinstance(f, (bytes, bytearray, memoryview)) or hasattr(f, "read") for f in lista_fuentes):
        partes = []
        for f in lista_fuentes:
            if hasattr(f, "seek"):
                f.seek(0)
            contenido = bytes(f.read()) if hasattr(f, "read") else bytes(f)
            partes.append(abrir_bytes_netcdf_en_memoria(contenido, entrada, bbox=bbox))
        da = xr.concat(partes, dim="time").sortby("time")
        if frecuencia == "diaria":
            return da.sel(time=slice(f"{inicio}-01", _fin_de_mes(fin)))
        return da.sel(time=slice(inicio, fin))

    def _pre(ds: xr.Dataset) -> xr.Dataset:
        if nombre not in ds.data_vars:
            raise KeyError(f"'{nombre}' no está en el dataset remoto (variables: {sorted(ds.data_vars)[:20]})")
        ds = normalizar_coordenadas(ds[[nombre]])
        return recortar_bbox(ds, bbox)

    with xr.open_mfdataset(
        lista_fuentes,
        combine="by_coords",
        preprocess=_pre,
        data_vars="minimal",
        coords="minimal",
        compat="override",
        **_kwargs_apertura(entrada),
    ) as ds:
        da = normalizar_tiempo(ds[nombre], frecuencia)
        if frecuencia == "diaria":
            da = da.sel(time=slice(f"{inicio}-01", _fin_de_mes(fin)))
        else:
            da = da.sel(time=slice(inicio, fin))
        return da.load()


def consultar_opendap(
    entrada: dict[str, Any],
    bbox: BBox,
    inicio: str,
    fin: str,
    *,
    progreso: Progreso | None = None,
) -> xr.DataArray:
    """Consulta una colección de NASA por OPeNDAP entre [inicio, fin] íntegramente en memoria RAM.

    No descarga ni escribe ningún archivo NetCDF/HDF en disco.
    """
    import earthaccess

    iniciar_sesion()
    avisar = progreso or (lambda *_: None)
    resultados = earthaccess.search_data(
        short_name=entrada["short_name"],
        version=entrada.get("version"),
        temporal=(f"{inicio}-01", f"{_fin_de_mes(fin)}T23:59:59"),
        bounding_box=bbox,
    )
    if not resultados:
        raise RuntimeError(
            f"0 gránulos en CMR para {entrada['short_name']} v{entrada.get('version')} entre {inicio} y {fin}"
        )

    sesion = earthaccess.get_requests_https_session()
    total = len(resultados)
    avisar(0, total, f"Consultando {total} gránulos vía OPeNDAP en memoria para {entrada['short_name']}")

    trabajadores = min(obtener_ajustes().opendap_workers, total)
    partes: list[xr.DataArray] = []

    if trabajadores <= 1 or total == 1:
        for i, g in enumerate(resultados, start=1):
            partes.append(leer_granulo_opendap(g, entrada, bbox, sesion=sesion))
            avisar(i, total, f"OPeNDAP en memoria {i}/{total}")
    else:
        # Leer el primer gránulo primero para descubrir y cachear las coordenadas (lat/lon) reales del servidor
        # antes de lanzar el resto de gránulos en paralelo.
        partes.append(leer_granulo_opendap(resultados[0], entrada, bbox, sesion=sesion))
        avisar(1, total, f"OPeNDAP en memoria 1/{total}")
        with ThreadPoolExecutor(max_workers=trabajadores, thread_name_prefix="opendap-ram") as pool:
            futuros = [pool.submit(leer_granulo_opendap, g, entrada, bbox, sesion) for g in resultados[1:]]
            for i, fut in enumerate(futuros, start=2):
                partes.append(fut.result())
                avisar(i, total, f"OPeNDAP en memoria {i}/{total}")

    da = xr.concat(partes, dim="time").sortby("time")
    if entrada["frecuencia"] == "diaria":
        da = da.sel(time=slice(f"{inicio}-01", _fin_de_mes(fin)))
    else:
        da = da.sel(time=slice(inicio, fin))
    return da


def preparar_crudo(da: xr.DataArray, entrada: dict, variable: str) -> xr.DataArray:
    """Rango válido → conversión de unidades del catálogo → metadatos en RAM."""
    da = convertir(aplicar_rango_valido(da, entrada), entrada)
    da.name = variable
    da.attrs.update({
        "variable": variable,
        "short_name": str(entrada.get("short_name")),
        "version": str(entrada.get("version", "")),
        "variable_archivo": entrada["variable"],
        "protocolo": "opendap_memoria",
    })
    return da


# ----------------------------------------------------------------------------------------------- Caché LRU en RAM (0 archivos en disco)
@dataclass
class EntradaCacheMemoria:
    variable: str
    region: str
    inicio: str
    fin: str
    da: xr.DataArray
    creado_en: str

    @property
    def clave(self) -> str:
        return f"{self.variable}_{self.region}_{self.inicio}_{self.fin}"

    def a_dict(self) -> dict[str, Any]:
        return {
            "clave": f"{self.variable}_{self.region}",
            "variable": self.variable,
            "region": self.region,
            "inicio": self.inicio,
            "fin": self.fin,
            "tipo": "memoria_ram",
            "unidad": self.da.attrs.get("units"),
            "dimensiones": list(self.da.dims),
            "forma": [int(s) for s in self.da.shape],
            "kb_ram": round(int(self.da.nbytes) / 1024.0, 2),
            "creado_en": self.creado_en,
        }


class CacheMemoriaLRU:
    """Caché LRU thread-safe en memoria RAM para DataArrays recortados (0 archivos NetCDF/HDF en disco)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: OrderedDict[tuple[str, str, str, str], EntradaCacheMemoria] = OrderedDict()

    def guardar(self, da: xr.DataArray, variable: str, region: str, inicio: str, fin: str) -> EntradaCacheMemoria:
        if "units" not in da.attrs:
            raise ValueError("El DataArray no tiene attrs['units']: convierte unidades antes de guardar en caché.")
        validar_periodo(inicio, fin)
        reg_slug = slug_region(region)
        copia = da.load().copy(deep=True)
        copia.name = variable
        entrada = EntradaCacheMemoria(
            variable=variable,
            region=reg_slug,
            inicio=inicio,
            fin=fin,
            da=copia,
            creado_en=datetime.now(timezone.utc).isoformat(),
        )
        clave = (variable, reg_slug, inicio, fin)
        max_items = obtener_ajustes().cache_memoria_max
        with self._lock:
            if clave in self._items:
                self._items.move_to_end(clave)
            self._items[clave] = entrada
            while len(self._items) > max_items:
                self._items.popitem(last=False)
        return entrada

    def buscar(self, variable: str, region: str, inicio: str, fin: str) -> xr.DataArray | None:
        """Busca coincidencia exacta o un periodo más amplio ya en RAM para la misma variable y región."""
        validar_periodo(inicio, fin)
        reg_slug = slug_region(region)
        clave_exacta = (variable, reg_slug, inicio, fin)
        with self._lock:
            if clave_exacta in self._items:
                self._items.move_to_end(clave_exacta)
                return self._items[clave_exacta].da.copy(deep=False)
            for (v, r, ini, fn), item in self._items.items():
                if v == variable and r == reg_slug and ini <= inicio and fn >= fin:
                    self._items.move_to_end((v, r, ini, fn))
                    da = item.da
                    if "time" in da.dims:
                        # Soporta series mensuales y diarias
                        es_diaria = da.sizes["time"] > 1 and (
                            float(np.median(np.diff(pd.DatetimeIndex(da["time"].values)).astype("timedelta64[D]").astype(float))) <= 2.0
                        )
                        if es_diaria:
                            return da.sel(time=slice(f"{inicio}-01", _fin_de_mes(fin))).copy(deep=False)
                        return da.sel(time=slice(inicio, fin)).copy(deep=False)
                    return da.copy(deep=False)
        return None

    def listar(self, variable: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._items.values())
        if variable is not None:
            items = [i for i in items if i.variable == variable]
        return [i.a_dict() for i in items]

    def limpiar(self, variable: str | None = None) -> int:
        with self._lock:
            if variable is None:
                n = len(self._items)
                self._items.clear()
                return n
            claves = [k for k in self._items if k[0] == variable]
            for k in claves:
                del self._items[k]
            return len(claves)


CACHE_MEMORIA = CacheMemoriaLRU()


def clave_cache_memoria(variable: str, region: str, inicio: str, fin: str) -> str:
    """Identificador lógico `<variable>_<region>_<inicio>_<fin>` en la caché en memoria RAM."""
    validar_periodo(inicio, fin)
    return f"{variable}_{slug_region(region)}_{inicio}_{fin}"


def guardar_en_memoria(da: xr.DataArray, variable: str, region: str, inicio: str, fin: str) -> str:
    """Guarda un DataArray ya convertido en la caché LRU en memoria RAM."""
    return CACHE_MEMORIA.guardar(da, variable, region, inicio, fin).clave


def buscar_en_memoria(variable: str, region: str, inicio: str, fin: str) -> xr.DataArray | None:
    """Recupera un DataArray de la caché en memoria RAM (o None si no está)."""
    return CACHE_MEMORIA.buscar(variable, region, inicio, fin)


def limpiar_cache_memoria(variable: str | None = None) -> int:
    """Vacía la caché en memoria RAM (toda o solo de una variable). Devuelve cuántas entradas se eliminaron."""
    return CACHE_MEMORIA.limpiar(variable)


def inventario_cache(variable: str | None = None) -> list[dict[str, Any]]:
    """Lista los cubos actualmente almacenados en memoria RAM."""
    return CACHE_MEMORIA.listar(variable)


# ----------------------------------------------------------------------------------------------- Flujo principal
def descargar_variable(
    variable: str,
    region: str,
    bbox: BBox,
    inicio: str,
    fin: str,
    catalogo: dict[str, dict],
    progreso: Progreso | None = None,
    forzar: bool = False,
) -> dict[str, Any]:
    """Consulta la variable por OPeNDAP y la deja lista en la caché en memoria RAM (sin archivos en disco)."""
    entrada = catalogo[variable]
    if entrada["grupo"] == "calculada" or not entrada.get("short_name"):
        raise ValueError(f"{variable} es calculada: consulta su origen '{entrada.get('origen')}'")
    validar_periodo(inicio, fin)
    bbox = validar_bbox(bbox)
    avisar = progreso or (lambda *_: None)

    if not forzar:
        en_ram = buscar_en_memoria(variable, region, inicio, fin)
        if en_ram is not None:
            clave = clave_cache_memoria(variable, region, inicio, fin)
            avisar(1, 1, f"ya en memoria RAM: {clave}")
            return {
                "variable": variable,
                "region": slug_region(region),
                "inicio": inicio,
                "fin": fin,
                "clave_memoria": clave,
                "kb_ram": round(int(en_ram.nbytes) / 1024.0, 2),
                "protocolo": "opendap_memoria",
            }

    crudo = consultar_opendap(entrada, bbox, inicio, fin, progreso=progreso)
    convertido = preparar_crudo(crudo, entrada, variable)
    item = CACHE_MEMORIA.guardar(convertido, variable, region, inicio, fin)
    return {
        "variable": variable,
        "region": item.region,
        "inicio": inicio,
        "fin": fin,
        "clave_memoria": item.clave,
        "kb_ram": round(int(convertido.nbytes) / 1024.0, 2),
        "protocolo": "opendap_memoria",
    }


def obtener_variable(
    variable: str,
    region: str,
    bbox: BBox,
    inicio: str,
    fin: str,
    catalogo: dict[str, dict],
    descargar: bool = False,
) -> xr.DataArray:
    """Devuelve la variable recortada y en unidades finales (attrs['units']) desde la caché en RAM o vía OPeNDAP.

    Nunca lee ni escribe archivos NetCDF/HDF en disco:
        - Si el cubo está en `CACHE_MEMORIA`, lo devuelve al instante.
        - Si no está y `descargar=True`, lo transmite desde NASA GES DISC por OPeNDAP a memoria RAM y lo cachea.
        - Si no está y `descargar=False`, lanza `DatosNoDisponibles`.
    """
    validar_periodo(inicio, fin)
    en_ram = buscar_en_memoria(variable, region, inicio, fin)
    if en_ram is not None:
        return en_ram
    if not descargar:
        raise DatosNoDisponibles(variable, region, inicio, fin)
    descargar_variable(variable, region, bbox, inicio, fin, catalogo, forzar=True)
    res = buscar_en_memoria(variable, region, inicio, fin)
    if res is None:
        raise DatosNoDisponibles(variable, region, inicio, fin)
    return res
