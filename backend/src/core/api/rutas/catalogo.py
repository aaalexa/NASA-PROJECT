"""Rutas de catálogo: datasets de NASA (GPCP, MERRA-2, GLDAS Noah, GPM IMERG), variables requeridas y regiones."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from core.config import PERIODO_COMUN, PERIODO_GLOBAL
from core.servicios.consultas import (
    consultar_catalogo_dte,
    consultar_datasets,
    consultar_variable_detalle,
    consultar_variables,
    obtener_datasets,
)
from core.servicios.regiones import cargar_regiones, listar_regiones_filtradas, resolver_region

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
        "down_to_earth": consultar_catalogo_dte(),
    }


@router.get(
    "/catalog",
    summary="Catálogo Down to Earth (4 variables: P, T, SM, ET; 3 colecciones; método OLS+HAC+Holm)",
)
@router.get(
    "/down-to-earth/catalogo",
    summary="Catálogo Down to Earth (4 variables: P, T, SM, ET; 3 colecciones; método OLS+HAC+Holm)",
)
def ruta_catalogo_down_to_earth() -> dict[str, Any]:
    return consultar_catalogo_dte()


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


@router.get(
    "/regiones",
    summary="Regiones predefinidas con coordenadas reales (lat/lon), centros de malla NASA y shortcuts",
)
def ruta_listar_regiones(
    zona: str | None = Query(
        default=None,
        description=(
            "Filtrar por zona: mexico, centroamerica, mexico_centroamerica, caribe, "
            "sudamerica, latinoamerica o referencia_global"
        ),
    ),
    solo_latinoamerica: bool = Query(
        default=False,
        description="Si es True, devuelve únicamente regiones de México, Centroamérica, Caribe y Sudamérica",
    ),
) -> dict[str, Any]:
    regiones = listar_regiones_filtradas(zona=zona, solo_latinoamerica=solo_latinoamerica)
    por_zona: dict[str, list[dict[str, Any]]] = {}
    for r in regiones:
        por_zona.setdefault(r["zona"], []).append(r)

    shortcuts = [
        {
            "id": r["id"],
            "nombre": r["nombre"],
            "zona": r["zona"],
            "pais": r["pais"],
            "bbox": r["bbox"],
            "centro": r["coordenadas"]["centro"],
            **r["shortcut"],
        }
        for r in regiones
    ]
    return {
        "total": len(regiones),
        "zonas_disponibles": [
            "mexico",
            "centroamerica",
            "mexico_centroamerica",
            "caribe",
            "sudamerica",
            "latinoamerica",
            "referencia_global",
        ],
        "shortcuts": shortcuts,
        "por_zona": por_zona,
        "regiones": regiones,
    }


@router.get(
    "/regiones/calcular-bbox",
    summary="Calcula la posición real de latitud/longitud, centro, GeoJSON y celdas NASA para cualquier bbox",
)
def ruta_calcular_bbox_personalizado(
    oeste: float = Query(..., description="Longitud oeste (mínima) en grados [-180, 180]"),
    sur: float = Query(..., description="Latitud sur (mínima) en grados [-90, 90]"),
    este: float = Query(..., description="Longitud este (máxima) en grados [-180, 180]"),
    norte: float = Query(..., description="Latitud norte (máxima) en grados [-90, 90]"),
    nombre: str | None = Query(default=None, description="Nombre opcional para el shortcut"),
) -> dict[str, Any]:
    return resolver_region(region=nombre, bbox=(oeste, sur, este, norte)).a_dict()


@router.get("/regiones/{region_id}", summary="Detalle de una región predefinida con coordenadas reales y mallas NASA")
def ruta_detalle_region(region_id: str) -> dict[str, Any]:
    return resolver_region(region=region_id).a_dict()

