"""Esquemas Pydantic v2 de entrada y salida de la API REST para el frontend."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RegionDTO(BaseModel):
    id: str = Field(..., description="Identificador slug de la región (ej. 'noreste_mexico', 'corredor_seco_centroamericano').")
    nombre: str
    descripcion: str = ""
    zona: str = "personalizada"
    pais: str = ""
    es_latinoamerica: bool = False
    bbox: list[float] = Field(..., min_length=4, max_length=4, description="[oeste, sur, este, norte] en grados.")
    predefinida: bool = True
    coordenadas: dict[str, Any] | None = None
    mallas_reales: dict[str, Any] | None = None
    shortcut: dict[str, Any] | None = None


class CalidadDTO(BaseModel):
    aceptada: bool
    n_esperados: int
    n_faltantes: int
    fraccion_faltante: float
    motivo: str | None = None
    meses_poca_cobertura: list[int] | None = None


class PuntoSerieDTO(BaseModel):
    fecha: str = Field(..., description="'AAAA-MM' para series mensuales o 'AAAA' para series anuales.")
    t: float = Field(..., description="Eje numérico de tiempo (meses desde el inicio o año).")
    valor: float | None = Field(None, description="Valor regional en las unidades de la variable.")
    anomalia: float | None = Field(None, description="Anomalía respecto a la climatología mensual (si aplica).")


class MesClimatologiaDTO(BaseModel):
    mes: int = Field(..., ge=1, le=12)
    valor: float | None = None


class SerieRespuestaDTO(BaseModel):
    variable: str
    nombre_simple: str
    definicion_simple: str
    grupo: str
    dataset: str
    short_name: str | None
    unidad: str
    frecuencia_serie: Literal["mensual", "anual"]
    region: RegionDTO
    periodo: list[str]
    media_climatologia: float | None
    climatologia_mensual: list[MesClimatologiaDTO] | None = None
    calidad: CalidadDTO
    puntos: list[PuntoSerieDTO]
    fuente_datos: Literal["opendap_memoria", "sintetico"]


class TendenciaMotorDTO(BaseModel):
    """Esquema exacto devuelto por motor.tendencias.calcular_tendencia (20 claves)."""

    variable: str
    region: str
    periodo: list[str]
    n: int
    r1: float
    n_ef: float
    pendiente_ols_decada: float
    ic95_decada: list[float]
    p_t: float
    sen_decada: float
    mk_z: float
    mk_tau: float
    p_mk: float
    cambio_pct_decada: float | None
    snr: float | None
    n_star_anios: float | None
    anios_faltantes: float | None
    veredicto: Literal["significativo", "indicio", "sin tendencia clara"]
    direccion: Literal["sube", "baja", "estable"]
    metodos: list[str]


class TendenciaRespuestaDTO(BaseModel):
    tendencia: TendenciaMotorDTO
    metadatos: dict[str, Any]
    puntos: list[PuntoSerieDTO] | None = None
    climatologia_mensual: list[MesClimatologiaDTO] | None = None


class PeticionEscanerDTO(BaseModel):
    region: str | None = Field(
        default="sahel",
        description="Id de región predefinida (ej. 'sahel', 'noreste_mexico') o nombre personalizado si se envía bbox.",
    )
    bbox: list[float] | None = Field(
        default=None,
        min_length=4,
        max_length=4,
        description="Bounding box opcional [oeste, sur, este, norte] en grados.",
    )
    inicio: str = Field(default="2001-01", description="Inicio del periodo en formato AAAA-MM.")
    fin: str = Field(default="2024-12", description="Fin del periodo en formato AAAA-MM.")
    variables: list[str] | None = Field(
        default=None,
        description="Lista opcional de ids de variables a escanear; si se omite, escanea todas las analizables.",
    )
    grupo: str | None = Field(default=None, description="Filtrar por grupo: lluvia, causa o calculada.")
    fuente: str | None = Field(default=None, description="Filtrar por dataset: gpcp, merra2 o imerg.")
    alfa: float = Field(default=0.05, gt=0.0, lt=0.5)
    descargar: bool = Field(default=False, description="Si True, descarga de NASA lo que no esté en caché.")
    sintetico: bool = Field(default=False, description="Si True, usa datos sintéticos deterministas (modo demo).")


class PeticionDosCarasDTO(BaseModel):
    variable: str = Field(default="lluvia_gpcp", description="Variable principal (ej. 'lluvia_gpcp').")
    region_a: str | None = Field(default="sahel", description="Primera región a comparar.")
    bbox_a: list[float] | None = Field(default=None, min_length=4, max_length=4)
    region_b: str | None = Field(default="sureste_mexico", description="Segunda región (o la misma si se compara variable_b).")
    bbox_b: list[float] | None = Field(default=None, min_length=4, max_length=4)
    variable_b: str | None = Field(
        default=None,
        description="Segunda variable opcional (ej. 'r20mm_imerg' frente a 'cdd_imerg' en la misma región).",
    )
    inicio: str = Field(default="2001-01")
    fin: str = Field(default="2024-12")
    alfa: float = Field(default=0.05, gt=0.0, lt=0.5)
    descargar: bool = Field(default=False)
    sintetico: bool = Field(default=False)


class PeticionDescargaDTO(BaseModel):
    variable: str = Field(..., description="Id de la variable del catálogo (ej. 'lluvia_gpcp', 'lluvia_merra2', 'lluvia_imerg_mes').")
    region: str | None = Field(default="sahel", description="Id de región predefinida o slug para la caché.")
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)
    inicio: str = Field(default="2001-01", description="Inicio en formato AAAA-MM.")
    fin: str = Field(default="2024-12", description="Fin en formato AAAA-MM.")
    forzar: bool = Field(default=False, description="Si True, vuelve a descargar aunque exista en caché.")
    sincrono: bool = Field(default=False, description="Si True, espera a que termine la descarga antes de responder.")

