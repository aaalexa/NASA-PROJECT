"""Rutas de análisis climático: series temporales, motor de tendencias, indicadores, escáner, dos caras y mapas."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Query

from core.api.esquemas import (
    PeticionDosCarasDTO,
    PeticionEscanerDTO,
    SerieRespuestaDTO,
    TendenciaRespuestaDTO,
)
from core.config import PERIODO_COMUN
from core.servicios.consultas import (
    consultar_indicadores,
    consultar_mapa_tendencias,
    consultar_serie,
    consultar_tendencia,
    ejecutar_dos_caras,
    ejecutar_escaner_region,
)

router = APIRouter(tags=["Series, Tendencias y Mapas"])


def _armar_bbox(
    oeste: float | None,
    sur: float | None,
    este: float | None,
    norte: float | None,
) -> tuple[float, float, float, float] | None:
    coords = (oeste, sur, este, norte)
    if all(c is None for c in coords):
        return None
    if any(c is None for c in coords):
        raise ValueError("Si especificas coordenadas de caja, debes enviar las cuatro: oeste, sur, este y norte.")
    return float(oeste), float(sur), float(este), float(norte)  # type: ignore[arg-type]


@router.get(
    "/series/{variable_id}",
    response_model=SerieRespuestaDTO,
    summary="Serie temporal regional (valores absolutos, anomalías, climatología y calidad)",
)
def ruta_consultar_serie(
    variable_id: str,
    region: str | None = Query(default="sahel", description="Id de región predefinida o slug personalizado"),
    oeste: float | None = Query(default=None, description="Longitud mínima [-180, 180]"),
    sur: float | None = Query(default=None, description="Latitud mínima [-90, 90]"),
    este: float | None = Query(default=None, description="Longitud máxima [-180, 180]"),
    norte: float | None = Query(default=None, description="Latitud máxima [-90, 90]"),
    inicio: str = Query(default=PERIODO_COMUN[0], description="Inicio del periodo (AAAA-MM)"),
    fin: str = Query(default=PERIODO_COMUN[1], description="Fin del periodo (AAAA-MM)"),
    anual: Literal["suma", "media"] | None = Query(default=None, description="Agregación anual opcional"),
    unidad: str | None = Query(default=None, description="Conversión opcional entre mm/dia y mm/mes"),
    mascara: Literal["tierra"] | None = Query(default=None, description="Aplicar máscara de tierra firme"),
    descargar: bool = Query(default=False, description="Descargar de NASA si no está en caché"),
    sintetico: bool = Query(default=False, description="Usar datos sintéticos deterministas (modo demo)"),
) -> dict[str, Any]:
    bbox = _armar_bbox(oeste, sur, este, norte)
    return consultar_serie(
        variable_id,
        region=region,
        bbox=bbox,
        inicio=inicio,
        fin=fin,
        anual=anual,
        unidad=unidad,
        mascara=mascara,
        descargar=descargar,
        sintetico=sintetico,
    )


@router.get(
    "/tendencias/{variable_id}",
    response_model=TendenciaRespuestaDTO,
    summary="Cálculo de tendencia, significancia (OLS + Mann-Kendall) y veredicto del motor",
)
def ruta_consultar_tendencia(
    variable_id: str,
    region: str | None = Query(default="sahel", description="Id de región predefinida o slug personalizado"),
    oeste: float | None = Query(default=None),
    sur: float | None = Query(default=None),
    este: float | None = Query(default=None),
    norte: float | None = Query(default=None),
    inicio: str = Query(default=PERIODO_COMUN[0], description="Inicio del periodo (AAAA-MM)"),
    fin: str = Query(default=PERIODO_COMUN[1], description="Fin del periodo (AAAA-MM)"),
    anual: Literal["suma", "media"] | None = Query(default=None, description="Agregación anual opcional"),
    unidad: str | None = Query(default=None, description="Conversión opcional entre mm/dia y mm/mes"),
    mascara: Literal["tierra"] | None = Query(default=None),
    alfa: float = Query(default=0.05, gt=0.0, lt=0.5, description="Nivel de significancia bilateral"),
    incluir_serie: bool = Query(default=True, description="Incluir los puntos de la serie para graficar"),
    descargar: bool = Query(default=False),
    sintetico: bool = Query(default=False, description="Usar datos sintéticos deterministas (modo demo)"),
) -> dict[str, Any]:
    bbox = _armar_bbox(oeste, sur, este, norte)
    return consultar_tendencia(
        variable_id,
        region=region,
        bbox=bbox,
        inicio=inicio,
        fin=fin,
        anual=anual,
        unidad=unidad,
        mascara=mascara,
        alfa=alfa,
        incluir_serie=incluir_serie,
        descargar=descargar,
        sintetico=sintetico,
    )


@router.get(
    "/indicadores",
    summary="Indicadores anuales de extremos de lluvia (CDD, R20mm, W, PRCPTOT, SDII) con GPM IMERG diario",
)
def ruta_consultar_indicadores(
    region: str | None = Query(default="sahel"),
    oeste: float | None = Query(default=None),
    sur: float | None = Query(default=None),
    este: float | None = Query(default=None),
    norte: float | None = Query(default=None),
    inicio: str = Query(default=PERIODO_COMUN[0]),
    fin: str = Query(default=PERIODO_COMUN[1]),
    cortar_en_anio: bool = Query(default=True, description="Cortar rachas secas el 31 de diciembre"),
    mascara: Literal["tierra"] | None = Query(default=None),
    alfa: float = Query(default=0.05, gt=0.0, lt=0.5),
    descargar: bool = Query(default=False),
    sintetico: bool = Query(default=False),
) -> dict[str, Any]:
    bbox = _armar_bbox(oeste, sur, este, norte)
    return consultar_indicadores(
        region=region,
        bbox=bbox,
        inicio=inicio,
        fin=fin,
        cortar_en_anio=cortar_en_anio,
        mascara=mascara,
        alfa=alfa,
        descargar=descargar,
        sintetico=sintetico,
    )


@router.get(
    "/escaner",
    summary="Escáner de todas las variables de una región ordenadas por veredicto y |SNR|",
)
def ruta_escaner_get(
    region: str | None = Query(default="sahel"),
    oeste: float | None = Query(default=None),
    sur: float | None = Query(default=None),
    este: float | None = Query(default=None),
    norte: float | None = Query(default=None),
    inicio: str = Query(default=PERIODO_COMUN[0]),
    fin: str = Query(default=PERIODO_COMUN[1]),
    grupo: str | None = Query(default=None, description="Filtrar por grupo: lluvia, causa, calculada"),
    fuente: str | None = Query(default=None, description="Filtrar por dataset: gpcp, merra2, imerg"),
    alfa: float = Query(default=0.05, gt=0.0, lt=0.5),
    descargar: bool = Query(default=False),
    sintetico: bool = Query(default=False),
) -> dict[str, Any]:
    bbox = _armar_bbox(oeste, sur, este, norte)
    return ejecutar_escaner_region(
        region=region,
        bbox=bbox,
        inicio=inicio,
        fin=fin,
        grupo=grupo,
        fuente=fuente,
        alfa=alfa,
        descargar=descargar,
        sintetico=sintetico,
    )


@router.post(
    "/escaner",
    summary="Escáner regional con selección personalizada de variables o bounding box",
)
def ruta_escaner_post(peticion: PeticionEscanerDTO) -> dict[str, Any]:
    return ejecutar_escaner_region(
        region=peticion.region,
        bbox=peticion.bbox,
        inicio=peticion.inicio,
        fin=peticion.fin,
        variables=peticion.variables,
        grupo=peticion.grupo,
        fuente=peticion.fuente,
        alfa=peticion.alfa,
        descargar=peticion.descargar,
        sintetico=peticion.sintetico,
    )


@router.get(
    "/dos-caras",
    summary="Compara 'las dos caras de la lluvia' entre dos regiones o dos variables/indicadores",
)
def ruta_dos_caras_get(
    variable: str = Query(default="lluvia_gpcp"),
    region_a: str = Query(default="sahel"),
    region_b: str = Query(default="sureste_mexico"),
    variable_b: str | None = Query(default=None),
    inicio: str = Query(default=PERIODO_COMUN[0]),
    fin: str = Query(default=PERIODO_COMUN[1]),
    alfa: float = Query(default=0.05, gt=0.0, lt=0.5),
    descargar: bool = Query(default=False),
    sintetico: bool = Query(default=False),
) -> dict[str, Any]:
    return ejecutar_dos_caras(
        variable=variable,
        region_a=region_a,
        region_b=region_b,
        variable_b=variable_b,
        inicio=inicio,
        fin=fin,
        alfa=alfa,
        descargar=descargar,
        sintetico=sintetico,
    )


@router.post(
    "/dos-caras",
    summary="Compara 'las dos caras' con regiones o bounding boxes personalizados",
)
def ruta_dos_caras_post(peticion: PeticionDosCarasDTO) -> dict[str, Any]:
    return ejecutar_dos_caras(
        variable=peticion.variable,
        region_a=peticion.region_a,
        bbox_a=peticion.bbox_a,
        region_b=peticion.region_b,
        bbox_b=peticion.bbox_b,
        variable_b=peticion.variable_b,
        inicio=peticion.inicio,
        fin=peticion.fin,
        alfa=peticion.alfa,
        descargar=peticion.descargar,
        sintetico=peticion.sintetico,
    )


@router.get(
    "/mapas/{variable_id}",
    summary="Mapa de tendencias por píxel (pendiente_decada, p_t, p_mk, veredicto) para una región",
)
def ruta_mapa_tendencias(
    variable_id: str,
    region: str | None = Query(default="noreste_mexico"),
    oeste: float | None = Query(default=None),
    sur: float | None = Query(default=None),
    este: float | None = Query(default=None),
    norte: float | None = Query(default=None),
    inicio: str = Query(default=PERIODO_COMUN[0]),
    fin: str = Query(default=PERIODO_COMUN[1]),
    mascara: Literal["tierra"] | None = Query(default=None),
    alfa: float = Query(default=0.05, gt=0.0, lt=0.5),
    descargar: bool = Query(default=False),
    sintetico: bool = Query(default=False),
) -> dict[str, Any]:
    bbox = _armar_bbox(oeste, sur, este, norte)
    return consultar_mapa_tendencias(
        variable_id,
        region=region,
        bbox=bbox,
        inicio=inicio,
        fin=fin,
        mascara=mascara,
        alfa=alfa,
        descargar=descargar,
        sintetico=sintetico,
    )

