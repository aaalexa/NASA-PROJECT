"""Indicadores anuales de extremos de lluvia a partir de datos diarios (skill indicadores-lluvia).

Definiciones (ETCCDI, con P_d en mm/dia):
    cdd           racha más larga de días consecutivos con P_d < 1 mm (y no NaN)   [dias]
    r20mm         número de días con P_d >= 20 mm                                  [dias]
    dias_humedos  número de días con P_d >= 1 mm (W)                               [dias]
    prcptot       suma de P_d en los días húmedos (P_d >= 1 mm)                    [mm/anio]
    sdii          prcptot / dias_humedos (NaN si dias_humedos == 0)                [mm/dia]

Por defecto las rachas que cruzan el 31 de diciembre se cortan en cada año natural (cortar_en_anio=True).
Con cortar_en_anio=False cada racha seca se asigna íntegra al año en que termina.
"""
from __future__ import annotations

import calendar
from typing import Literal

import numpy as np
import pandas as pd
import xarray as xr

__all__ = [
    "UNIDADES_INDICADORES",
    "racha_seca_maxima",
    "indicadores_anuales",
    "serie_indicador_region",
]

NombreIndicador = Literal["cdd", "r20mm", "dias_humedos", "prcptot", "sdii"]

UNIDADES_INDICADORES: dict[str, str] = {
    "cdd": "dias",
    "r20mm": "dias",
    "dias_humedos": "dias",
    "prcptot": "mm/anio",
    "sdii": "mm/dia",
}


def racha_seca_maxima(seco: np.ndarray) -> np.ndarray:
    """Racha máxima de True consecutivos a lo largo del último eje (referencia §2).

    Entrada: array booleano de cualquier dimensión; el eje de tiempo es el último.
    Salida: array de enteros (np.int64) con la forma seco.shape[:-1] (o escalar 0-D si seco es 1-D).
    """
    seco_b = np.asarray(seco, dtype=bool)
    if seco_b.shape[-1] == 0:
        return np.zeros(seco_b.shape[:-1], dtype=np.int64)
    c = np.cumsum(seco_b, axis=-1, dtype=np.int64)
    reinicio = np.where(seco_b, 0, c)
    base = np.maximum.accumulate(reinicio, axis=-1)
    return (c - base).max(axis=-1)


def _racha_al_terminar(seco: np.ndarray) -> np.ndarray:
    """Coloca la longitud total de cada racha de True en su último día (0 en el resto)."""
    seco_b = np.asarray(seco, dtype=bool)
    if seco_b.shape[-1] == 0:
        return np.zeros_like(seco_b, dtype=np.int64)
    c = np.cumsum(seco_b, axis=-1, dtype=np.int64)
    reinicio = np.where(seco_b, 0, c)
    base = np.maximum.accumulate(reinicio, axis=-1)
    corrida = c - base
    sig_seco = np.concatenate([seco_b[..., 1:], np.zeros(seco_b.shape[:-1] + (1,), dtype=bool)], axis=-1)
    fin_racha = seco_b & ~sig_seco
    return np.where(fin_racha, corrida, 0)


def _validar_diario(pr: xr.DataArray) -> None:
    unidad = pr.attrs.get("units")
    if unidad != "mm/dia":
        raise ValueError(
            f"indicadores_anuales requiere lluvia diaria en 'mm/dia', no {unidad!r} "
            "(convierte antes con motor.catalogo.convertir)"
        )
    if "time" not in pr.dims:
        raise ValueError("indicadores_anuales requiere dimensión 'time' diaria")
    if pr.sizes["time"] >= 2:
        fechas = pd.DatetimeIndex(pr["time"].values)
        mediana_dias = float(np.median(np.diff(fechas).astype("timedelta64[D]").astype(float)))
        if mediana_dias > 2.0:
            raise ValueError(
                f"indicadores_anuales requiere frecuencia diaria (paso mediano observado: {mediana_dias:.1f} días)"
            )


def _cdd_por_anio(seco_anio: xr.DataArray) -> xr.DataArray:
    if seco_anio.chunks is not None and "time" in seco_anio. dims:
        seco_anio = seco_anio.chunk({"time": -1})
    return xr.apply_ufunc(
        racha_seca_maxima,
        seco_anio,
        input_core_dims=[["time"]],
        dask="parallelized",
        output_dtypes=[np.int64],
    )


def indicadores_anuales(
    pr: xr.DataArray,
    max_faltantes: float = 0.10,
    *,
    cortar_en_anio: bool = True,
) -> xr.Dataset:
    """Calcula CDD, R20mm, días húmedos (W), PRCPTOT y SDII por año natural (referencia §1–§2).

    Funciona con series 1-D (time,) y cubos 3-D (time, lat, lon).
    Si un año tiene más de max_faltantes (10 % por defecto) de los días del calendario como NaN, todos sus
    indicadores en ese año/píxel quedan como NaN.
    """
    _validar_diario(pr)
    if not 0.0 <= max_faltantes <= 1.0:
        raise ValueError(f"max_faltantes debe estar entre 0 y 1, no {max_faltantes}")

    if pr.chunks is not None:
        pr = pr.chunk({"time": -1})

    valido = pr.notnull()
    seco = (pr < 1.0) & valido
    humedo = (pr >= 1.0) & valido
    intenso = (pr >= 20.0) & valido

    if cortar_en_anio:
        cdd = seco.groupby("time.year").map(_cdd_por_anio).rename(year="anio").astype(float)
    else:
        fin_racha = xr.apply_ufunc(
            _racha_al_terminar,
            seco,
            input_core_dims=[["time"]],
            output_core_dims=[["time"]],
            dask="parallelized",
            output_dtypes=[np.int64],
        )
        cdd = fin_racha.groupby("time.year").max("time").rename(year="anio").astype(float)

    r20mm = intenso.groupby("time.year").sum("time").rename(year="anio").astype(float)
    dias_humedos = humedo.groupby("time.year").sum("time").rename(year="anio").astype(float)
    prcptot = pr.where(humedo, 0.0).groupby("time.year").sum("time").rename(year="anio").astype(float)
    sdii = xr.where(dias_humedos > 0, prcptot / dias_humedos, np.nan)

    # Control de calidad por año respecto a los días reales del calendario (365 o 366).
    n_validos = valido.groupby("time.year").sum("time").rename(year="anio")
    anios = n_validos["anio"].values.astype(int)
    dias_calendario = xr.DataArray(
        np.array([366 if calendar.isleap(int(a)) else 365 for a in anios], dtype=float),
        coords={"anio": n_validos["anio"]},
        dims=("anio",),
    )
    frac_faltante = (dias_calendario - n_validos) / dias_calendario
    anio_ok = frac_faltante <= max_faltantes + 1e-12

    ds = xr.Dataset(
        {
            "cdd": cdd.where(anio_ok),
            "r20mm": r20mm.where(anio_ok),
            "dias_humedos": dias_humedos.where(anio_ok),
            "prcptot": prcptot.where(anio_ok),
            "sdii": sdii.where(anio_ok),
        }
    )
    ds = ds.assign_coords(anio=anios)
    for nombre, unidad in UNIDADES_INDICADORES.items():
        ds[nombre].attrs = {"units": unidad, "indicador": nombre, "cortar_en_anio": cortar_en_anio}
    ds.attrs = {"max_faltantes": max_faltantes, "cortar_en_anio": cortar_en_anio}
    return ds


def serie_indicador_region(
    pr: xr.DataArray,
    indicador: NombreIndicador,
    *,
    max_faltantes: float = 0.10,
    min_area_valida: float = 0.9,
    cortar_en_anio: bool = True,
) -> xr.DataArray:
    """Calcula el indicador por píxel y después promedia con pesos cos(latitud) (evita el sesgo de promediar antes)."""
    from core.motor.series import promedio_area

    ind = indicador.lower()
    if ind not in UNIDADES_INDICADORES:
        raise ValueError(f"indicador '{indicador}' desconocido (válidos: {sorted(UNIDADES_INDICADORES)})")
    ds = indicadores_anuales(pr, max_faltantes=max_faltantes, cortar_en_anio=cortar_en_anio)
    da = ds[ind]
    if "lat" in da.dims and "lon" in da.dims:
        da = promedio_area(da, min_area_valida=min_area_valida)
    return da

