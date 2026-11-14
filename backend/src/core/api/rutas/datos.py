"""Rutas de OPeNDAP y caché en memoria RAM (sin almacenar archivos NetCDF/HDF en disco)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, status

from core.api.esquemas import PeticionDescargaDTO
from core.config import PERIODO_COMUN
from core.motor.datos import inventario_cache, limpiar_cache_memoria, validar_periodo
from core.motor.escaner import limpiar_cache_mapas_memoria
from core.servicios.consultas import describir_consulta_opendap, obtener_catalogo
from core.servicios.descargas import obtener_gestor_descargas
from core.servicios.regiones import resolver_region

router = APIRouter(tags=["OPeNDAP y Caché en Memoria RAM"])


@router.get(
    "/opendap/consulta",
    summary="Inspecciona los índices espaciales y las expresiones OPeNDAP (DAP4/DAP2) sin almacenar en disco",
)
def ruta_describir_opendap(
    variable: str = Query(default="lluvia_gpcp", description="Id de la variable del catálogo"),
    region: str | None = Query(default="sahel", description="Id de región predefinida o slug"),
    oeste: float | None = Query(default=None),
    sur: float | None = Query(default=None),
    este: float | None = Query(default=None),
    norte: float | None = Query(default=None),
    inicio: str = Query(default=PERIODO_COMUN[0]),
    fin: str = Query(default=PERIODO_COMUN[1]),
) -> dict[str, Any]:
    coords = (oeste, sur, este, norte)
    if all(c is None for c in coords):
        bbox = None
    elif any(c is None for c in coords):
        raise ValueError("Si especificas coordenadas de caja, debes enviar las cuatro: oeste, sur, este y norte.")
    else:
        bbox = (float(oeste), float(sur), float(este), float(norte))  # type: ignore[arg-type]
    return describir_consulta_opendap(variable, region=region, bbox=bbox, inicio=inicio, fin=fin)


@router.get("/cache", summary="Inventario de cubos actualmente en la caché LRU de memoria RAM")
def ruta_inventario_cache(
    variable: str | None = Query(default=None, description="Filtrar por id de variable"),
) -> dict[str, Any]:
    items = inventario_cache(variable)
    kb_total = round(sum(float(i.get("kb_ram", 0.0)) for i in items), 2)
    return {
        "almacenamiento_disco": False,
        "tipo_cache": "lru_memoria_ram",
        "total": len(items),
        "kb_ram_total": kb_total,
        "entradas": items,
    }


@router.delete("/cache", summary="Vacía la caché LRU en memoria RAM")
def ruta_limpiar_cache(
    variable: str | None = Query(default=None, description="Opcional: limpiar solo una variable"),
) -> dict[str, Any]:
    eliminadas = limpiar_cache_memoria(variable)
    mapas_eliminados = limpiar_cache_mapas_memoria() if variable is None else 0
    return {
        "eliminadas_cubos": eliminadas,
        "eliminadas_mapas": mapas_eliminados,
    }


@router.post(
    "/opendap/precargar",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Consulta NASA GES DISC vía OPeNDAP y precarga el subconjunto regional en memoria RAM",
)
@router.post(
    "/descargas",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Consulta NASA GES DISC vía OPeNDAP y precarga el subconjunto regional en memoria RAM",
)
def ruta_lanzar_descarga(peticion: PeticionDescargaDTO) -> dict[str, Any]:
    catalogo = obtener_catalogo()
    if peticion.variable not in catalogo:
        raise KeyError(f"Variable '{peticion.variable}' no existe en el catálogo")
    validar_periodo(peticion.inicio, peticion.fin)
    reg = resolver_region(peticion.region, peticion.bbox)
    gestor = obtener_gestor_descargas()
    tarea = gestor.lanzar(
        peticion.variable,
        reg.id,
        reg.bbox,
        peticion.inicio,
        peticion.fin,
        catalogo,
        forzar=peticion.forzar,
        sincrono=peticion.sincrono,
    )
    return tarea.a_dict()


@router.get("/descargas", summary="Lista las tareas OPeNDAP en memoria recientes y en curso")
def ruta_listar_descargas() -> dict[str, Any]:
    gestor = obtener_gestor_descargas()
    tareas = gestor.listar()
    return {"total": len(tareas), "tareas": tareas}


@router.get("/descargas/{tarea_id}", summary="Estado y progreso de una tarea OPeNDAP en memoria")
def ruta_estado_descarga(tarea_id: str) -> dict[str, Any]:
    gestor = obtener_gestor_descargas()
    return gestor.obtener(tarea_id).a_dict()
