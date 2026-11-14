"""Plantilla de motor/datos.py — acceso a NASA Earthdata con caché.

Las partes sin red (ruta_cache, normalizar_coordenadas, guardar_cache, leer_cache) están listas para usar.
Las de red (descargar_y_recortar) son un esqueleto: pruébalas con un año y una región pequeña antes de
confiar en ellas. Credenciales SOLO por variables de entorno o .netrc (ver SKILL.md).
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import numpy as np
import xarray as xr

BBox = tuple[float, float, float, float]  # (oeste, sur, este, norte), lon en [-180, 180)

DIR_DATA = Path("data")
DIR_RAW = DIR_DATA / "raw"
DIR_CACHE = DIR_DATA / "cache"

_NOMBRES_LAT = ("lat", "latitude", "y", "Latitude")
_NOMBRES_LON = ("lon", "longitude", "x", "Longitude")


def iniciar_sesion():
    """Inicia sesión en Earthdata con variables de entorno o .netrc. Nunca pide la contraseña.

    Devuelve un earthaccess.Auth autenticado o lanza RuntimeError explicando qué configurar.
    """
    import earthaccess

    for estrategia in ("environment", "netrc"):
        try:
            auth = earthaccess.login(strategy=estrategia)
        except Exception:  # noqa: BLE001 — una estrategia que falla no es un error todavía
            continue
        if auth is not None and auth.authenticated:
            return auth
    raise RuntimeError(
        "No hay credenciales de Earthdata. Define EARTHDATA_USERNAME y EARTHDATA_PASSWORD "
        "o crea ~/.netrc con 'machine urs.earthdata.nasa.gov login <usuario> password <clave>'."
    )


def ruta_cache(variable: str, region: str, inicio: str, fin: str, formato: str = "nc") -> Path:
    """Ruta de caché data/cache/<variable>_<region>_<inicio>_<fin>.<formato>.

    variable: id del catálogo; region: slug en minúsculas; inicio/fin: 'AAAA-MM'; formato: 'nc' o 'zarr'.
    """
    if formato not in ("nc", "zarr"):
        raise ValueError(f"formato debe ser 'nc' o 'zarr', no {formato!r}")
    slug = region.strip().lower().replace(" ", "_")
    return DIR_CACHE / f"{variable}_{slug}_{inicio}_{fin}.{formato}"


def normalizar_coordenadas(da: xr.DataArray) -> xr.DataArray:
    """Deja el DataArray con dims (time, lat, lon), lat ascendente y lon en [-180, 180) ordenada.

    No cambia valores ni unidades.
    """
    renombres = {}
    for n in _NOMBRES_LAT:
        if n in da.dims and n != "lat":
            renombres[n] = "lat"
    for n in _NOMBRES_LON:
        if n in da.dims and n != "lon":
            renombres[n] = "lon"
    da = da.rename(renombres)
    if "lon" in da.dims:
        lon = ((da["lon"] + 180) % 360) - 180
        da = da.assign_coords(lon=lon).sortby("lon")
    if "lat" in da.dims:
        da = da.sortby("lat")
    orden = [d for d in ("time", "lat", "lon") if d in da.dims]
    resto = [d for d in da.dims if d not in orden]
    return da.transpose(*orden, *resto)


def recortar_bbox(da: xr.DataArray, bbox: BBox) -> xr.DataArray:
    """Recorta a (oeste, sur, este, norte). Requiere coordenadas normalizadas. Soporta cruzar el antimeridiano."""
    oeste, sur, este, norte = bbox
    da = da.sel(lat=slice(sur, norte))
    if oeste <= este:
        return da.sel(lon=slice(oeste, este))
    return xr.concat([da.sel(lon=slice(oeste, 180)), da.sel(lon=slice(-180, este))], dim="lon")


def guardar_cache(da: xr.DataArray, ruta: Path) -> Path:
    """Escritura atómica: escribe en <ruta>.tmp y renombra. Exige attrs['units']."""
    if "units" not in da.attrs:
        raise ValueError("El DataArray no tiene attrs['units']: convierte unidades antes de guardar en caché.")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp) if tmp.is_dir() else tmp.unlink()
    ds = da.to_dataset(name=da.name or "valor")
    if ruta.suffix == ".zarr":
        ds.to_zarr(tmp, mode="w")
    else:
        ds.to_netcdf(tmp, engine="h5netcdf")
    if ruta.exists():
        shutil.rmtree(ruta) if ruta.is_dir() else ruta.unlink()
    os.replace(tmp, ruta)
    return ruta


def leer_cache(ruta: Path) -> xr.DataArray:
    """Lee un DataArray de caché (.nc o .zarr) y lo carga en memoria si es pequeño."""
    ds = xr.open_zarr(ruta) if ruta.suffix == ".zarr" else xr.open_dataset(ruta, engine="h5netcdf")
    nombre = list(ds.data_vars)[0]
    return ds[nombre]


def descargar_y_recortar(entrada: dict, bbox: BBox, inicio: str, fin: str) -> xr.DataArray:
    """ESQUELETO. Busca, descarga por lotes anuales, recorta y concatena. Devuelve unidades ORIGINALES.

    entrada: entrada del catálogo (short_name, version, variable...). inicio/fin: 'AAAA-MM'.
    """
    import earthaccess

    iniciar_sesion()
    partes: list[xr.DataArray] = []
    for anio in range(int(inicio[:4]), int(fin[:4]) + 1):
        resultados = earthaccess.search_data(
            short_name=entrada["short_name"],
            version=entrada.get("version"),
            temporal=(f"{anio}-01-01", f"{anio}-12-31"),
            bounding_box=bbox,
        )
        if not resultados:
            raise RuntimeError(f"0 gránulos para {entrada['short_name']} en {anio}: ¿short_name/versión verificados?")
        lote = DIR_RAW / entrada["short_name"] / str(anio)
        rutas = earthaccess.download(resultados, local_path=lote)
        kwargs = {"group": "Grid"} if entrada["short_name"] == "GPM_3IMERGM" else {}
        with xr.open_mfdataset(rutas, engine="h5netcdf", combine="by_coords", **kwargs) as ds:
            da = normalizar_coordenadas(ds[entrada["variable"]])
            partes.append(recortar_bbox(da, bbox).load())
        shutil.rmtree(lote, ignore_errors=True)  # patrón descargar → recortar → borrar
    da = xr.concat(partes, dim="time").sel(time=slice(inicio, fin))
    return da


def obtener_variable(variable: str, region: str, bbox: BBox, inicio: str, fin: str, catalogo: dict) -> xr.DataArray:
    """Devuelve la variable recortada y en unidades finales (attrs['units']), leyendo la caché si existe."""
    from motor.catalogo import convertir

    ruta = ruta_cache(variable, region, inicio, fin)
    if ruta.exists():
        return leer_cache(ruta)
    entrada = catalogo[variable]
    da = descargar_y_recortar(entrada, bbox, inicio, fin)
    da = convertir(da, entrada)
    da.name = variable
    guardar_cache(da, ruta)
    return da


if __name__ == "__main__":
    # Prueba rápida sin red de normalizar_coordenadas.
    t = np.array(["2001-01-01"], dtype="datetime64[ns]")
    da = xr.DataArray(np.zeros((1, 4, 3)), dims=("time", "lon", "lat"),
                      coords={"time": t, "lon": [0.0, 90.0, 180.0, 270.0], "lat": [10.0, 0.0, -10.0]})
    n = normalizar_coordenadas(da)
    print(n.dims, n.lon.values, n.lat.values)
