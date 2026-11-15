"""Preprocesamiento: del cubo (time, lat, lon) a la serie regional lista para el motor (skill preprocesamiento-series).

Orden fijo de operaciones:
    1. Recorte por bounding box o polígono GeoJSON.
    2. Máscara opcional (tierra Natural Earth o máscara booleana de cultivos).
    3. Promedio espacial ponderado por cos(latitud) con control de área válida mínima (90 %).
    4. Climatología mensual C_m y anomalías y_t = x̄(t) − C_{m(t)} (para series mensuales).
    5. Agregación anual opcional ('suma' para lluvia en mm/mes → mm/anio; 'media' para el resto).
    6. Reindexado al calendario completo y control de calidad (máx. 10 % de datos faltantes; nunca interpola).
    7. Empaquetado para motor.tendencias.calcular_tendencia.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import geopandas as gpd
import numpy as np
import pandas as pd
import regionmask
import xarray as xr

from core.config import PERIODO_COMUN, PERIODO_GLOBAL
from core.motor.catalogo import cambiar_unidad
from core.motor.datos import BBox, normalizar_coordenadas, validar_bbox

__all__ = [
    "PERIODO_COMUN",
    "PERIODO_GLOBAL",
    "SerieRechazada",
    "recortar_bbox",
    "recortar_poligono",
    "mascara_tierra",
    "mascara_cultivos",
    "aplicar_mascara",
    "promedio_area",
    "climatologia",
    "anomalias",
    "anomalias_estandarizadas",
    "agregar_anual",
    "reindexar_calendario",
    "control_calidad",
    "preparar_para_motor",
    "serie_region",
]

MetodoAnual = Literal["suma", "media", "media_ponderada_dias"]


class SerieRechazada(ValueError):
    """La serie supera el máximo de datos faltantes permitido (10 % por defecto). Lleva .reporte."""

    def __init__(self, mensaje: str, reporte: dict[str, Any]):
        super().__init__(mensaje)
        self.reporte = reporte


# ----------------------------------------------------------------------------------------------- 1. Recorte
def recortar_bbox(da: xr.DataArray, bbox: BBox) -> xr.DataArray:
    """Recorta un DataArray (con coords normalizadas) a (oeste, sur, este, norte). Soporta cruzar el antimeridiano.

    Lanza ValueError si ningún centro de celda cae dentro de la caja.
    """
    oeste, sur, este, norte = validar_bbox(bbox)
    attrs = dict(da.attrs)
    if ("lat" in da.dims and da.sizes["lat"] > 1 and float(da["lat"][0]) > float(da["lat"][-1])) or (
        "lon" in da.dims and float(da["lon"].max()) >= 180.0
    ):
        da = normalizar_coordenadas(da)
    sub = da.sel(lat=slice(sur, norte))
    if oeste <= este:
        sub = sub.sel(lon=slice(oeste, este))
    else:
        sub = xr.concat([sub.sel(lon=slice(oeste, 180.0)), sub.sel(lon=slice(-180.0, este))], dim="lon")
    if sub.sizes.get("lat", 0) == 0 or sub.sizes.get("lon", 0) == 0:
        raise ValueError(f"la caja {bbox} no contiene ningún centro de celda de la malla")
    sub.attrs = attrs
    return sub


def _cargar_geodataframe(geojson: str | Path | dict | gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if isinstance(geojson, gpd.GeoDataFrame):
        return geojson
    if isinstance(geojson, dict):
        if geojson.get("type") == "FeatureCollection":
            return gpd.GeoDataFrame.from_features(geojson["features"], crs="EPSG:4326")
        if geojson.get("type") == "Feature":
            return gpd.GeoDataFrame.from_features([geojson], crs="EPSG:4326")
        from shapely.geometry import shape

        return gpd.GeoDataFrame({"geometry": [shape(geojson)]}, crs="EPSG:4326")
    texto = str(geojson).strip()
    if texto.startswith("{"):
        import json

        return _cargar_geodataframe(json.loads(texto))
    return gpd.read_file(Path(geojson))


def recortar_poligono(da: xr.DataArray, geojson: str | Path | dict | gpd.GeoDataFrame) -> xr.DataArray:
    """Recorta por el bounding box del polígono y aplica su máscara con regionmask.

    Si ningún centro de celda cae dentro (polígono pequeño frente a celdas grandes), calcula la fracción
    aproximada de cada celda cubierta por el polígono (mask_3D_frac_approx) y la deja en la coordenada
    '_fraccion_poligono' para que promedio_area pondere por ella. Si aun así no hay celdas, lanza ValueError.
    """
    attrs = dict(da.attrs)
    gdf = _cargar_geodataframe(geojson)
    if gdf.empty:
        raise ValueError("el GeoJSON no contiene ningún polígono")
    unido = gdf.union_all() if hasattr(gdf, "union_all") else gdf.unary_union
    gdf_unido = gpd.GeoDataFrame({"geometry": [unido]}, crs=gdf.crs or "EPSG:4326")
    minx, miny, maxx, maxy = gdf_unido.total_bounds

    # Margen de una celda para que mask_3D_frac_approx funcione cuando el polígono cae entre centros.
    dlat = float(np.abs(np.diff(da["lat"].values)).max()) if da.sizes.get("lat", 0) > 1 else 1.0
    dlon = float(np.abs(np.diff(da["lon"].values)).max()) if da.sizes.get("lon", 0) > 1 else 1.0
    bbox_Amplio: BBox = (
        max(-180.0, float(minx - dlon)),
        max(-90.0, float(miny - dlat)),
        min(180.0, float(maxx + dlon)),
        min(90.0, float(maxy + dlat)),
    )
    sub = recortar_bbox(da, bbox_Amplio)
    regiones = regionmask.from_geopandas(gdf_unido)
    mascara_centros = regiones.mask(sub["lon"], sub["lat"]).notnull()

    if bool(mascara_centros.any()):
        out = sub.where(mascara_centros)
        out = out.dropna("lat", how="all").dropna("lon", how="all")
        out.attrs = attrs
        return out

    frac_3d = regiones.mask_3D_frac_approx(sub["lon"], sub["lat"])
    frac = frac_3d.isel(region=0).drop_vars("region", errors="ignore")
    if not bool((frac > 0).any()):
        raise ValueError("el polígono no intersecta ninguna celda de la malla")
    out = sub.where(frac > 0)
    out = out.assign_coords(_fraccion_poligono=(("lat", "lon"), frac.values))
    out = out.dropna("lat", how="all").dropna("lon", how="all")
    out.attrs = attrs
    return out


# ----------------------------------------------------------------------------------------------- 2. Máscaras
def mascara_tierra(da: xr.DataArray) -> xr.DataArray:
    """Máscara booleana (lat, lon) de tierra firme según Natural Earth 1:110m."""
    tierra = regionmask.defined_regions.natural_earth_v5_0_0.land_110
    m = tierra.mask(da["lon"], da["lat"]).notnull()
    m.name = "mascara_tierra"
    return m


def mascara_cultivos(cultivos: xr.DataArray, malla: xr.DataArray | None = None,
                     umbral: float = 0.5) -> xr.DataArray:
    """Máscara booleana (lat, lon) donde la fracción de celdas de cultivo (clases 12 y 14) es ≥ umbral."""
    if not 0.0 < umbral <= 1.0:
        raise ValueError(f"umbral de cultivo debe estar en (0, 1], no {umbral}")
    base = cultivos.mean("time", skipna=True) if "time" in cultivos.dims else (
        cultivos.mean("anio", skipna=True) if "anio" in cultivos.dims else cultivos
    )
    if malla is not None and (base.sizes != malla.sizes or not np.allclose(base["lat"], malla["lat"])):
        from core.motor.escaner import regrillar_fraccion

        base = regrillar_fraccion(base, malla)
    return base >= umbral


def aplicar_mascara(da: xr.DataArray, mascara: xr.DataArray | Literal["tierra"]) -> xr.DataArray:
    """Aplica una máscara booleana (o 'tierra') con da.where(mascara) conservando attrs."""
    attrs = dict(da.attrs)
    m = mascara_tierra(da) if isinstance(mascara, str) and mascara == "tierra" else mascara
    if not isinstance(m, xr.DataArray):
        raise TypeError("mascara debe ser un xr.DataArray booleano o 'tierra'")
    out = da.where(m.astype(bool))
    out.attrs = attrs
    return out


# ----------------------------------------------------------------------------------------------- 3. Promedio espacial
def _bordes_celdas(centros: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Bordes inferior y superior de cada celda a partir de sus centros (puntos medios; extremos por medio paso)."""
    c = np.asarray(centros, dtype=np.float64).ravel()
    if c.size == 1:
        paso = 0.5
        return c - paso / 2, c + paso / 2
    medios = (c[:-1] + c[1:]) / 2.0
    inf = np.concatenate([[c[0] - (medios[0] - c[0])], medios])
    sup = np.concatenate([medios, [c[-1] + (c[-1] - medios[-1])]])
    return np.minimum(inf, sup), np.maximum(inf, sup)


def pesos_area_region(da: xr.DataArray, bbox: Sequence[float] | None = None) -> xr.DataArray:
    """Área de cada celda que cae dentro de la región: Aᵢ ∝ Δλᵢ·|sin φ₂ − sin φ₁| recortada a la caja (Down to Earth §02).

    Usa los bordes de cada celda (deducidos del espaciado de la malla) y los recorta a (oeste, sur, este, norte),
    de modo que una celda que queda a medias fuera de la caja pesa solo por la parte que está dentro. Sin `bbox`
    devuelve el área esférica completa de cada celda. Las unidades son relativas (radianes·adimensional).
    """
    lat_inf, lat_sup = _bordes_celdas(da["lat"].values)
    lon_inf, lon_sup = _bordes_celdas(da["lon"].values)
    lat_inf, lat_sup = np.clip(lat_inf, -90.0, 90.0), np.clip(lat_sup, -90.0, 90.0)
    if bbox is not None:
        oeste, sur, este, norte = validar_bbox(bbox)
        lat_inf, lat_sup = np.clip(lat_inf, sur, norte), np.clip(lat_sup, sur, norte)
        if oeste <= este:
            lon_inf, lon_sup = np.clip(lon_inf, oeste, este), np.clip(lon_sup, oeste, este)
        else:  # cruza el antimeridiano: cada celda se recorta al segmento que contiene su centro
            centros = np.asarray(da["lon"].values, dtype=np.float64)
            en_oeste = centros >= oeste
            lon_inf = np.where(en_oeste, np.clip(lon_inf, oeste, 180.0), np.clip(lon_inf, -180.0, este))
            lon_sup = np.where(en_oeste, np.clip(lon_sup, oeste, 180.0), np.clip(lon_sup, -180.0, este))
    franja = np.abs(np.sin(np.deg2rad(lat_sup)) - np.sin(np.deg2rad(lat_inf)))
    ancho = np.deg2rad(np.clip(lon_sup - lon_inf, 0.0, None))
    return xr.DataArray(np.outer(franja, ancho), coords={"lat": da["lat"], "lon": da["lon"]}, dims=("lat", "lon"))


def fraccion_tierra_desde_malla(malla: xr.DataArray, huella: xr.DataArray) -> xr.DataArray:
    """Fracción de cada celda de `malla` cubierta por las celdas de tierra de `huella` (Down to Earth §02).

    `huella` es un cubo de una fuente que solo tiene datos sobre tierra (GLDAS, 0.25°): una subcelda cuenta como
    tierra si tiene algún dato válido en el período. Para cada celda de `malla` (GPCP 0.5°, MERRA-2 0.5°×0.625°)
    se cuenta qué fracción de las subceldas de `huella` cuyo centro cae dentro de ella son tierra. Así P y T se
    promedian sobre la misma huella terrestre que SM y ET, sin descargar máscaras externas. Las celdas de `malla`
    sin ninguna subcelda de `huella` dentro reciben 0.
    """
    dim_t = "time" if "time" in huella.dims else ("anio" if "anio" in huella.dims else None)
    tierra = huella.notnull().any(dim_t) if dim_t else huella.notnull()
    t_vals = np.asarray(tierra.values, dtype=bool)
    lat_h = np.asarray(tierra["lat"].values, dtype=np.float64)
    lon_h = np.asarray(tierra["lon"].values, dtype=np.float64)
    lat_inf, lat_sup = _bordes_celdas(malla["lat"].values)
    lon_inf, lon_sup = _bordes_celdas(malla["lon"].values)
    frac = np.zeros((lat_inf.size, lon_inf.size), dtype=np.float64)
    for i in range(lat_inf.size):
        fil = (lat_h >= lat_inf[i]) & (lat_h < lat_sup[i])
        if not fil.any():
            continue
        sub_filas = t_vals[fil, :]
        for j in range(lon_inf.size):
            col = (lon_h >= lon_inf[j]) & (lon_h < lon_sup[j])
            if col.any():
                frac[i, j] = float(sub_filas[:, col].mean())
    return xr.DataArray(frac, coords={"lat": malla["lat"], "lon": malla["lon"]}, dims=("lat", "lon"))


def promedio_area(da: xr.DataArray, min_area_valida: float = 0.9,
                  fraccion: xr.DataArray | None = None,
                  pesos: xr.DataArray | None = None) -> xr.DataArray:
    """Promedio espacial ponderado X = Σ(wᵢ·Xᵢ)/Σ(wᵢ) (referencia §1 y Down to Earth §02).

    Por defecto wᵢ = cos(latitud) × `fraccion` (o la coordenada `_fraccion_poligono`). Si se pasa `pesos`
    (p. ej. `pesos_area_region(...) × fraccion_tierra_desde_malla(...)`), se usan tal cual. Si la fracción de área
    válida de la región en un paso de tiempo es < min_area_valida (0.9 por defecto), ese paso se marca como NaN.
    Conserva attrs['units'] y registra la cobertura de área válida en attrs `cobertura_area_*`.
    """
    if not 0.0 <= min_area_valida <= 1.0:
        raise ValueError(f"min_area_valida debe estar entre 0 y 1, no {min_area_valida}")
    attrs = dict(da.attrs)
    if pesos is not None:
        w = pesos.fillna(0.0).clip(min=0.0)
    else:
        lat_2d, _ = xr.broadcast(da["lat"], da["lon"])
        w = np.cos(np.deg2rad(lat_2d)).clip(min=0.0)
        if fraccion is None and "_fraccion_poligono" in da.coords:
            fraccion = da.coords["_fraccion_poligono"]
        if fraccion is not None:
            w = w * fraccion.fillna(0.0)

    dim_tiempo = "time" if "time" in da.dims else ("anio" if "anio" in da.dims else None)
    en_region = da.notnull().any(dim_tiempo) if dim_tiempo else da.notnull()
    peso_total = (w * en_region).sum(("lat", "lon"))
    if float(peso_total) <= 0.0:
        raise ValueError("la región no tiene ninguna celda con datos válidos")

    peso_valido = (w * da.notnull()).sum(("lat", "lon"))
    frac_valida = peso_valido / peso_total
    peso_malla = w.sum(("lat", "lon"))
    frac_malla = peso_valido / peso_malla if float(peso_malla) > 0.0 else frac_valida

    serie = da.weighted(w.fillna(0.0)).mean(("lat", "lon"), skipna=True)
    serie = serie.where(frac_valida >= min_area_valida)
    serie = serie.drop_vars("_fraccion_poligono", errors="ignore")
    frac_arr = np.asarray(frac_malla.values, dtype=np.float64)
    finitos = frac_arr[np.isfinite(frac_arr)]
    if finitos.size > 0:
        attrs["cobertura_area_media"] = float(np.mean(finitos))
        attrs["cobertura_area_min"] = float(np.min(finitos))
        attrs["cobertura_estable"] = bool((np.max(finitos) - np.min(finitos)) <= 0.05)
    serie.attrs = attrs
    serie.name = da.name
    return serie


# ----------------------------------------------------------------------------------------------- 4. Climatología y anomalías
def climatologia(serie: xr.DataArray, base: tuple[str, str] | None = None) -> xr.DataArray:
    """Climatología mensual C_m (m = 1..12) en el periodo base (referencia §2). Funciona en 1-D y 3-D."""
    if "time" not in serie.dims:
        raise ValueError("climatologia requiere dimensión 'time' mensual")
    attrs = dict(serie.attrs)
    sub = serie.sel(time=slice(base[0], base[1])) if base is not None else serie
    if sub.sizes.get("time", 0) == 0:
        raise ValueError(f"no hay datos en el periodo base {base}")
    clim = sub.groupby("time.month").mean("time", skipna=True)

    # Comprobar cobertura por mes en el periodo base (~80 % recomendado en referencia §2).
    if sub.ndim == 1:
        meses_sub = pd.DatetimeIndex(sub["time"].values).month
        validos = sub.notnull().groupby("time.month").sum("time")
        pocos = []
        for m in clim["month"].values:
            n_m = int((meses_sub == int(m)).sum())
            if n_m > 0 and float(validos.sel(month=m)) / n_m < 0.8:
                pocos.append(int(m))
        if pocos:
            attrs["meses_poca_cobertura"] = pocos

    if base is not None:
        attrs["periodo_base"] = [str(base[0]), str(base[1])]
    else:
        fechas = pd.DatetimeIndex(sub["time"].values)
        attrs["periodo_base"] = [fechas[0].strftime("%Y-%m"), fechas[-1].strftime("%Y-%m")]
    clim.attrs = attrs
    return clim


def anomalias(serie: xr.DataArray, clim: xr.DataArray | None = None,
              base: tuple[str, str] | None = None) -> xr.DataArray:
    """Anomalías mensuales y_t = x̄(t) − C_{mes(t)} (referencia §2). Funciona en 1-D y 3-D."""
    if clim is None:
        clim = climatologia(serie, base=base)
    anom = (serie.groupby("time.month") - clim).drop_vars("month", errors="ignore")
    attrs = {**serie.attrs}
    if "periodo_base" in clim.attrs:
        attrs["periodo_base"] = clim.attrs["periodo_base"]
    if "meses_poca_cobertura" in clim.attrs:
        attrs["meses_poca_cobertura"] = clim.attrs["meses_poca_cobertura"]
    if clim.ndim == 1:
        attrs["media_climatologia"] = float(clim.mean("month", skipna=True).values)
    anom.attrs = attrs
    anom.name = serie.name
    return anom


def anomalias_estandarizadas(serie: xr.DataArray, base: tuple[str, str] | None = None,
                             min_valores: int = 2) -> xr.DataArray:
    """Anomalías mensuales estandarizadas z = (valor − μ_mes) / s_mes (Down to Earth §04).

    Para cada mes calendario m = 1..12 calcula el promedio μ_mes y la desviación estándar muestral s_mes (ddof=1)
    en el periodo de referencia `base` (o en toda la serie si `base` es None). Si s_mes = 0 o hay menos de
    `min_valores` datos válidos en ese mes calendario (2 por defecto; Down to Earth usa 10), devuelve NaN en ese
    mes. La serie resultante conserva la tendencia y está en escala adimensional ('1').
    """
    if "time" not in serie.dims:
        raise ValueError("anomalias_estandarizadas requiere dimensión 'time' mensual")
    sub = serie.sel(time=slice(base[0], base[1])) if base is not None else serie
    if sub.sizes.get("time", 0) == 0:
        raise ValueError(f"no hay datos en el periodo base {base}")

    mu_mes = sub.groupby("time.month").mean("time", skipna=True)
    s_mes = sub.groupby("time.month").std("time", ddof=1, skipna=True)
    n_mes = sub.notnull().groupby("time.month").sum("time")
    mu_mes = mu_mes.where(n_mes >= max(2, int(min_valores)))
    s_valida = s_mes.where((s_mes > 0.0) & (n_mes >= max(2, int(min_valores))))

    anom = (serie.groupby("time.month") - mu_mes).drop_vars("month", errors="ignore")
    z = (anom.groupby("time.month") / s_valida).drop_vars("month", errors="ignore")
    attrs = {**serie.attrs, "units": "1", "escala": "z_mensual"}
    if base is not None:
        attrs["periodo_base"] = [str(base[0]), str(base[1])]
    z.attrs = attrs
    z.name = serie.name
    return z


# ----------------------------------------------------------------------------------------------- 5. Agregación anual
def agregar_anual(serie: xr.DataArray, metodo: MetodoAnual) -> xr.DataArray:
    """Agrega una serie mensual por año natural (referencia §3 y Down to Earth §02). Dimensión de salida: 'anio'.

    - metodo='suma': solo para unidades de cantidad ('mm/mes' → 'mm/anio'). Si la serie está en 'mm/dia' u otra
      unidad de tasa, lanza ValueError (convierte antes a 'mm/mes' con cambiar_unidad).
    - metodo='media': promedio aritmético simple de los 12 meses, conserva la unidad.
    - metodo='media_ponderada_dias': promedio mensual ponderado por los días de cada mes
      Σ(X_mes × días_mes) / Σ(días_mes) (Down to Earth §02 para T y SM). Conserva la unidad.
    Solo se agregan años con los 12 meses válidos; un año incompleto queda como NaN.
    """
    if metodo not in ("suma", "media", "media_ponderada_dias"):
        raise ValueError(f"metodo debe ser 'suma', 'media' o 'media_ponderada_dias', no {metodo!r}")
    if "time" not in serie.dims:
        raise ValueError("agregar_anual requiere una serie mensual con dimensión 'time'")
    unidad = serie.attrs.get("units")
    if metodo == "suma" and unidad != "mm/mes":
        raise ValueError(
            f"agregar_anual con metodo='suma' requiere unidades de cantidad 'mm/mes', no {unidad!r}. "
            "Si la lluvia está en 'mm/dia', conviértela antes a 'mm/mes' multiplicando por los días del mes."
        )
    conteo = serie.notnull().groupby("time.year").sum("time")
    if metodo == "suma":
        anual = serie.groupby("time.year").sum("time", skipna=False)
        unidad_salida = "mm/anio"
    elif metodo == "media_ponderada_dias":
        dias = serie["time"].dt.days_in_month.astype(float)
        num = (serie * dias).groupby("time.year").sum("time", skipna=False)
        den = dias.where(serie.notnull()).groupby("time.year").sum("time", skipna=False)
        anual = num / den
        unidad_salida = unidad
    else:
        anual = serie.groupby("time.year").mean("time", skipna=False)
        unidad_salida = unidad
    anual = anual.where(conteo == 12).rename(year="anio")
    anual = anual.assign_coords(anio=anual["anio"].values.astype(int))
    attrs = {**serie.attrs, "metodo_agregacion_anual": metodo}
    if unidad_salida is not None:
        attrs["units"] = unidad_salida
    anual.attrs = attrs
    anual.name = serie.name
    return anual


# ----------------------------------------------------------------------------------------------- 6. Control de calidad
def reindexar_calendario(serie: xr.DataArray, inicio: str, fin: str) -> xr.DataArray:
    """Reindexa la serie al calendario completo entre inicio y fin; fechas ausentes aparecen como NaN."""
    attrs = dict(serie.attrs)
    if "time" in serie.dims:
        ini = f"{inicio[:7]}-01"
        fn = f"{fin[:7]}-01"
        calendario = pd.date_range(ini, fn, freq="MS")
        fechas = pd.DatetimeIndex(serie["time"].values).to_period("M").to_timestamp()
        out = serie.assign_coords(time=fechas).reindex(time=calendario)
    elif "anio" in serie.dims:
        anios = np.arange(int(str(inicio)[:4]), int(str(fin)[:4]) + 1, dtype=int)
        out = serie.assign_coords(anio=serie["anio"].values.astype(int)).reindex(anio=anios)
    else:
        raise ValueError("la serie debe tener dimensión 'time' (mensual) o 'anio' (anual)")
    out.attrs = attrs
    out.name = serie.name
    return out


def control_calidad(serie: xr.DataArray, inicio: str, fin: str, max_faltantes: float = 0.10,
                    *, lanzar: bool = True) -> dict[str, Any]:
    """Evalúa datos faltantes en el calendario completo [inicio, fin] (referencia §4).

    Devuelve {'aceptada', 'n_esperados', 'n_faltantes', 'fraccion_faltante', 'motivo'}.
    Si fraccion_faltante > max_faltantes y lanzar=True, lanza SerieRechazada(..., reporte).
    """
    reind = reindexar_calendario(serie, inicio, fin)
    n_esperados = int(reind.size)
    if n_esperados == 0:
        reporte = {"aceptada": False, "n_esperados": 0, "n_faltantes": 0,
                   "fraccion_faltante": 1.0, "motivo": "periodo vacío"}
        if lanzar:
            raise SerieRechazada("periodo vacío (0 pasos de tiempo)", reporte)
        return reporte
    n_faltantes = int(np.isnan(reind.values).sum())
    fraccion = float(n_faltantes / n_esperados)
    aceptada = fraccion <= max_faltantes + 1e-12
    nombre = serie.name or serie.attrs.get("variable", "serie")
    motivo = None if aceptada else (
        f"{nombre}: {100.0 * fraccion:.1f} % de datos faltantes "
        f"({n_faltantes}/{n_esperados}, máximo {100.0 * max_faltantes:.0f} %)"
    )
    reporte = {
        "aceptada": aceptada,
        "n_esperados": n_esperados,
        "n_faltantes": n_faltantes,
        "fraccion_faltante": fraccion,
        "motivo": motivo,
    }
    if not aceptada and lanzar:
        raise SerieRechazada(motivo or "serie rechazada por datos faltantes", reporte)
    return reporte


# ----------------------------------------------------------------------------------------------- 7. Entrada del motor
def preparar_para_motor(serie: xr.DataArray, media_climatologia: float | None = None) -> dict[str, Any]:
    """Empaqueta una serie 1-D en el dict que espera motor.tendencias.calcular_tendencia (referencia §5)."""
    if media_climatologia is None and "media_climatologia" in serie.attrs:
        media_climatologia = float(serie.attrs["media_climatologia"])
    if "time" in serie.dims:
        fechas = pd.DatetimeIndex(serie["time"].values)
        t = (fechas.year - fechas.year[0]) * 12 + (fechas.month - fechas.month[0])
        unidad: Literal["mes", "anio"] = "mes"
        periodo = (fechas[0].strftime("%Y-%m"), fechas[-1].strftime("%Y-%m"))
    elif "anio" in serie.dims:
        t = serie["anio"].values.astype(float)
        unidad = "anio"
        periodo = (str(int(t[0])), str(int(t[-1])))
    else:
        raise ValueError("la serie debe tener dimensión 'time' o 'anio'")
    return {
        "y": serie.values.astype(float),
        "t": np.asarray(t, dtype=float),
        "unidad_tiempo": unidad,
        "periodo": periodo,
        "media_climatologia": media_climatologia,
    }


def serie_region(
    da: xr.DataArray,
    bbox_o_geojson: BBox | str | Path | dict | gpd.GeoDataFrame | None,
    inicio: str,
    fin: str,
    *,
    mascara: xr.DataArray | Literal["tierra"] | None = None,
    anual: MetodoAnual | None = None,
    periodo_base: tuple[str, str] | None = None,
    min_area_valida: float = 0.9,
    max_faltantes: float = 0.10,
) -> tuple[xr.DataArray, dict[str, Any]]:
    """Flujo completo del cubo a la serie de una región (pasos 1–6 en orden).

    Devuelve (serie_para_motor, reporte_calidad).
    - Para análisis mensual: serie_para_motor son las anomalías mensuales con attrs['media_climatologia'].
    - Para análisis anual (o si da ya tiene dimensión 'anio'): serie_para_motor es la serie anual.
    """
    cubo = da
    if bbox_o_geojson is not None and ("lat" in cubo.dims and "lon" in cubo.dims):
        if isinstance(bbox_o_geojson, (tuple, list)) and len(bbox_o_geojson) == 4:
            cubo = recortar_bbox(cubo, (float(bbox_o_geojson[0]), float(bbox_o_geojson[1]),
                                        float(bbox_o_geojson[2]), float(bbox_o_geojson[3])))
        else:
            cubo = recortar_poligono(cubo, bbox_o_geojson)

    if mascara is not None and ("lat" in cubo.dims and "lon" in cubo.dims):
        cubo = aplicar_mascara(cubo, mascara)

    if "lat" in cubo.dims and "lon" in cubo.dims:
        serie_abs = promedio_area(cubo, min_area_valida=min_area_valida)
    else:
        serie_abs = cubo.copy()

    if "time" in serie_abs.dims:
        serie_abs = reindexar_calendario(serie_abs, inicio, fin)
        reporte = control_calidad(serie_abs, inicio, fin, max_faltantes=max_faltantes, lanzar=True)
        if anual is not None:
            fuente_anual = cambiar_unidad(serie_abs, "mm/mes") if (
                anual == "suma" and serie_abs.attrs.get("units") == "mm/dia"
            ) else serie_abs
            serie_out = agregar_anual(fuente_anual, anual)
            serie_out = reindexar_calendario(serie_out, inicio[:4], fin[:4])
            # Un mes faltante anula su año entero: 10 % de meses faltantes repartidos pueden dejar
            # todos los años en NaN. Por eso la serie anual pasa también su propio control de calidad.
            reporte["anual"] = control_calidad(serie_out, inicio[:4], fin[:4],
                                               max_faltantes=max_faltantes, lanzar=True)
            vals = serie_out.values
            media_anual = float(np.nanmean(vals)) if np.isfinite(vals).any() else None
            if media_anual is not None:
                serie_out.attrs["media_climatologia"] = media_anual
        else:
            base = periodo_base or (inicio, fin)
            clim = climatologia(serie_abs, base=base)
            serie_out = anomalias(serie_abs, clim=clim)
            if "meses_poca_cobertura" in clim.attrs:
                reporte["meses_poca_cobertura"] = clim.attrs["meses_poca_cobertura"]
    elif "anio" in serie_abs.dims:
        serie_out = reindexar_calendario(serie_abs, inicio[:4], fin[:4])
        reporte = control_calidad(serie_out, inicio[:4], fin[:4], max_faltantes=max_faltantes, lanzar=True)
        vals = serie_out.values
        if np.isfinite(vals).any():
            serie_out.attrs["media_climatologia"] = float(np.nanmean(vals))
    else:
        raise ValueError("el DataArray debe tener dimensión 'time' o 'anio'")

    return serie_out, reporte
