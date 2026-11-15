"""Servicios de consulta para la API: catálogo, series, tendencias, indicadores, escáner, dos caras y mapas."""
from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Any, Literal, Sequence

import numpy as np
import pandas as pd
import xarray as xr

from core.config import PERIODO_COMUN, obtener_ajustes
from core.motor.catalogo import cambiar_unidad, cargar_catalogo, cargar_datasets
from core.motor.datos import (
    BBox,
    DatosNoDisponibles,
    buscar_en_memoria,
    construir_url_opendap_subset,
    indices_bbox_grilla,
    inventario_cache,
    limpiar_cache_memoria,
    obtener_variable,
    validar_periodo,
)
from core.motor.down_to_earth import (
    INFO_VARIABLES_DTE,
    ORDEN_VARIABLES_DTE,
    PARES_PRIORITARIOS_DTE,
    PERIODO_DTE_DEFECTO,
    analizar_cuatro_variables_dte,
    generar_csv_anual_dte,
    generar_csv_mensual_dte,
)
from core.motor.escaner import (
    comparar_dos_caras,
    escanear_region,
    mapa_tendencias,
    obtener_mapa_tendencias,
)
from core.motor.indicadores import UNIDADES_INDICADORES, indicadores_anuales, serie_indicador_region
from core.motor.series import (
    MetodoAnual,
    SerieRechazada,
    agregar_anual,
    anomalias,
    aplicar_mascara,
    climatologia,
    control_calidad,
    preparar_para_motor,
    promedio_area,
    recortar_bbox,
    reindexar_calendario,
)
from core.motor.tendencias import calcular_tendencia, ols
from core.servicios.regiones import RegionResuelta, cargar_regiones, resolver_region


def _limpiar_float(v: Any) -> float | None:
    if v is None:
        return None
    f = float(v)
    return f if np.isfinite(f) else None


def _matriz_json(arr: np.ndarray) -> list[list[float | None]]:
    arr2d = np.asarray(arr, dtype=np.float64)
    return [[_limpiar_float(x) for x in fila] for fila in arr2d]


@lru_cache(maxsize=4)
def _catalogo_en_memoria(ruta: str) -> dict[str, dict]:
    return cargar_catalogo(ruta)


@lru_cache(maxsize=4)
def _datasets_en_memoria(ruta: str) -> dict[str, dict]:
    return cargar_datasets(ruta)


def obtener_catalogo() -> dict[str, dict]:
    return _catalogo_en_memoria(str(obtener_ajustes().ruta_catalogo))


def obtener_datasets() -> dict[str, dict]:
    return _datasets_en_memoria(str(obtener_ajustes().ruta_catalogo))


def _es_analizable(entrada: dict) -> bool:
    """True si la variable produce directamente una serie mensual o anual para el motor de tendencias."""
    return entrada["frecuencia"] in ("mensual", "anual")


# ----------------------------------------------------------------------------------------------- Catálogo y datasets
def consultar_datasets() -> list[dict[str, Any]]:
    catalogo = obtener_catalogo()
    datasets = obtener_datasets()
    salida: list[dict[str, Any]] = []
    for did, ds in datasets.items():
        vars_ds = [
            {
                "id": v["id"],
                "nombre_simple": v["nombre_simple"],
                "definicion_simple": v["definicion_simple"],
                "grupo": v["grupo"],
                "short_name": v["short_name"],
                "variable_archivo": v["variable"],
                "unidad_original": v["unidad_original"],
                "unidad_final": v["unidad_final"],
                "conversion": v["conversion"],
                "frecuencia": v["frecuencia"],
                "desde": str(v["desde"]),
                "resolucion": v["resolucion"],
                "analizable": _es_analizable(v),
            }
            for v in catalogo.values()
            if v.get("fuente") == did
        ]
        salida.append({**ds, "variables": vars_ds})
    return salida


def consultar_variables(
    *,
    grupo: str | None = None,
    fuente: str | None = None,
    frecuencia: str | None = None,
    solo_analizables: bool = False,
) -> list[dict[str, Any]]:
    catalogo = obtener_catalogo()
    res: list[dict[str, Any]] = []
    for vid, v in catalogo.items():
        if grupo and v["grupo"] != grupo:
            continue
        if fuente and v.get("fuente") != fuente:
            continue
        if frecuencia and v["frecuencia"] != frecuencia:
            continue
        if solo_analizables and not _es_analizable(v):
            continue
        res.append({
            **v,
            "desde": str(v["desde"]),
            "analizable": _es_analizable(v),
            "archivos_en_cache": len(inventario_cache(vid)),
        })
    return res


def consultar_variable_detalle(variable_id: str) -> dict[str, Any]:
    catalogo = obtener_catalogo()
    if variable_id not in catalogo:
        raise KeyError(f"Variable '{variable_id}' no existe en el catálogo (válidas: {sorted(catalogo)})")
    v = catalogo[variable_id]
    return {
        **v,
        "desde": str(v["desde"]),
        "analizable": _es_analizable(v),
        "cache": inventario_cache(variable_id),
    }


def estado_cache_region(
    variable_id: str,
    region: str,
    inicio: str,
    fin: str,
) -> bool:
    catalogo = obtener_catalogo()
    entrada = catalogo[variable_id]
    var_real = entrada["origen"] if entrada["grupo"] == "calculada" else variable_id
    return buscar_en_memoria(var_real, region, inicio, fin) is not None


def describir_consulta_opendap(
    variable_id: str,
    *,
    region: str | None = None,
    bbox: Sequence[float] | None = None,
    inicio: str = PERIODO_COMUN[0],
    fin: str = PERIODO_COMUN[1],
) -> dict[str, Any]:
    """Devuelve los índices espaciales y las expresiones OPeNDAP (DAP4 y DAP2) para una variable y región."""
    validar_periodo(inicio, fin)
    reg = resolver_region(region, bbox)
    catalogo = obtener_catalogo()
    datasets = obtener_datasets()
    if variable_id not in catalogo:
        raise KeyError(f"Variable '{variable_id}' no existe en el catálogo (válidas: {sorted(catalogo)})")
    entrada = catalogo[variable_id]
    var_real = entrada["origen"] if entrada["grupo"] == "calculada" else variable_id
    ent_real = catalogo[var_real]
    ds_info = datasets.get(ent_real.get("fuente", ""), {})
    base_ejemplo = f"{ds_info.get('opendap_base', 'https://gesdisc.earthdata.nasa.gov/opendap')}/{ent_real['short_name']}_granulo.nc4"

    grilla = ent_real.get("grilla")
    lat_slice, lon_slice = indices_bbox_grilla(grilla, reg.bbox) if grilla else (None, None)
    return {
        "variable": variable_id,
        "variable_opendap": var_real,
        "short_name": ent_real["short_name"],
        "version": ent_real.get("version"),
        "variable_archivo": ent_real["variable"],
        "grupo_hdf": ent_real.get("grupo_hdf"),
        "region": reg.a_dict(),
        "periodo": [inicio, fin],
        "almacenamiento_disco": False,
        "indices_espaciales": {
            "lat_slice": list(lat_slice) if lat_slice else None,
            "lon_slice": list(lon_slice) if lon_slice else None,
            "n_lat": (lat_slice[1] - lat_slice[0] + 1) if lat_slice else None,
            "n_lon": (lon_slice[1] - lon_slice[0] + 1) if lon_slice else None,
        },
        "ejemplo_url_dap4": construir_url_opendap_subset(
            base_ejemplo, ent_real, reg.bbox, protocolo="dap4", lat_slice=lat_slice, lon_slice=lon_slice
        ),
        "ejemplo_url_dap2": construir_url_opendap_subset(
            base_ejemplo, ent_real, reg.bbox, protocolo="dap2", lat_slice=lat_slice, lon_slice=lon_slice
        ),
        "en_memoria_ram": buscar_en_memoria(var_real, reg.id, inicio, fin) is not None,
    }


# ----------------------------------------------------------------------------------------------- Generador sintético (modo demo)
def _semilla_estable(*partes: str) -> int:
    h = hashlib.sha256("::".join(partes).encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big")


def _cubo_sintetico(
    variable: str,
    entrada: dict,
    reg: RegionResuelta,
    inicio: str,
    fin: str,
) -> xr.DataArray:
    """Genera un cubo 3-D determinista (con estacionalidad, tendencia y ruido AR(1)) para pruebas de frontend."""
    oeste, sur, este, norte = reg.bbox
    lats = np.linspace(sur + 0.25, norte - 0.25, 4) if norte - sur > 0.6 else np.array([(sur + norte) / 2.0])
    lons = np.linspace(oeste + 0.25, este - 0.25, 4) if este - oeste > 0.6 else np.array([(oeste + este) / 2.0])
    rng = np.random.default_rng(_semilla_estable(variable, reg.id))

    # Signo determinista según región para que 'sahel' y 'sureste_mexico' permitan probar "las dos caras".
    signos_predefinidos = {
        "sahel": -1.0,
        "noreste_mexico": -1.0,
        "amazonia": -1.0,
        "sureste_mexico": 1.0,
        "india_monzon": 1.0,
    }
    signo = signos_predefinidos.get(reg.id, -1.0 if _semilla_estable(reg.id) % 2 == 0 else 1.0)

    if entrada["frecuencia"] == "diaria":
        fechas = pd.date_range(f"{inicio}-01", f"{fin}-28", freq="D")
        n_t = len(fechas)
        t_anios = (fechas.year - fechas.year[0]).values.astype(float)
        est = 0.5 + 0.5 * np.sin(2.0 * np.pi * fechas.day_of_year.values / 365.25)
        prob_lluvia = np.clip(0.28 + 0.004 * signo * t_anios, 0.05, 0.65)[:, None, None] * est[:, None, None]
        llueve = rng.random((n_t, lats.size, lons.size)) < prob_lluvia
        escala = np.clip(8.0 + 0.15 * signo * t_anios, 3.0, 20.0)[:, None, None]
        datos = np.where(llueve, rng.gamma(shape=1.4, scale=escala, size=(n_t, lats.size, lons.size)), 0.0)
        da = xr.DataArray(
            datos,
            coords={"time": fechas, "lat": lats, "lon": lons},
            dims=("time", "lat", "lon"),
            name=variable,
            attrs={"units": entrada["unidad_final"], "fuente_datos": "sintetico"},
        )
        return da

    fechas = pd.date_range(f"{inicio}-01", f"{fin}-01", freq="MS")
    n_t = len(fechas)
    t_idx = np.arange(n_t, dtype=np.float64)
    meses = fechas.month.values

    unidad = entrada["unidad_final"]
    if variable == "evapotranspiracion":
        base, amp, pend, sigma = 45.0, 18.0, signo * 0.035, 4.2
    elif unidad == "mm/mes":
        base, amp, pend, sigma = 85.0, 35.0, signo * 0.06, 8.0
    elif unidad == "mm/dia":
        base, amp, pend, sigma = 2.8, 1.2, signo * 0.002, 0.28
    elif unidad == "degC":
        base, amp, pend, sigma = 24.0, 5.0, 0.006, 0.45
    elif unidad == "m3/m3":
        base, amp, pend, sigma = 0.22, 0.055, signo * 0.00018, 0.014
    elif unidad == "mm":
        base, amp, pend, sigma = 28.0, 6.0, signo * 0.008, 1.2
    else:
        base, amp, pend, sigma = 10.0, 2.0, signo * 0.01, 0.5

    estacional = amp * np.sin(2.0 * np.pi * (meses - 4) / 12.0)
    phi = 0.35
    eta = rng.normal(0.0, sigma * np.sqrt(1.0 - phi**2), size=(n_t, lats.size, lons.size))
    ruido = np.empty_like(eta)
    ruido[0] = rng.normal(0.0, sigma, size=(lats.size, lons.size))
    for i in range(1, n_t):
        ruido[i] = phi * ruido[i - 1] + eta[i]

    # Pulso hídrico intermensual común por región para reproducir covariación física en modo demo
    rng_reg = np.random.default_rng(_semilla_estable("pulso_hidrico_dte", reg.id))
    pulso = rng_reg.normal(0.0, 1.0, size=n_t)
    if variable in ("lluvia_gpcp", "lluvia_imerg_mes"):
        ruido = ruido + (0.55 * sigma * pulso)[:, None, None]
    elif variable == "humedad_suelo":
        ruido = ruido + (0.60 * sigma * pulso)[:, None, None]
    elif variable == "evapotranspiracion":
        ruido = ruido + (0.50 * sigma * pulso)[:, None, None]
    elif variable == "temp_aire":
        ruido = ruido - (0.45 * sigma * pulso)[:, None, None]

    grad_lat = np.linspace(-0.08, 0.08, lats.size)[None, :, None] * base
    grad_lon = np.linspace(-0.05, 0.05, lons.size)[None, None, :] * base
    valores = base + estacional[:, None, None] + (pend * t_idx)[:, None, None] + grad_lat + grad_lon + ruido
    if unidad in ("mm/mes", "mm/dia", "mm"):
        valores = np.clip(valores, 0.0, None)
    elif unidad == "m3/m3":
        valores = np.clip(valores, 0.01, 0.60)

    return xr.DataArray(
        valores,
        coords={"time": fechas, "lat": lats, "lon": lons},
        dims=("time", "lat", "lon"),
        name=variable,
        attrs={"units": unidad, "fuente_datos": "sintetico"},
    )


def _obtener_cubo(
    variable: str,
    reg: RegionResuelta,
    inicio: str,
    fin: str,
    *,
    descargar: bool = False,
    sintetico: bool = False,
) -> tuple[xr.DataArray, str]:
    """Devuelve (cubo_3d, fuente_datos) donde fuente_datos es 'opendap_memoria' o 'sintetico'."""
    catalogo = obtener_catalogo()
    if variable not in catalogo:
        raise KeyError(f"Variable '{variable}' no existe en el catálogo (válidas: {sorted(catalogo)})")
    entrada = catalogo[variable]
    if sintetico:
        return _cubo_sintetico(variable, entrada, reg, inicio, fin), "sintetico"
    da = obtener_variable(variable, reg.id, reg.bbox, inicio, fin, catalogo, descargar=descargar)
    try:
        da = recortar_bbox(da, reg.bbox)
    except ValueError:
        limpiar_cache_memoria(variable)
        if not descargar:
            raise
        da = obtener_variable(variable, reg.id, reg.bbox, inicio, fin, catalogo, descargar=True)
        da = recortar_bbox(da, reg.bbox)
    return da, "opendap_memoria"


# ----------------------------------------------------------------------------------------------- Consultas de series y tendencias
def _construir_serie_y_motor(
    variable: str,
    reg: RegionResuelta,
    inicio: str,
    fin: str,
    *,
    anual: MetodoAnual | None = None,
    unidad: str | None = None,
    mascara: Literal["tierra"] | None = None,
    periodo_base: tuple[str, str] | None = None,
    descargar: bool = False,
    sintetico: bool = False,
) -> dict[str, Any]:
    """Prepara la serie absoluta, las anomalías (si es mensual), la climatología y la entrada del motor."""
    validar_periodo(inicio, fin)
    catalogo = obtener_catalogo()
    if variable not in catalogo:
        raise KeyError(f"Variable '{variable}' no existe en el catálogo (válidas: {sorted(catalogo)})")
    entrada = catalogo[variable]

    if entrada["frecuencia"] == "diaria":
        raise ValueError(
            f"'{variable}' es diaria y no se analiza directamente; consulta sus indicadores anuales: "
            "cdd_imerg, r20mm_imerg, dias_humedos_imerg, prcptot_imerg o sdii_imerg."
        )

    if entrada["grupo"] == "calculada":
        origen = entrada["origen"]
        indicador = entrada["indicador"]
        cubo_diario, fuente = _obtener_cubo(origen, reg, inicio, fin, descargar=descargar, sintetico=sintetico)
        if mascara == "tierra":
            cubo_diario = aplicar_mascara(cubo_diario, "tierra")
        serie_ind = serie_indicador_region(cubo_diario, indicador)
        serie_ind = reindexar_calendario(serie_ind, inicio[:4], fin[:4])
        calidad = control_calidad(serie_ind, inicio[:4], fin[:4], lanzar=True)
        vals = serie_ind.values.astype(float)
        media_clim = float(np.nanmean(vals)) if np.isfinite(vals).any() else None
        serie_ind.attrs["media_climatologia"] = media_clim
        em = preparar_para_motor(serie_ind, media_climatologia=media_clim)
        puntos = [
            {
                "fecha": str(int(a)),
                "t": float(t_i),
                "valor": _limpiar_float(v),
                "anomalia": None,
            }
            for a, t_i, v in zip(serie_ind["anio"].values, em["t"], vals)
        ]
        return {
            "entrada": entrada,
            "unidad": serie_ind.attrs.get("units", entrada["unidad_final"]),
            "frecuencia_serie": "anual",
            "serie_motor": serie_ind,
            "entrada_motor": em,
            "media_climatologia": _limpiar_float(media_clim),
            "climatologia_mensual": None,
            "puntos": puntos,
            "calidad": calidad,
            "fuente_datos": fuente,
        }

    cubo, fuente = _obtener_cubo(variable, reg, inicio, fin, descargar=descargar, sintetico=sintetico)
    if mascara == "tierra":
        cubo = aplicar_mascara(cubo, "tierra")
    if unidad and unidad != cubo.attrs.get("units"):
        cubo = cambiar_unidad(cubo, unidad)

    serie_abs = promedio_area(cubo)
    serie_abs = reindexar_calendario(serie_abs, inicio, fin)
    calidad = control_calidad(serie_abs, inicio, fin, lanzar=True)

    if anual is not None:
        metodo_agg: MetodoAnual = anual
        fuente_anual = (
            cambiar_unidad(serie_abs, "mm/mes")
            if metodo_agg == "suma" and serie_abs.attrs.get("units") == "mm/dia"
            else serie_abs
        )
        serie_anual = agregar_anual(fuente_anual, metodo_agg)
        serie_anual = reindexar_calendario(serie_anual, inicio[:4], fin[:4])
        # Un mes faltante anula su año: la serie anual necesita su propio control de calidad.
        calidad = {**calidad, "anual": control_calidad(serie_anual, inicio[:4], fin[:4], lanzar=True)}
        vals = serie_anual.values.astype(float)
        media_clim = float(np.nanmean(vals)) if np.isfinite(vals).any() else None
        serie_anual.attrs["media_climatologia"] = media_clim
        em = preparar_para_motor(serie_anual, media_climatologia=media_clim)
        puntos = [
            {
                "fecha": str(int(a)),
                "t": float(t_i),
                "valor": _limpiar_float(v),
                "anomalia": None,
            }
            for a, t_i, v in zip(serie_anual["anio"].values, em["t"], vals)
        ]
        return {
            "entrada": entrada,
            "unidad": serie_anual.attrs.get("units", entrada["unidad_final"]),
            "frecuencia_serie": "anual",
            "serie_motor": serie_anual,
            "entrada_motor": em,
            "media_climatologia": _limpiar_float(media_clim),
            "climatologia_mensual": None,
            "puntos": puntos,
            "calidad": calidad,
            "fuente_datos": fuente,
        }

    base = periodo_base or (inicio, fin)
    clim = climatologia(serie_abs, base=base)
    anom = anomalias(serie_abs, clim=clim)
    media_clim = anom.attrs.get("media_climatologia")
    em = preparar_para_motor(anom, media_climatologia=media_clim)

    fechas = pd.DatetimeIndex(serie_abs["time"].values)
    puntos = [
        {
            "fecha": f.strftime("%Y-%m"),
            "t": float(t_i),
            "valor": _limpiar_float(v_abs),
            "anomalia": _limpiar_float(v_anom),
        }
        for f, t_i, v_abs, v_anom in zip(fechas, em["t"], serie_abs.values, anom.values)
    ]
    clim_lista = [
        {"mes": int(m), "valor": _limpiar_float(v)}
        for m, v in zip(clim["month"].values, clim.values)
    ]
    return {
        "entrada": entrada,
        "unidad": anom.attrs.get("units", entrada["unidad_final"]),
        "frecuencia_serie": "mensual",
        "serie_motor": anom,
        "entrada_motor": em,
        "media_climatologia": _limpiar_float(media_clim),
        "climatologia_mensual": clim_lista,
        "puntos": puntos,
        "calidad": calidad,
        "fuente_datos": fuente,
    }


def consultar_serie(
    variable: str,
    *,
    region: str | None = None,
    bbox: Sequence[float] | None = None,
    inicio: str = PERIODO_COMUN[0],
    fin: str = PERIODO_COMUN[1],
    anual: MetodoAnual | None = None,
    unidad: str | None = None,
    mascara: Literal["tierra"] | None = None,
    periodo_base: tuple[str, str] | None = None,
    descargar: bool = False,
    sintetico: bool = False,
) -> dict[str, Any]:
    """Devuelve la serie preprocesada (valores absolutos, anomalías, climatología y reporte de calidad)."""
    reg = resolver_region(region, bbox)
    info = _construir_serie_y_motor(
        variable,
        reg,
        inicio,
        fin,
        anual=anual,
        unidad=unidad,
        mascara=mascara,
        periodo_base=periodo_base,
        descargar=descargar,
        sintetico=sintetico,
    )
    e = info["entrada"]
    return {
        "variable": variable,
        "nombre_simple": e["nombre_simple"],
        "definicion_simple": e["definicion_simple"],
        "grupo": e["grupo"],
        "dataset": e["dataset"],
        "short_name": e["short_name"],
        "unidad": info["unidad"],
        "frecuencia_serie": info["frecuencia_serie"],
        "region": reg.a_dict(),
        "periodo": list(info["entrada_motor"]["periodo"]),
        "media_climatologia": info["media_climatologia"],
        "climatologia_mensual": info["climatologia_mensual"],
        "calidad": info["calidad"],
        "puntos": info["puntos"],
        "fuente_datos": info["fuente_datos"],
    }


def consultar_tendencia(
    variable: str,
    *,
    region: str | None = None,
    bbox: Sequence[float] | None = None,
    inicio: str = PERIODO_COMUN[0],
    fin: str = PERIODO_COMUN[1],
    anual: MetodoAnual | None = None,
    unidad: str | None = None,
    mascara: Literal["tierra"] | None = None,
    periodo_base: tuple[str, str] | None = None,
    alfa: float = 0.05,
    incluir_serie: bool = True,
    descargar: bool = False,
    sintetico: bool = False,
) -> dict[str, Any]:
    """Calcula la tendencia y veredicto oficial del motor para una variable y región."""
    reg = resolver_region(region, bbox)
    info = _construir_serie_y_motor(
        variable,
        reg,
        inicio,
        fin,
        anual=anual,
        unidad=unidad,
        mascara=mascara,
        periodo_base=periodo_base,
        descargar=descargar,
        sintetico=sintetico,
    )
    em = info["entrada_motor"]
    resultado_motor = calcular_tendencia(
        em["y"],
        em["t"],
        unidad_tiempo=em["unidad_tiempo"],
        variable=variable,
        region=reg.id,
        periodo=em["periodo"],
        media_climatologia=em["media_climatologia"],
        alfa=alfa,
    )

    # Recta OLS ajustada sobre los datos válidos para que el frontend la dibuje sin recalcular.
    valido = np.isfinite(em["y"]) & np.isfinite(em["t"])
    ajuste = ols(em["y"][valido], em["t"][valido])

    e = info["entrada"]
    respuesta: dict[str, Any] = {
        "tendencia": resultado_motor,
        "metadatos": {
            "nombre_simple": e["nombre_simple"],
            "definicion_simple": e["definicion_simple"],
            "grupo": e["grupo"],
            "dataset": e["dataset"],
            "short_name": e["short_name"],
            "unidad": info["unidad"],
            "unidad_pendiente": f"{info['unidad']}/decada",
            "frecuencia_serie": info["frecuencia_serie"],
            "region": reg.a_dict(),
            "media_climatologia": info["media_climatologia"],
            "recta_ols": {
                "beta0": float(ajuste.beta0),
                "beta1_por_paso": float(ajuste.beta1),
            },
            "calidad": info["calidad"],
            "fuente_datos": info["fuente_datos"],
        },
    }
    if incluir_serie:
        respuesta["puntos"] = info["puntos"]
        respuesta["climatologia_mensual"] = info["climatologia_mensual"]
    return respuesta


# ----------------------------------------------------------------------------------------------- Indicadores de lluvia
def consultar_indicadores(
    *,
    region: str | None = None,
    bbox: Sequence[float] | None = None,
    inicio: str = PERIODO_COMUN[0],
    fin: str = PERIODO_COMUN[1],
    cortar_en_anio: bool = True,
    mascara: Literal["tierra"] | None = None,
    alfa: float = 0.05,
    descargar: bool = False,
    sintetico: bool = False,
) -> dict[str, Any]:
    """Calcula los 5 indicadores anuales (CDD, R20mm, W, PRCPTOT, SDII) y sus tendencias a partir de IMERG diario."""
    validar_periodo(inicio, fin)
    reg = resolver_region(region, bbox)
    catalogo = obtener_catalogo()
    cubo_diario, fuente = _obtener_cubo(
        "lluvia_imerg_dia", reg, inicio, fin, descargar=descargar, sintetico=sintetico
    )
    if mascara == "tierra":
        cubo_diario = aplicar_mascara(cubo_diario, "tierra")

    ds_pixel = indicadores_anuales(cubo_diario, cortar_en_anio=cortar_en_anio)
    mapa_ids = {
        "cdd": "cdd_imerg",
        "r20mm": "r20mm_imerg",
        "dias_humedos": "dias_humedos_imerg",
        "prcptot": "prcptot_imerg",
        "sdii": "sdii_imerg",
    }

    indicadores_out: dict[str, Any] = {}
    tendencias_por_id: dict[str, dict[str, Any]] = {}
    for ind_key, vid in mapa_ids.items():
        da_ind = promedio_area(ds_pixel[ind_key]) if ("lat" in ds_pixel.dims and "lon" in ds_pixel.dims) else ds_pixel[ind_key]
        da_ind = reindexar_calendario(da_ind, inicio[:4], fin[:4])
        da_ind.name = vid
        # Misma regla que /tendencias/{indicador}: más de 10 % de años faltantes → SerieRechazada (HTTP 422).
        calidad = control_calidad(da_ind, inicio[:4], fin[:4], lanzar=True)
        vals = da_ind.values.astype(float)
        media_clim = float(np.nanmean(vals)) if np.isfinite(vals).any() else None
        em = preparar_para_motor(da_ind, media_climatologia=media_clim)
        tend = calcular_tendencia(
            em["y"],
            em["t"],
            unidad_tiempo="anio",
            variable=vid,
            region=reg.id,
            periodo=em["periodo"],
            media_climatologia=media_clim,
            alfa=alfa,
        )
        tendencias_por_id[vid] = tend
        e = catalogo[vid]
        indicadores_out[vid] = {
            "id": vid,
            "indicador": ind_key,
            "nombre_simple": e["nombre_simple"],
            "definicion_simple": e["definicion_simple"],
            "unidad": UNIDADES_INDICADORES[ind_key],
            "serie": [
                {"anio": int(a), "valor": _limpiar_float(v)}
                for a, v in zip(da_ind["anio"].values, vals)
            ],
            "tendencia": tend,
            "calidad": calidad,
        }

    # ¿Se alargan las rachas secas a la vez que cambian los días de tormenta?
    dos_caras_extremos = comparar_dos_caras(
        tendencias_por_id["cdd_imerg"],
        tendencias_por_id["r20mm_imerg"],
    )
    return {
        "region": reg.a_dict(),
        "periodo": [inicio[:4], fin[:4]],
        "cortar_en_anio": cortar_en_anio,
        "fuente_datos": fuente,
        "indicadores": indicadores_out,
        "dos_caras_extremos": dos_caras_extremos,
    }


# ----------------------------------------------------------------------------------------------- Escáner y dos caras
def ejecutar_escaner_region(
    *,
    region: str | None = None,
    bbox: Sequence[float] | None = None,
    inicio: str = PERIODO_COMUN[0],
    fin: str = PERIODO_COMUN[1],
    variables: list[str] | None = None,
    grupo: str | None = None,
    fuente: str | None = None,
    alfa: float = 0.05,
    descargar: bool = False,
    sintetico: bool = False,
) -> dict[str, Any]:
    """Escanea múltiples variables en una región y las devuelve ordenadas por veredicto y |SNR|."""
    validar_periodo(inicio, fin)
    reg = resolver_region(region, bbox)
    catalogo = obtener_catalogo()

    if variables is not None:
        ids = []
        for v in variables:
            if v not in catalogo:
                raise KeyError(f"Variable '{v}' no existe en el catálogo")
            if _es_analizable(catalogo[v]):
                ids.append(v)
    else:
        ids = [
            v["id"]
            for v in consultar_variables(grupo=grupo, fuente=fuente, solo_analizables=True)
        ]

    series_preparadas: dict[str, xr.DataArray | SerieRechazada] = {}
    medias: dict[str, float | None] = {}
    fuentes_usadas: set[str] = set()

    for vid in ids:
        try:
            info = _construir_serie_y_motor(
                vid, reg, inicio, fin, descargar=descargar, sintetico=sintetico
            )
            series_preparadas[vid] = info["serie_motor"]
            medias[vid] = info["media_climatologia"]
            fuentes_usadas.add(info["fuente_datos"])
        except SerieRechazada as exc:
            series_preparadas[vid] = exc
        except DatosNoDisponibles as exc:
            series_preparadas[vid] = SerieRechazada(
                f"no disponible en caché ({exc.inicio} → {exc.fin})",
                {"aceptada": False, "motivo": "no disponible en caché"},
            )
        except ValueError as exc:
            series_preparadas[vid] = SerieRechazada(str(exc), {"aceptada": False, "motivo": str(exc)})

    res = escanear_region(series_preparadas, reg.id, medias_climatologia=medias, alfa=alfa)
    for item in res["resultados"]:
        e = catalogo[item["variable"]]
        item["nombre_simple"] = e["nombre_simple"]
        item["definicion_simple"] = e["definicion_simple"]
        item["grupo"] = e["grupo"]
        item["dataset"] = e["dataset"]
        item["unidad"] = e["unidad_final"]

    return {
        "region": reg.a_dict(),
        "periodo": [inicio, fin],
        "fuente_datos": "sintetico" if "sintetico" in fuentes_usadas else "opendap_memoria",
        "resultados": res["resultados"],
        "rechazadas": res["rechazadas"],
    }


def ejecutar_dos_caras(
    *,
    variable: str = "lluvia_gpcp",
    region_a: str | None = None,
    bbox_a: Sequence[float] | None = None,
    region_b: str | None = None,
    bbox_b: Sequence[float] | None = None,
    variable_b: str | None = None,
    inicio: str = PERIODO_COMUN[0],
    fin: str = PERIODO_COMUN[1],
    alfa: float = 0.05,
    descargar: bool = False,
    sintetico: bool = False,
) -> dict[str, Any]:
    """Compara dos regiones (o dos variables en la misma región) con motor.escaner.comparar_dos_caras."""
    reg_a = resolver_region(region_a, bbox_a)
    reg_b = resolver_region(region_b, bbox_b) if (region_b or bbox_b) else reg_a
    var_b = variable_b or variable

    res_a = consultar_tendencia(
        variable,
        region=reg_a.id,
        bbox=reg_a.bbox,
        inicio=inicio,
        fin=fin,
        alfa=alfa,
        incluir_serie=True,
        descargar=descargar,
        sintetico=sintetico,
    )
    res_b = consultar_tendencia(
        var_b,
        region=reg_b.id,
        bbox=reg_b.bbox,
        inicio=inicio,
        fin=fin,
        alfa=alfa,
        incluir_serie=True,
        descargar=descargar,
        sintetico=sintetico,
    )
    comparacion = comparar_dos_caras(res_a["tendencia"], res_b["tendencia"])
    return {
        **comparacion,
        "detalle_a": res_a,
        "detalle_b": res_b,
    }


# ----------------------------------------------------------------------------------------------- Mapa de tendencias
def consultar_mapa_tendencias(
    variable: str,
    *,
    region: str | None = None,
    bbox: Sequence[float] | None = None,
    inicio: str = PERIODO_COMUN[0],
    fin: str = PERIODO_COMUN[1],
    mascara: Literal["tierra"] | None = None,
    alfa: float = 0.05,
    descargar: bool = False,
    sintetico: bool = False,
) -> dict[str, Any]:
    """Calcula el mapa de tendencias por píxel para una región y lo devuelve en JSON listo para el frontend."""
    validar_periodo(inicio, fin)
    reg = resolver_region(region, bbox)
    catalogo = obtener_catalogo()
    if variable not in catalogo:
        raise KeyError(f"Variable '{variable}' no existe en el catálogo")
    entrada = catalogo[variable]

    if entrada["frecuencia"] == "diaria":
        raise ValueError(f"'{variable}' es diaria; usa un indicador anual (p. ej. cdd_imerg o r20mm_imerg).")

    if entrada["grupo"] == "calculada":
        cubo_d, fuente = _obtener_cubo(
            entrada["origen"], reg, inicio, fin, descargar=descargar, sintetico=sintetico
        )
        if mascara == "tierra":
            cubo_d = aplicar_mascara(cubo_d, "tierra")
        ds_ind = indicadores_anuales(cubo_d)
        cubo_motor = reindexar_calendario(ds_ind[entrada["indicador"]], inicio[:4], fin[:4])
        unidad_tiempo: Literal["mes", "anio"] = "anio"
    else:
        cubo_m, fuente = _obtener_cubo(variable, reg, inicio, fin, descargar=descargar, sintetico=sintetico)
        if mascara == "tierra":
            cubo_m = aplicar_mascara(cubo_m, "tierra")
        # Meses ausentes como NaN para que el límite de 10 % faltante por píxel los cuente.
        cubo_m = reindexar_calendario(cubo_m, inicio, fin)
        cubo_motor = anomalias(cubo_m, base=(inicio, fin))
        unidad_tiempo = "mes"

    n_pixeles = int(cubo_motor.sizes.get("lat", 1) * cubo_motor.sizes.get("lon", 1))
    max_px = obtener_ajustes().max_pixeles
    if n_pixeles > max_px:
        raise ValueError(
            f"La región contiene {n_pixeles} píxeles (máximo síncrono: {max_px}). "
            "Usa una caja más pequeña o una variable de menor resolución (p. ej. lluvia_gpcp a 0.5°)."
        )

    if sintetico:
        ds_mapa = mapa_tendencias(cubo_motor, unidad_tiempo=unidad_tiempo, alfa=alfa).compute()
    else:
        ds_mapa = obtener_mapa_tendencias(
            cubo_motor, variable, reg.id, inicio, fin, unidad_tiempo=unidad_tiempo, alfa=alfa
        )

    pend = np.asarray(ds_mapa["pendiente_decada"].values, dtype=np.float64)
    ver = np.asarray(ds_mapa["veredicto"].values, dtype=np.float64)
    validos = np.isfinite(pend) & np.isfinite(ver)

    return {
        "variable": variable,
        "nombre_simple": entrada["nombre_simple"],
        "unidad_pendiente": f"{entrada['unidad_final']}/decada",
        "region": reg.a_dict(),
        "periodo": [inicio, fin],
        "alfa": float(alfa),
        "fuente_datos": fuente,
        "codigos_veredicto": {"2": "significativo", "1": "indicio", "0": "sin tendencia clara"},
        "lat": [float(x) for x in ds_mapa["lat"].values],
        "lon": [float(x) for x in ds_mapa["lon"].values],
        "pendiente_decada": _matriz_json(pend),
        "p_t": _matriz_json(ds_mapa["p_t"].values),
        "p_mk": _matriz_json(ds_mapa["p_mk"].values),
        "veredicto": _matriz_json(ver),
        "resumen": {
            "n_pixeles_total": n_pixeles,
            "n_pixeles_validos": int(validos.sum()),
            "n_significativos_secos": int((validos & (ver == 2.0) & (pend < 0.0)).sum()),
            "n_significativos_humedos": int((validos & (ver == 2.0) & (pend > 0.0)).sum()),
            "n_indicio": int((validos & (ver == 1.0)).sum()),
        },
    }


# ----------------------------------------------------------------------------------------------- Down to Earth (4 variables, OLS+HAC+Holm y lectura conjunta)
def consultar_catalogo_dte() -> dict[str, Any]:
    """Catálogo focalizado de la guía 'Down to Earth': 4 variables (P, T, SM, ET), 3 colecciones y método."""
    catalogo = obtener_catalogo()
    datasets = obtener_datasets()
    regiones = [r.a_dict() for r in cargar_regiones().values()]

    variables_dte: list[dict[str, Any]] = []
    for codigo in ORDEN_VARIABLES_DTE:
        meta_dte = INFO_VARIABLES_DTE[codigo]
        vid = meta_dte["id"]
        ent = catalogo[vid]
        variables_dte.append({
            "code": codigo,
            "id": vid,
            "name": meta_dte["nombre"],
            "question": meta_dte["pregunta"],
            "rationale": meta_dte["por_que_elegirla"],
            "collection": meta_dte["coleccion"],
            "short_name": ent["short_name"],
            "version": ent.get("version"),
            "collection_concept_id": ent.get("collection_concept_id"),
            "field": meta_dte["campo"],
            "raw_unit": ent["unidad_original"],
            "monthly_unit": meta_dte["unidad_mensual"],
            "annual_unit": meta_dte["unidad_anual"],
            "slope_unit": meta_dte["unidad_decada"],
            "monthly_conversion": meta_dte["conversion_texto"],
            "annual_aggregation": meta_dte["agregacion_anual"],
            "resolution": ent.get("resolucion"),
            "url_summary": ent.get("url_summary"),
        })

    colecciones_dte = [
        datasets[did]
        for did in ("gpcp", "merra2", "gldas")
        if did in datasets
    ]

    return {
        "project": "Down to Earth — Cuatro variables, dos formas de analizarlas",
        "period_default": list(PERIODO_DTE_DEFECTO),
        "months_expected": 288,
        "years_expected": 24,
        "collections": colecciones_dte,
        "variables": variables_dte,
        "method": {
            "trend": (
                "OLS lineal con constante sobre el tramo común más largo de años completos y consecutivos "
                "de las cuatro variables (t = anio - anio_inicial)"
            ),
            "spatial_average": (
                "X = Σ(Aᵢ·Xᵢ)/Σ(Aᵢ), Aᵢ = área esférica de la celda dentro de la región × fracción de tierra "
                "según la huella de GLDAS (mismo territorio terrestre para GPCP, MERRA-2 y GLDAS)"
            ),
            "labels": [
                "aumento con evidencia estadística según este método",
                "disminución con evidencia estadística según este método",
                "evidencia insuficiente",
                "evidencia insuficiente tras el ajuste",
            ],
            "uncertainty": "HAC / Newey-West (maxlags=1, kernel='bartlett', use_correction=True)",
            "test": "Wald bilateral normal (use_t=False), H0: b = 0 vs H1: b != 0, alpha = 0.05",
            "multiple_testing": "Holm sobre la familia fija de 4 tendencias [P, T, SM, ET]",
            "sensitivity": "Revisión automática de rezagos HAC maxlags = 1, 2 y 3",
            "joint_analysis": (
                "Pearson descriptivo r sobre anomalías mensuales estandarizadas (z) sin tendencia lineal "
                "para los 3 pares prioritarios: P-SM, T-SM y P-ET (sin p-valores ni significancia)"
            ),
            "priority_pairs": [p["pair"] for p in PARES_PRIORITARIOS_DTE],
        },
        "regions": regiones,
    }


def _obtener_cubos_cuatro_variables_dte(
    reg: RegionResuelta,
    inicio: str,
    fin: str,
    *,
    mascara: Literal["tierra"] | None = None,
    descargar: bool = False,
    sintetico: bool = False,
    fallback_sintetico: bool = True,
) -> tuple[dict[str, xr.DataArray], str]:
    """Obtiene los cubos 3-D de P, T, SM y ET en su propia grilla nativa sin remuestrear entre sí."""
    catalogo = obtener_catalogo()
    cubos: dict[str, xr.DataArray] = {}
    fuentes: set[str] = set()

    for codigo in ORDEN_VARIABLES_DTE:
        vid = INFO_VARIABLES_DTE[codigo]["id"]
        entrada = catalogo[vid]
        if sintetico:
            da = _cubo_sintetico(vid, entrada, reg, inicio, fin)
            fuente = "sintetico"
        else:
            try:
                da, fuente = _obtener_cubo(
                    vid, reg, inicio, fin, descargar=descargar, sintetico=False
                )
            except DatosNoDisponibles:
                if not fallback_sintetico or descargar:
                    raise
                da = _cubo_sintetico(vid, entrada, reg, inicio, fin)
                fuente = "sintetico"
        if mascara == "tierra":
            da = aplicar_mascara(da, "tierra")
        cubos[codigo] = da
        fuentes.add(fuente)

    fuente_final = "sintetico" if "sintetico" in fuentes else "opendap_memoria"
    return cubos, fuente_final


def consultar_demo_dte(
    *,
    region: str | None = "sahel",
    bbox: Sequence[float] | None = None,
    inicio: str = PERIODO_DTE_DEFECTO[0],
    fin: str = PERIODO_DTE_DEFECTO[1],
    alfa: float = 0.05,
    mascara: Literal["tierra"] | None = None,
    descargar: bool = False,
    sintetico: bool = False,
    fallback_sintetico: bool = True,
) -> dict[str, Any]:
    """Ejecuta el análisis completo 'Down to Earth' (secciones 01 a 06) para P, T, SM y ET."""
    validar_periodo(inicio, fin)
    reg = resolver_region(region, bbox)
    cubos, fuente = _obtener_cubos_cuatro_variables_dte(
        reg,
        inicio,
        fin,
        mascara=mascara,
        descargar=descargar,
        sintetico=sintetico,
        fallback_sintetico=fallback_sintetico,
    )
    return analizar_cuatro_variables_dte(
        cubos,
        region_meta=reg.a_dict(),
        inicio=inicio,
        fin=fin,
        alfa=alfa,
        fuente_datos=fuente,
    )


def exportar_csv_dte(
    frecuencia: Literal["mensual", "anual"],
    *,
    region: str | None = "sahel",
    bbox: Sequence[float] | None = None,
    inicio: str = PERIODO_DTE_DEFECTO[0],
    fin: str = PERIODO_DTE_DEFECTO[1],
    mascara: Literal["tierra"] | None = None,
    descargar: bool = False,
    sintetico: bool = False,
    fallback_sintetico: bool = True,
) -> str:
    """Genera en memoria RAM el CSV mensual o anual de las 4 variables (P, T, SM, ET)."""
    resultado = consultar_demo_dte(
        region=region,
        bbox=bbox,
        inicio=inicio,
        fin=fin,
        mascara=mascara,
        descargar=descargar,
        sintetico=sintetico,
        fallback_sintetico=fallback_sintetico,
    )
    if frecuencia == "anual":
        return generar_csv_anual_dte(resultado)
    return generar_csv_mensual_dte(resultado)
