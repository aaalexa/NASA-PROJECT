"""Escáner regional, mapas de tendencias por píxel, las dos caras e impacto en población (skill escaner-y-mapas).

Ningún cálculo estadístico vive aquí: todo número de tendencia, p-valor o veredicto proviene de
motor.tendencias.calcular_tendencia para que el mapa y la ficha de una región nunca se contradigan.
"""
from __future__ import annotations

from collections import OrderedDict
import threading
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr

from core.config import obtener_ajustes
from core.motor.datos import slug_region, validar_periodo
from core.motor.series import SerieRechazada, preparar_para_motor
from core.motor.tendencias import UnidadTiempo, calcular_tendencia

__all__ = [
    "CODIGO_VEREDICTO",
    "escanear_region",
    "mapa_tendencias",
    "obtener_mapa_tendencias",
    "limpiar_cache_mapas_memoria",
    "comparar_dos_caras",
    "regrillar_poblacion",
    "regrillar_fraccion",
    "poblacion_afectada",
]

CODIGO_VEREDICTO: dict[str, float] = {
    "significativo": 2.0,
    "indicio": 1.0,
    "sin tendencia clara": 0.0,
}
_ORDEN_VEREDICTO: dict[str, int] = {
    "significativo": 0,
    "indicio": 1,
    "sin tendencia clara": 2,
}


# ----------------------------------------------------------------------------------------------- 1. Escáner regional
def escanear_region(
    series: dict[str, xr.DataArray | SerieRechazada],
    region: str,
    medias_climatologia: dict[str, float | None] | None = None,
    *,
    alfa: float = 0.05,
    max_faltantes: float = 0.10,
) -> dict[str, Any]:
    """Evalúa todas las series de una región y las ordena por veredicto y |SNR| de mayor a menor.

    Las series rechazadas por calidad (SerieRechazada o > max_faltantes de NaN) o demasiado cortas se incluyen
    en 'rechazadas' con su motivo para que la interfaz las muestre como 'datos insuficientes'.
    """
    medias = medias_climatologia or {}
    resultados: list[dict[str, Any]] = []
    rechazadas: list[dict[str, str]] = []

    for variable, item in series.items():
        if isinstance(item, SerieRechazada):
            rechazadas.append({"variable": variable, "motivo": str(item)})
            continue
        serie = item
        vals = np.asarray(serie.values, dtype=float)
        if vals.size == 0 or float(np.isnan(vals).mean()) > max_faltantes + 1e-12:
            frac = 1.0 if vals.size == 0 else float(np.isnan(vals).mean())
            rechazadas.append({
                "variable": variable,
                "motivo": f"datos insuficientes ({100.0 * frac:.1f} % faltantes, máximo {100.0 * max_faltantes:.0f} %)",
            })
            continue
        try:
            entrada_motor = preparar_para_motor(serie, media_climatologia=medias.get(variable))
            res = calcular_tendencia(
                entrada_motor["y"],
                entrada_motor["t"],
                unidad_tiempo=entrada_motor["unidad_tiempo"],
                variable=variable,
                region=region,
                periodo=entrada_motor["periodo"],
                media_climatologia=entrada_motor["media_climatologia"],
                alfa=alfa,
            )
            resultados.append(res)
        except ValueError as exc:
            rechazadas.append({"variable": variable, "motivo": str(exc)})

    resultados.sort(
        key=lambda r: (
            _ORDEN_VEREDICTO.get(r["veredicto"], 99),
            -abs(r["snr"]) if r["snr"] is not None else float("inf"),
        )
    )
    return {
        "region": region,
        "resultados": resultados,
        "rechazadas": rechazadas,
    }


# ----------------------------------------------------------------------------------------------- 2. Mapa por píxel
def _nucleo_pixel(
    y: np.ndarray,
    *,
    t: np.ndarray,
    unidad_tiempo: UnidadTiempo,
    alfa: float,
    max_faltantes: float,
) -> tuple[float, float, float, float]:
    """Núcleo 1-D por píxel: devuelve (pendiente_decada, p_t, p_mk, codigo_veredicto)."""
    y_arr = np.asarray(y, dtype=np.float64)
    if y_arr.size == 0 or float(np.isnan(y_arr).mean()) > max_faltantes + 1e-12:
        return np.nan, np.nan, np.nan, np.nan
    try:
        r = calcular_tendencia(
            y_arr,
            t,
            unidad_tiempo=unidad_tiempo,
            variable="pixel",
            region="pixel",
            periodo=("0", "1"),
            alfa=alfa,
        )
    except ValueError:
        return np.nan, np.nan, np.nan, np.nan
    return (
        float(r["pendiente_ols_decada"]),
        float(r["p_t"]),
        float(r["p_mk"]),
        float(CODIGO_VEREDICTO[r["veredicto"]]),
    )


def _eje_tiempo_cubo(cubo: xr.DataArray, unidad_tiempo: UnidadTiempo) -> tuple[str, np.ndarray, tuple[str, str]]:
    if "time" in cubo.dims:
        fechas = pd.DatetimeIndex(cubo["time"].values)
        if unidad_tiempo == "mes":
            t = (fechas.year - fechas.year[0]) * 12 + (fechas.month - fechas.month[0])
            periodo = (fechas[0].strftime("%Y-%m"), fechas[-1].strftime("%Y-%m"))
        else:
            t = fechas.year.values.astype(float)
            periodo = (str(int(t[0])), str(int(t[-1])))
        return "time", np.asarray(t, dtype=np.float64), periodo
    if "anio" in cubo.dims:
        t = cubo["anio"].values.astype(np.float64)
        return "anio", t, (str(int(t[0])), str(int(t[-1])))
    raise ValueError("el cubo debe tener dimensión 'time' o 'anio'")


def mapa_tendencias(
    cubo: xr.DataArray,
    unidad_tiempo: UnidadTiempo,
    alfa: float = 0.05,
    *,
    max_faltantes: float = 0.10,
) -> xr.Dataset:
    """Calcula la tendencia por píxel con xr.apply_ufunc y devuelve un Dataset (lat, lon) (skill escaner-y-mapas §2).

    Variables de salida:
        pendiente_decada   unidades del cubo por década
        p_t                p-valor bilateral de la prueba t corregida (0–1)
        p_mk               p-valor de Mann-Kendall (0–1)
        veredicto          2.0 = significativo, 1.0 = indicio, 0.0 = sin tendencia clara, NaN = sin datos
    """
    if unidad_tiempo not in ("mes", "anio"):
        raise ValueError(f"unidad_tiempo debe ser 'mes' o 'anio', no {unidad_tiempo!r}")
    dim_t, t, periodo = _eje_tiempo_cubo(cubo, unidad_tiempo)
    trabajo = cubo.chunk({dim_t: -1, "lat": 20, "lon": 20}) if cubo.chunks is not None else cubo

    pendiente, p_t, p_mk, ver = xr.apply_ufunc(
        _nucleo_pixel,
        trabajo,
        kwargs={"t": t, "unidad_tiempo": unidad_tiempo, "alfa": alfa, "max_faltantes": max_faltantes},
        input_core_dims=[[dim_t]],
        output_core_dims=[[], [], [], []],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[np.float64, np.float64, np.float64, np.float64],
    )
    unidad_base = cubo.attrs.get("units", "")
    unidad_pendiente = f"{unidad_base}/decada" if unidad_base else "1/decada"
    pendiente.attrs = {"units": unidad_pendiente, "long_name": "Pendiente OLS por década"}
    p_t.attrs = {"units": "1", "long_name": "p-valor prueba t corregida por n efectivo"}
    p_mk.attrs = {"units": "1", "long_name": "p-valor Mann-Kendall"}
    ver.attrs = {
        "units": "codigo",
        "codigos": "2=significativo, 1=indicio, 0=sin tendencia clara, NaN=sin datos",
    }

    ds = xr.Dataset(
        {
            "pendiente_decada": pendiente,
            "p_t": p_t,
            "p_mk": p_mk,
            "veredicto": ver,
        }
    )
    ds.attrs = {
        "variable": str(cubo.name or cubo.attrs.get("variable", "variable")),
        "unidad_variable": unidad_base,
        "unidad_tiempo": unidad_tiempo,
        "periodo": list(periodo),
        "alfa": float(alfa),
        "codigos_veredicto": "2=significativo, 1=indicio, 0=sin tendencia clara, NaN=sin datos",
    }
    return ds


_CACHE_MAPAS_MEMORIA: OrderedDict[tuple[str, str, str, str, float], xr.Dataset] = OrderedDict()
_LOCK_MAPAS = threading.Lock()


def limpiar_cache_mapas_memoria() -> int:
    """Vacía la caché en memoria RAM de mapas de tendencias."""
    with _LOCK_MAPAS:
        n = len(_CACHE_MAPAS_MEMORIA)
        _CACHE_MAPAS_MEMORIA.clear()
        return n


def obtener_mapa_tendencias(
    cubo: xr.DataArray,
    variable: str,
    region: str,
    inicio: str,
    fin: str,
    unidad_tiempo: UnidadTiempo,
    *,
    alfa: float = 0.05,
    usar_cache: bool = True,
) -> xr.Dataset:
    """Obtiene el mapa de tendencias desde la caché LRU en memoria RAM (0 archivos .zarr/.nc en disco)."""
    validar_periodo(inicio, fin)
    reg_slug = slug_region(region)
    clave = (variable, reg_slug, inicio, fin, float(alfa))
    if usar_cache:
        with _LOCK_MAPAS:
            if clave in _CACHE_MAPAS_MEMORIA:
                _CACHE_MAPAS_MEMORIA.move_to_end(clave)
                return _CACHE_MAPAS_MEMORIA[clave].copy(deep=False)

    ds = mapa_tendencias(cubo, unidad_tiempo=unidad_tiempo, alfa=alfa).compute()
    ds.attrs["variable"] = variable
    ds.attrs["region"] = reg_slug

    if usar_cache:
        max_items = obtener_ajustes().cache_memoria_max
        with _LOCK_MAPAS:
            _CACHE_MAPAS_MEMORIA[clave] = ds
            while len(_CACHE_MAPAS_MEMORIA) > max_items:
                _CACHE_MAPAS_MEMORIA.popitem(last=False)
    return ds


# ----------------------------------------------------------------------------------------------- 3. Las dos caras
def comparar_dos_caras(res_a: dict[str, Any], res_b: dict[str, Any]) -> dict[str, Any]:
    """Compara dos resultados del motor de tendencias (dos regiones o dos indicadores de extremos).

    dos_caras es True solo cuando ambas son 'significativo' y tienen direcciones opuestas ('sube' vs 'baja').
    """
    dir_a, dir_b = res_a.get("direccion"), res_b.get("direccion")
    signo_opuesto = {dir_a, dir_b} == {"sube", "baja"}
    ambas_significativas = (
        res_a.get("veredicto") == "significativo" and res_b.get("veredicto") == "significativo"
    )
    return {
        "region_a": res_a,
        "region_b": res_b,
        "signo_opuesto": bool(signo_opuesto),
        "ambas_significativas": bool(ambas_significativas),
        "dos_caras": bool(signo_opuesto and ambas_significativas),
    }


# ----------------------------------------------------------------------------------------------- 4. Población
def _bordes(centros: np.ndarray) -> np.ndarray:
    c = np.asarray(centros, dtype=np.float64)
    if c.size == 1:
        return np.array([c[0] - 0.25, c[0] + 0.25], dtype=np.float64)
    d = np.diff(c)
    if np.any(d <= 0):
        raise ValueError("las coordenadas de la malla destino deben ser estrictamente ascendentes")
    return np.concatenate([[c[0] - d[0] / 2.0], c[:-1] + d / 2.0, [c[-1] + d[-1] / 2.0]])


def _resolucion_media(coords: np.ndarray) -> float:
    return float(np.mean(np.abs(np.diff(coords)))) if coords.size > 1 else float("inf")


def regrillar_poblacion(pob: xr.DataArray, malla: xr.DataArray | xr.Dataset) -> xr.DataArray:
    """Regrilla conteos de población (personas por celda) a la malla destino conservando el total (referencia §1).

    Cada celda fina se asigna a la celda destino que contiene su centro y se suman las personas.
    Comprueba que |total_regrillado − total_original| / total_original <= 1e-6 dentro de la extensión destino.
    """
    lat_dst = malla["lat"].values
    lon_dst = malla["lon"].values
    lat_src = pob["lat"].values
    lon_src = pob["lon"].values

    if _resolucion_media(lat_src) > _resolucion_media(lat_dst) * 1.001 or (
        _resolucion_media(lon_src) > _resolucion_media(lon_dst) * 1.001
    ):
        raise ValueError("la malla de población debe ser igual o más fina que la malla del mapa")

    bordes_lat = _bordes(lat_dst)
    bordes_lon = _bordes(lon_dst)
    lat_f, lon_f = np.meshgrid(lat_src, lon_src, indexing="ij")
    j = np.digitize(lat_f.ravel(), bordes_lat) - 1
    k = np.digitize(lon_f.ravel(), bordes_lon) - 1
    p = np.nan_to_num(np.asarray(pob.values, dtype=np.float64).ravel(), nan=0.0)

    n_lat, n_lon = lat_dst.size, lon_dst.size
    dentro = (j >= 0) & (j < n_lat) & (k >= 0) & (k < n_lon)
    plano = np.bincount(
        j[dentro] * n_lon + k[dentro],
        weights=p[dentro],
        minlength=n_lat * n_lon,
    )
    out = xr.DataArray(
        plano.reshape(n_lat, n_lon),
        coords={"lat": malla["lat"], "lon": malla["lon"]},
        dims=("lat", "lon"),
        name="poblacion",
        attrs={"units": "personas"},
    )
    total_in = float(p[dentro].sum())
    if total_in > 0.0 and abs(float(out.values.sum()) - total_in) / total_in > 1e-6:
        raise ValueError("El regrillado no conservó el total de población")
    return out


def regrillar_fraccion(clases_bool: xr.DataArray, malla: xr.DataArray | xr.Dataset) -> xr.DataArray:
    """Fracción media de píxeles verdaderos (p. ej. cultivos MCD12Q1) dentro de cada celda de la malla destino."""
    lat_dst = malla["lat"].values
    lon_dst = malla["lon"].values
    bordes_lat = _bordes(lat_dst)
    bordes_lon = _bordes(lon_dst)
    lat_f, lon_f = np.meshgrid(clases_bool["lat"].values, clases_bool["lon"].values, indexing="ij")
    j = np.digitize(lat_f.ravel(), bordes_lat) - 1
    k = np.digitize(lon_f.ravel(), bordes_lon) - 1
    vals = np.asarray(clases_bool.values, dtype=np.float64).ravel()

    n_lat, n_lon = lat_dst.size, lon_dst.size
    dentro = (j >= 0) & (j < n_lat) & (k >= 0) & (k < n_lon) & np.isfinite(vals)
    idx = j[dentro] * n_lon + k[dentro]
    suma = np.bincount(idx, weights=vals[dentro], minlength=n_lat * n_lon)
    conteo = np.bincount(idx, minlength=n_lat * n_lon)
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = np.where(conteo > 0, suma / conteo, np.nan)
    return xr.DataArray(
        frac.reshape(n_lat, n_lon),
        coords={"lat": malla["lat"], "lon": malla["lon"]},
        dims=("lat", "lon"),
        name="fraccion_cultivo",
        attrs={"units": "fraccion"},
    )


def poblacion_afectada(
    mapa: xr.Dataset,
    pob_malla: xr.DataArray,
    mascara_cultivo: xr.DataArray | None = None,
    *,
    umbral_cultivo: float = 0.5,
    anio_poblacion: int = 2020,
) -> dict[str, Any]:
    """Suma la población en celdas con tendencia significativa negativa (seca) y positiva (húmeda) (referencia §2)."""
    if pob_malla.sizes != mapa["pendiente_decada"].sizes:
        pob_malla = regrillar_poblacion(pob_malla, mapa)

    s = np.asarray(mapa["pendiente_decada"].values, dtype=np.float64)
    v = np.asarray(mapa["veredicto"].values, dtype=np.float64)
    p = np.nan_to_num(np.asarray(pob_malla.values, dtype=np.float64), nan=0.0)

    con_dato = np.isfinite(s) & np.isfinite(v)
    seca_sig = con_dato & (s < 0.0) & (v == 2.0)
    hum_sig = con_dato & (s > 0.0) & (v == 2.0)
    seca_ind = con_dato & (s < 0.0) & (v == 1.0)
    hum_ind = con_dato & (s > 0.0) & (v == 1.0)

    pob_total = int(round(float(p[con_dato].sum())))
    pob_seca = int(round(float(p[seca_sig].sum())))
    pob_humeda = int(round(float(p[hum_sig].sum())))
    pob_seca_indicio = int(round(float(p[seca_ind].sum())))
    pob_humeda_indicio = int(round(float(p[hum_ind].sum())))

    pct_seca = float(100.0 * pob_seca / pob_total) if pob_total > 0 else 0.0
    pct_humeda = float(100.0 * pob_humeda / pob_total) if pob_total > 0 else 0.0

    pob_seca_agr: int | None = None
    pob_humeda_agr: int | None = None
    if mascara_cultivo is not None:
        mc = mascara_cultivo
        if mc.sizes != mapa["pendiente_decada"].sizes:
            mc = regrillar_fraccion(mc, mapa)
        arr_mc = np.asarray(mc.values)
        es_cultivo = arr_mc.astype(bool) if arr_mc.dtype == bool else (
            np.isfinite(arr_mc) & (arr_mc >= umbral_cultivo)
        )
        pob_seca_agr = int(round(float(p[seca_sig & es_cultivo].sum())))
        pob_humeda_agr = int(round(float(p[hum_sig & es_cultivo].sum())))

    return {
        "pob_seca": pob_seca,
        "pob_humeda": pob_humeda,
        "pob_total_region": pob_total,
        "pct_seca": pct_seca,
        "pct_humeda": pct_humeda,
        "pob_seca_indicio": pob_seca_indicio,
        "pob_humeda_indicio": pob_humeda_indicio,
        "anio_poblacion": int(anio_poblacion),
        "pob_seca_agricola": pob_seca_agr,
        "pob_humeda_agricola": pob_humeda_agr,
        "umbral_cultivo": float(umbral_cultivo),
    }

