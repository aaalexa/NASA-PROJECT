"""Esquemas Pydantic v2 de entrada y salida de la API REST para el frontend."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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
    anual: dict[str, Any] | None = Field(
        None, description="Control de calidad de la serie anual agregada (solo cuando se pide 'anual')."
    )


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



# ================================================================================================ Down to Earth (cálculo)
class FilaMensualDTE(BaseModel):
    """Una fila mensual regional. Valores en unidades finales (mm/mes, °C, m³/m³, mm/mes) u originales NASA."""

    fecha: str = Field(..., description="Mes en formato AAAA-MM (también acepta AAAA-MM-DD).", examples=["2001-01"])
    P: float | None = Field(None, description="Precipitación (mm/mes; o mm/día si unidades='originales').")
    T: float | None = Field(None, description="Temperatura del aire a 2 m (°C; o K si unidades='originales').")
    SM: float | None = Field(None, description="Humedad del suelo 0–10 cm (m³/m³; o kg/m² si unidades='originales').")
    ET: float | None = Field(None, description="Evapotranspiración real (mm/mes; o kg/m²/s si unidades='originales').")


class PeticionCalculoDTE(BaseModel):
    """Serie mensual regional para calcular el análisis Down to Earth con el método fijo."""

    serie: list[FilaMensualDTE] = Field(..., min_length=1, max_length=5000)
    unidades: Literal["finales", "originales"] = Field(
        "finales", description="'finales' (mm/mes, °C, m³/m³, mm/mes) u 'originales' NASA (mm/día, K, kg/m², kg/m²/s)."
    )
    inicio: str = Field("2001-01", description="Inicio del período de análisis (AAAA-MM).")
    fin: str = Field("2024-12", description="Fin del período de análisis (AAAA-MM).")
    alfa: float = Field(0.05, gt=0.0, lt=0.5, description="α fijado de antemano para la familia de Holm.")
    region: str | None = Field(None, description="Id de región (solo metadatos; la serie ya es un promedio regional).")
    simulado: bool = Field(False, description="Marca los resultados como datos simulados.")
    incluir_tablas: bool = Field(False, description="Añade 'tablas' (mensual, anual, diccionario) con formato.")


class PeticionTrabajoDTE(BaseModel):
    """Análisis Down to Earth de una región con datos reales de NASA (descarga OPeNDAP en segundo plano)."""

    region: str | None = Field("corredor_seco_centroamericano", description="Id de región predefinida.")
    bbox: list[float] | None = Field(None, min_length=4, max_length=4, description="[oeste, sur, este, norte].")
    inicio: str = Field("2001-01", description="Inicio (AAAA-MM).")
    fin: str = Field("2024-12", description="Fin (AAAA-MM).")
    alfa: float = Field(0.05, gt=0.0, lt=0.5)
    forzar: bool = Field(False, description="Crea un trabajo nuevo aunque exista uno igual (por defecto se reutiliza).")
    sincrono: bool = Field(False, description="Solo pruebas: espera a que termine antes de responder.")


class _Abierto(BaseModel):
    model_config = ConfigDict(extra="allow")


class TramoDTE(_Abierto):
    start: int
    end: int
    n_years: int
    criterion: str


class MetadataDTE(_Abierto):
    project: str
    region: dict[str, Any] | None = None
    period: list[str]
    months_total: int
    years_expected: int
    years_complete_count: int
    trend_span: TramoDTE | None = Field(None, description="Tramo común de años completos usado en las 4 tendencias.")
    simulated: bool = Field(..., description="True si algún dato es sintético o simulado: rotular la vista.")
    warnings: list[str] = Field(default_factory=list)
    spatial_weighting: str
    alpha: float
    method: dict[str, Any]
    source: str


class UnidadesDTE(_Abierto):
    monthly: str
    annual: str
    slope_decade: str


class PuntoMensualDTE(_Abierto):
    date: str
    value: float | None = None
    z: float | None = None


class PuntoAnualDTE(_Abierto):
    year: int
    value: float | None = None
    fitted: float | None = None


class VariableDTE(_Abierto):
    id: str
    code: Literal["P", "T", "SM", "ET"]
    name: str
    units: UnidadesDTE
    monthly: list[PuntoMensualDTE]
    annual: list[PuntoAnualDTE]
    slope_decade: float | None = Field(None, description="Pendiente × 10 (por década).")
    ci95: list[float | None] | None = Field(None, description="IC95 % individual por década (b ± 1.96·SE) × 10.")
    p_raw: float | None = Field(None, description="p de Wald bilateral (HAC, rezago 1), sin ajustar.")
    p_holm: float | None = Field(None, description="p ajustado por Holm sobre [P, T, SM, ET]: decide la etiqueta.")
    significant: bool | None = None
    direction: Literal["aumento", "disminucion"] | None = Field(None, description="Solo con evidencia; si no, null.")
    estimate_sign: Literal["positiva", "negativa", "nula"] | None = None
    label: str = Field(..., description="Etiqueta oficial (nunca 'sin cambio').")
    summary_text: str
    sensible_al_rezago: bool | None = None
    sensitivity: dict[str, dict[str, Any]] | None = None
    quality: dict[str, Any]


class ParDTE(_Abierto):
    pair: str
    var_x: str
    var_y: str
    r: float | None = Field(None, description="Pearson entre residuos z sin estación ni tendencia (exploratorio).")
    n: int
    common_period: list[str] | None = None
    summary_text: str


class ConjuntoDTE(_Abierto):
    preprocessing: dict[str, str]
    standardized_anomalies: list[dict[str, Any]]
    pairs: dict[str, ParDTE]
    pairs_list: list[ParDTE]


class EntradaLimpiezaDTE(BaseModel):
    fecha: str | None
    variable: str | None
    valor_original: float | None
    accion: str
    motivo: str


class LimpiezaDTE(_Abierto):
    steps: list[str]
    summary: dict[str, dict[str, Any]]
    log: list[EntradaLimpiezaDTE]


class ResultadoDTE(_Abierto):
    """Resultado completo Down to Earth: metadatos, 4 variables, limpieza, análisis conjunto y conclusión."""

    metadata: MetadataDTE
    variables: dict[str, VariableDTE]
    data_cleaning: LimpiezaDTE
    joint: ConjuntoDTE
    conclusion: dict[str, Any]
    tablas: dict[str, list[dict[str, Any]]] | None = Field(
        None, description="Solo si se pide: tablas mensual, anual y diccionario con formato de presentación."
    )


class TrabajoDTEDTO(_Abierto):
    id: str
    region: str
    bbox: list[float]
    inicio: str
    fin: str
    alfa: float
    estado: Literal["pendiente", "ejecutando", "completado", "error"]
    etapa: str
    paso_actual: int
    total_pasos: int
    porcentaje: float
    mensaje: str
    etapas: list[str]
    etapas_completadas: list[str]
    creado_en: str
    actualizado_en: str
    error: str | None = None
    enlaces: dict[str, Any]
