"""Rutas de catálogo: datasets de NASA (GPCP, MERRA-2, GPM IMERG), variables requeridas y regiones."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from core.config import PERIODO_COMUN, PERIODO_GLOBAL
from core.servicios.consultas import (
    consultar_datasets,
    consultar_variable_detalle,
    consultar_variables,
    obtener_datasets,
)
from core.servicios.regiones import cargar_regiones, resolver_region

router = APIRouter(tags=["Catálogo y Metadatos"])


@router.get("/catalogo", summary="Catálogo completo para inicializar el frontend")
def ruta_catalogo_completo() -> dict[str, Any]:
    """Devuelve en una sola llamada los datasets de NASA, las variables disponibles, las regiones y los periodos."""
    regiones = [r.a_dict() for r in cargar_regiones().values()]
    return {
        "datasets": consultar_datasets(),
        "variables": consultar_variables(),
        "regiones": regiones,
        "periodos": {
            "comun": list(PERIODO_COMUN),
            "global": list(PERIODO_GLOBAL),
        },
    }


@router.get("/datasets", summary="Lista los datasets de NASA (GPCP, MERRA-2, GPM IMERG) y sus variables")
def ruta_listar_datasets() -> dict[str, Any]:
    datasets = consultar_datasets()
    return {"total": len(datasets), "datasets": datasets}


@router.get("/datasets/{dataset_id}", summary="Detalle de un dataset de NASA (gpcp, merra2, imerg)")
def ruta_detalle_dataset(dataset_id: str) -> dict[str, Any]:
    todos = {d["id"]: d for d in consultar_datasets()}
    if dataset_id not in todos:
        validos = sorted( obtener_datasets() )
        raise KeyError(f"Dataset '{dataset_id}' no existe (válidos: {validos})")
    return todos[dataset_id]


@router.get("/variables", summary="Lista y filtra las variables del catálogo")
def ruta_listar_variables(
    grupo: str | None = Query(default=None, description="Filtrar por grupo: lluvia, causa, calculada"),
    fuente: str | None = Query(default=None, description="Filtrar por dataset: gpcp, merra2, imerg"),
    frecuencia: str | None = Query(default=None, description="Filtrar por frecuencia: diaria, mensual, anual"),
    solo_analizables: bool = Query(default=False, description="Omitir variables crudas diarias"),
) -> dict[str, Any]:
    variables = consultar_variables(
        grupo=grupo,
        fuente=fuente,
        frecuencia=frecuencia,
        solo_analizables=solo_analizables,
    )
    return {"total": len(variables), "variables": variables}


@router.get("/variables/{variable_id}", summary="Metadatos, unidad, conversión y caché de una variable")
def ruta_detalle_variable(variable_id: str) -> dict[str, Any]:
    return consultar_variable_detalle(variable_id)


@router.get("/regiones", summary="Regiones predefinidas con sus bounding boxes")
def ruta_listar_regiones() -> dict[str, Any]:
    regiones = [r.a_dict() for r in cargar_regiones().values()]
    return {"total": len(regiones), "regiones": regiones}


@router.get("/regiones/{region_id}", summary="Detalle de una región predefinida")
def ruta_detalle_region(region_id: str) -> dict[str, Any]:
    return resolver_region(region=region_id).a_dict()

