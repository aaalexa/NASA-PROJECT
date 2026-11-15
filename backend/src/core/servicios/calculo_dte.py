"""Servicios de cálculo Down to Earth: desde una tabla mensual (entrada del usuario) o con datos reales de NASA.

Ambos caminos terminan en `motor.down_to_earth.analizar_cuatro_variables_dte`, de modo que la API, el comando
`nasa-project dte` y el script de la skill aplican exactamente las mismas fórmulas.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Literal

import numpy as np
import pandas as pd
import xarray as xr

from core.motor.datos import descargar_variable, validar_periodo
from core.motor.down_to_earth import (
    INFO_VARIABLES_DTE,
    ORDEN_VARIABLES_DTE,
    PERIODO_DTE_DEFECTO,
    analizar_cuatro_variables_dte,
)
from core.motor.limpieza_dte import convertir_unidades_originales, leer_tabla_mensual
from core.servicios.consultas import consultar_demo_dte, obtener_catalogo
from core.servicios.regiones import resolver_region

UNIDADES_FINALES_ATTR: dict[str, str] = {"P": "mm/mes", "T": "degC", "SM": "m3/m3", "ET": "mm/mes"}
MAX_FILAS_TABLA = 5000

# progreso(variable, paso_actual, total_pasos, mensaje)
ProgresoRegion = Callable[[str, int, int, str], None]


def calcular_dte_desde_tabla(
    df: pd.DataFrame,
    *,
    unidades: Literal["finales", "originales"] = "finales",
    inicio: str = PERIODO_DTE_DEFECTO[0],
    fin: str = PERIODO_DTE_DEFECTO[1],
    alfa: float = 0.05,
    region: str | None = None,
    bbox: Sequence[float] | None = None,
    simulado: bool = False,
    fuente: str = "entrada_usuario",
) -> dict[str, Any]:
    """Limpia y analiza una tabla mensual regional (fecha, P, T, SM, ET) con el método fijo de Down to Earth.

    `unidades="originales"` convierte desde las unidades NASA (mm/día, K, kg/m², kg/m²/s). La región solo aporta
    metadatos (nombre y caja): la tabla ya debe contener promedios regionales.
    """
    validar_periodo(inicio, fin)
    if len(df) == 0:
        raise ValueError("La tabla está vacía.")
    if len(df) > MAX_FILAS_TABLA:
        raise ValueError(f"La tabla tiene {len(df)} filas; el máximo es {MAX_FILAS_TABLA}.")
    series, registro, columnas = leer_tabla_mensual(df)
    if unidades == "originales":
        series, reg_conv = convertir_unidades_originales(series)
        registro = [*registro, *reg_conv]
    elif unidades != "finales":
        raise ValueError("unidades debe ser 'finales' u 'originales'.")

    entradas: dict[str, xr.DataArray] = {}
    vacio = pd.Series(dtype="float64", index=pd.DatetimeIndex([]))
    for c in ORDEN_VARIABLES_DTE:
        s = series.get(c, vacio)
        entradas[c] = xr.DataArray(
            s.to_numpy(dtype=np.float64), coords={"time": s.index.values}, dims=("time",),
            attrs={"units": UNIDADES_FINALES_ATTR[c]},
        )
    region_meta = resolver_region(region, bbox).a_dict() if (region or bbox) else None
    resultado = analizar_cuatro_variables_dte(
        entradas, inicio, fin, alfa=alfa, region_meta=region_meta, fuente_datos=fuente,
        simulado=simulado, registro_entrada=registro,
    )
    resultado["metadata"]["input"] = {
        "rows": int(len(df)),
        "units": unidades,
        "columns_used": columnas,
        "missing_variables": [c for c in ORDEN_VARIABLES_DTE if c not in columnas],
    }
    for c in resultado["metadata"]["input"]["missing_variables"]:
        resultado["metadata"]["warnings"].append(f"{c}: columna ausente en la entrada; se publica como no evaluable.")
    return resultado


def analizar_region_real(
    *,
    region: str | None,
    bbox: Sequence[float] | None,
    inicio: str = PERIODO_DTE_DEFECTO[0],
    fin: str = PERIODO_DTE_DEFECTO[1],
    alfa: float = 0.05,
    progreso: ProgresoRegion | None = None,
) -> dict[str, Any]:
    """Descarga por OPeNDAP P, T, SM y ET reales de la región y ejecuta el análisis. Nunca usa datos sintéticos.

    Lanza DatosNoDisponibles / RuntimeError si falta algún producto: no rellena con datos inventados.
    """
    validar_periodo(inicio, fin)
    reg = resolver_region(region, bbox)
    catalogo = obtener_catalogo()
    for codigo in ORDEN_VARIABLES_DTE:
        vid = INFO_VARIABLES_DTE[codigo]["id"]

        def _prog(actual: int, total: int, msg: str, _c: str = codigo) -> None:
            if progreso is not None:
                progreso(_c, actual, total, msg)

        _prog(0, 0, f"descargando {catalogo[vid]['short_name']} v{catalogo[vid].get('version')}")
        descargar_variable(vid, reg.id, reg.bbox, inicio, fin, catalogo, progreso=_prog)

    if progreso is not None:
        progreso("analisis", 0, 1, "limpieza y análisis estadístico")
    resultado = consultar_demo_dte(
        region=region, bbox=bbox, inicio=inicio, fin=fin, alfa=alfa, descargar=False, fallback_sintetico=False,
    )
    md = resultado["metadata"]
    if md.get("source") != "opendap_memoria" or md.get("simulated"):
        raise RuntimeError("El resultado no proviene íntegramente de datos reales de NASA.")
    if progreso is not None:
        progreso("analisis", 1, 1, "análisis completado")
    return resultado
