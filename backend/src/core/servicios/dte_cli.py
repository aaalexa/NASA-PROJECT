"""Corrida del análisis Down to Earth con datos reales de NASA y escritura de resultados en disco.

Uso (CLI):
    nasa-project dte --region corredor_seco_centroamericano --salida resultados/dte/corredor_seco_centroamericano
    nasa-project dte --bbox -92 12 -83 16 --inicio 2001-01 --fin 2024-12 --salida resultados/dte/mi_caja

Con docker compose (compose no lee backend/.env por sí solo: hay que pasarlo con --env-file):
    docker compose --env-file backend/.env run --rm -v ./resultados:/app/resultados api \
        nasa-project dte --region sahel --salida /app/resultados/dte/sahel

Qué hace:
  1. Carga credenciales de `backend/.env` si existe (sin sobrescribir variables ya definidas; nunca las imprime).
  2. Descarga por OPeNDAP a memoria P (GPCP v3.3), T (MERRA-2 T2M), SM y ET (GLDAS Noah 2.1) para la región.
  3. Ejecuta `analizar_cuatro_variables_dte` (método fijo: OLS anual + HAC rezago 1 + Holm [P, T, SM, ET] +
     sensibilidad rezagos 2 y 3; anomalías z y Pearson P–SM, T–SM, P–ET). Nunca usa datos sintéticos.
  4. Limpieza estructural de las series regionales (motor/limpieza_dte.py) con registro de cada acción.
  5. Escribe en `--salida` (ver `escribir_salidas`): resultados.json, serie_regional.csv (precisión completa, entrada
     del script de la skill analisis-down-to-earth), mensual.csv y anual.csv con formato, registro_limpieza.csv y
     diccionario_datos.csv.

Reanalizar sin descargar (desde una serie regional ya guardada):
    nasa-project dte --region sahel --desde-csv resultados/dte/sahel/serie_regional.csv --salida resultados/dte/sahel
"""
from __future__ import annotations

import json
import math
import os
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr

from core.config import cargar_dotenv
from core.motor.down_to_earth import (
    ORDEN_VARIABLES_DTE,
    PERIODO_DTE_DEFECTO,
    analizar_cuatro_variables_dte,
)
from core.motor.limpieza_dte import diccionario_datos, tabla_anual_formateada, tabla_mensual_formateada
from core.servicios.calculo_dte import analizar_region_real
from core.servicios.regiones import resolver_region

RAIZ_BACKEND = Path(__file__).resolve().parents[3]


def cargar_env(ruta: Path | None = None) -> list[str]:
    """Carga backend/.env (o `ruta`) sin sobrescribir variables ya definidas. Ver core.config.cargar_dotenv."""
    return cargar_dotenv(ruta or (RAIZ_BACKEND / ".env"))


def _json_seguro(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_seguro(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_seguro(v) for v in obj]
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):
        obj = obj.item()
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def csv_serie_regional(resultado: dict[str, Any]) -> str:
    """CSV mensual regional con precisión completa (fecha,P,T,SM,ET) para el script de la skill."""
    vars_d = resultado["variables"]
    lineas = ["fecha,P,T,SM,ET"]
    for i, fila in enumerate(vars_d["P"]["monthly"]):
        vals = []
        for c in ORDEN_VARIABLES_DTE:
            v = vars_d[c]["monthly"][i]["value"]
            vals.append("" if v is None else repr(float(v)))
        lineas.append(f"{fila['date']},{','.join(vals)}")
    return "\n".join(lineas) + "\n"


def ejecutar_dte_real(
    *,
    region: str | None,
    bbox: Sequence[float] | None,
    inicio: str = PERIODO_DTE_DEFECTO[0],
    fin: str = PERIODO_DTE_DEFECTO[1],
    salida: Path,
    alfa: float = 0.05,
    avisar: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Descarga los datos reales, ejecuta el análisis y escribe los archivos. Devuelve el resultado (dict JSON)."""
    reg = resolver_region(region, bbox)
    avisar(f"Región: {reg.id} bbox={list(reg.bbox)}  período {inicio} a {fin}")

    def _progreso(var: str, actual: int, total: int, msg: str) -> None:
        if total == 0 or actual == total or actual % max(1, total // 10) == 0:
            avisar(f"   [{var}] {actual}/{total} {msg}")

    resultado = analizar_region_real(
        region=region, bbox=bbox, inicio=inicio, fin=fin, alfa=alfa, progreso=_progreso
    )
    escribir_salidas(resultado, salida)
    return resultado


def analizar_desde_csv(
    ruta_csv: Path,
    *,
    region: str | None = None,
    bbox: Sequence[float] | None = None,
    inicio: str = PERIODO_DTE_DEFECTO[0],
    fin: str = PERIODO_DTE_DEFECTO[1],
    alfa: float = 0.05,
) -> dict[str, Any]:
    """Reanaliza una serie regional mensual ya descargada (serie_regional.csv: fecha,P,T,SM,ET en unidades finales).

    No descarga nada: aplica limpieza y análisis sobre los promedios regionales guardados con precisión completa.
    """
    df = pd.read_csv(ruta_csv, dtype={"fecha": str})
    faltan = [c for c in ("fecha", *ORDEN_VARIABLES_DTE) if c not in df.columns]
    if faltan:
        raise ValueError(f"{ruta_csv} no tiene las columnas {faltan} (se espera fecha,P,T,SM,ET).")
    fechas = pd.to_datetime(df["fecha"].str[:7] + "-01", format="%Y-%m-%d")
    unidades = {"P": "mm/mes", "T": "degC", "SM": "m3/m3", "ET": "mm/mes"}
    entradas = {
        c: xr.DataArray(pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=np.float64),
                        coords={"time": fechas.values}, dims=("time",), attrs={"units": unidades[c]})
        for c in ORDEN_VARIABLES_DTE
    }
    region_meta = resolver_region(region, bbox).a_dict() if (region or bbox) else None
    resultado = analizar_cuatro_variables_dte(
        entradas, inicio, fin, alfa=alfa, region_meta=region_meta, fuente_datos="csv_regional"
    )
    resultado["metadata"]["input_file"] = str(ruta_csv)
    return resultado


def escribir_salidas(resultado: dict[str, Any], salida: Path) -> list[Path]:
    """Escribe resultados y tablas con formato. Devuelve las rutas escritas.

    - resultados.json: todo el análisis (incluye data_cleaning con resumen y registro).
    - serie_regional.csv: promedios regionales mensuales con precisión completa (entrada del script de la skill).
    - mensual.csv / anual.csv: tablas de presentación con decimales fijos, unidades en el nombre de columna y
      marcas de completitud (vacío = faltante).
    - registro_limpieza.csv: una fila por acción de limpieza (fecha, variable, valor original, acción, motivo).
    - diccionario_datos.csv: descripción, unidad, tipo, fuente, conversión y decimales de cada columna.
    """
    salida.mkdir(parents=True, exist_ok=True)
    rutas = {
        "resultados.json": json.dumps(_json_seguro(resultado), ensure_ascii=False, indent=2, allow_nan=False),
        "serie_regional.csv": csv_serie_regional(resultado),
        "mensual.csv": tabla_mensual_formateada(resultado).to_csv(index=False, lineterminator="\n"),
        "anual.csv": tabla_anual_formateada(resultado).to_csv(index=False, lineterminator="\n"),
        "registro_limpieza.csv": pd.DataFrame(
            resultado.get("data_cleaning", {}).get("log", []),
            columns=["fecha", "variable", "valor_original", "accion", "motivo"],
        ).to_csv(index=False, lineterminator="\n"),
        "diccionario_datos.csv": diccionario_datos().to_csv(index=False, lineterminator="\n"),
    }
    escritas = []
    for nombre, contenido in rutas.items():
        ruta = salida / nombre
        ruta.write_text(contenido, encoding="utf-8")
        escritas.append(ruta)
    return escritas
