/**
 * Typed client for the Moody Trends FastAPI backend (see docs/api/FRONTEND_API.md).
 * Rules enforced here: dates are "YYYY-MM", a bbox is sent complete or not at all,
 * NASA credentials never reach the browser.
 */
import type { GeoPoint, RegionAnalysisPayload } from "@/types/geo";

export const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

/** Backend period limits (every NASA source covers it). */
export const PERIOD_MIN = "2001-01";
export const PERIOD_MAX = "2024-12";

export type DteCode = "P" | "T" | "SM" | "ET";

/** Backend variable id -> Down to Earth code (the 4 core variables analysed together with Holm). */
export const ID_TO_DTE: Record<string, DteCode> = {
  lluvia_gpcp: "P",
  temp_aire: "T",
  humedad_suelo: "SM",
  evapotranspiracion: "ET",
};
export const DTE_CODES: DteCode[] = ["P", "T", "SM", "ET"];

export type DataMode = "sintetico" | "descargar" | "memoria";

// ---------------------------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------------------------

export interface BBox {
  oeste: number;
  sur: number;
  este: number;
  norte: number;
}

export interface DteQuality {
  n_months_valid?: number;
  n_years_complete?: number;
  complete_period?: boolean;
  warnings: string[];
  [k: string]: unknown;
}

export interface DteVariable {
  id: string;
  code: DteCode;
  name: string;
  question: string;
  units: { monthly: string; annual: string; slope_decade: string };
  monthly: { date: string; value: number | null; z: number | null }[];
  annual: { year: number; value: number | null; fitted: number | null }[];
  slope_decade: number | null;
  ci95: [number, number] | null;
  p_raw: number | null;
  p_holm: number | null;
  significant: boolean;
  direction: "aumento" | "disminucion" | "estable";
  label: string;
  summary_text: string;
  sensible_al_rezago: boolean;
  quality: DteQuality;
}

export interface DtePair {
  pair: string;
  var_x: string;
  var_y: string;
  question: string;
  interpretation_note?: string;
  r: number | null;
  n: number;
  direction_description?: string;
  summary_text: string;
}

export interface DteResult {
  metadata: {
    period: [string, string];
    alpha: number;
    source: "sintetico" | "opendap_memoria";
    months_total: number;
    years_expected: number;
    years_complete_count: number;
    region: { id: string; nombre: string; bbox: [number, number, number, number]; [k: string]: unknown };
    [k: string]: unknown;
  };
  variables: Record<DteCode, DteVariable>;
  joint: {
    standardized_anomalies: { date: string; P: number | null; T: number | null; SM: number | null; ET: number | null }[];
    pairs_list: DtePair[];
  };
  conclusion: {
    joint_reading: string;
    changes_with_statistical_evidence: string[];
    inconclusive_or_insufficient_evidence: string[];
    exploratory_associations: string[];
    methodological_limits: string[];
  };
}

export interface Salud {
  estado: string;
  credenciales_earthdata: { listo: boolean };
  [k: string]: unknown;
}

export interface BackendRegion {
  id: string;
  nombre: string;
  descripcion?: string;
  zona: string;
  pais?: string;
  es_latinoamerica?: boolean;
  bbox: [number, number, number, number];
}

/** One entry of `GET /api/v1/catalogo` -> `variables[]`. */
export interface BackendVariable {
  id: string;
  codigo_dte: DteCode | null;
  grupo: string;
  fuente: string;
  nombre_simple: string;
  definicion_simple: string;
  pregunta?: string;
  por_que_elegirla?: string;
  dataset: string;
  short_name?: string;
  unidad_final: string;
  frecuencia: "mensual" | "anual" | "diaria";
  analizable: boolean;
  resolucion?: string;
  desde?: string;
}

export interface BackendDataset {
  id: string;
  nombre: string;
  [k: string]: unknown;
}

export interface Catalogo {
  datasets: BackendDataset[];
  variables: BackendVariable[];
  regiones: BackendRegion[];
  periodos: { comun: [string, string]; global: [string, string] };
  down_to_earth?: Record<string, unknown>;
}

/** `GET /api/v1/tendencias/{id}` for variables outside the 4-variable Down to Earth family. */
export interface TendenciaMotor {
  variable: string;
  n: number;
  pendiente_ols_decada: number | null;
  ic95_decada: [number, number] | null;
  p_t: number | null;
  sen_decada: number | null;
  p_mk: number | null;
  cambio_pct_decada: number | null;
  snr: number | null;
  veredicto: "significativo" | "indicio" | "sin tendencia clara";
  direccion: "sube" | "baja" | "estable";
  n_star_anios: number | null;
  anios_faltantes: number | null;
}

export interface TendenciaRespuesta {
  tendencia: TendenciaMotor;
  metadatos: {
    nombre_simple: string;
    unidad: string;
    unidad_pendiente: string;
    frecuencia_serie: string;
    media_climatologia?: number | null;
    recta_ols?: { beta0: number; beta1_por_paso: number };
    fuente_datos: "sintetico" | "opendap_memoria";
    [k: string]: unknown;
  };
  puntos?: { fecha: string; t: number; valor: number | null; anomalia: number | null }[];
}

// ---------------------------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: {
      error?: string;
      mensaje?: string;
      sugerencia?: string;
      reporte?: Record<string, unknown>;
      detail?: unknown;
      [k: string]: unknown;
    }
  ) {
    super(body?.mensaje ?? `HTTP ${status}`);
    this.name = "ApiError";
  }
}

/** Network failure: the backend is not running or CORS blocks the origin. */
export class BackendOfflineError extends Error {
  constructor() {
    super(`No response from ${BACKEND_URL}`);
    this.name = "BackendOfflineError";
  }
}

export type ApiFailure =
  | "offline"
  | "bad_request"
  | "not_found"
  | "no_data_in_memory"
  | "series_rejected"
  | "validation"
  | "aborted"
  | "unknown";

export function classifyError(e: unknown): ApiFailure {
  if (e instanceof DOMException && e.name === "AbortError") return "aborted";
  if (e instanceof BackendOfflineError) return "offline";
  if (e instanceof ApiError) {
    if (e.status === 400) return "bad_request";
    if (e.status === 404) return e.body.error === "datos_no_disponibles_en_memoria" ? "no_data_in_memory" : "not_found";
    if (e.status === 422) return e.body.error === "serie_rechazada" ? "series_rejected" : "validation";
  }
  return "unknown";
}

// ---------------------------------------------------------------------------------------------
// Geometry helpers
// ---------------------------------------------------------------------------------------------

/** "2015-03-21" -> "2015-03". The backend rejects full dates with HTTP 400. */
export const toYearMonth = (iso: string) => iso.trim().slice(0, 7);

/** Clamp a "YYYY-MM" value into the period every source covers. */
export const clampPeriod = (ym: string) => (ym < PERIOD_MIN ? PERIOD_MIN : ym > PERIOD_MAX ? PERIOD_MAX : ym);

/**
 * Bounding box of the drawn polygon. NASA grids are 0.25-0.5 degrees, so very small regions
 * (a city) are widened to at least `minSpan` degrees around their centre, or the box would hold no cell.
 */
export function bboxFromPoints(points: GeoPoint[], minSpan = 1): BBox {
  const lats = points.map((p) => p.lat);
  const lngs = points.map((p) => p.lng);
  let oeste = Math.min(...lngs);
  let este = Math.max(...lngs);
  let sur = Math.min(...lats);
  let norte = Math.max(...lats);
  if (este - oeste < minSpan) {
    const c = (este + oeste) / 2;
    oeste = c - minSpan / 2;
    este = c + minSpan / 2;
  }
  if (norte - sur < minSpan) {
    const c = (norte + sur) / 2;
    sur = c - minSpan / 2;
    norte = c + minSpan / 2;
  }
  const r = (n: number) => Number(n.toFixed(4));
  return {
    oeste: r(Math.max(-180, oeste)),
    sur: r(Math.max(-90, sur)),
    este: r(Math.min(180, este)),
    norte: r(Math.min(90, norte)),
  };
}

export function toRegionSlug(name: string): string {
  return (
    name
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_|_$/g, "")
      .slice(0, 48) || "region_personalizada"
  );
}

/** Region query for the backend: an official id when we know it, otherwise slug + full bbox. */
export function regionParams(region: Pick<RegionAnalysisPayload, "regionName" | "triangleVertices" | "outline" | "backendId">) {
  if (region.backendId) return { region: region.backendId };
  return { region: toRegionSlug(region.regionName), ...bboxFromPoints(region.outline ?? region.triangleVertices) };
}

/** Rectangle corners (SW, SE, NE, NW) of a bbox, as the outline the globe draws. */
export function outlineFromBBox([oeste, sur, este, norte]: [number, number, number, number]): GeoPoint[] {
  return [
    { lat: sur, lng: oeste },
    { lat: sur, lng: este },
    { lat: norte, lng: este },
    { lat: norte, lng: oeste },
  ];
}

// ---------------------------------------------------------------------------------------------
// HTTP
// ---------------------------------------------------------------------------------------------

type Params = Record<string, string | number | boolean | undefined | null>;

function buildUrl(path: string, params: Params = {}) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  }
  return `${BACKEND_URL}${path}${qs.size ? `?${qs}` : ""}`;
}

export async function apiGet<T>(path: string, params: Params = {}, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(buildUrl(path, params), { signal });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new BackendOfflineError();
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, body);
  return body as T;
}

export const fetchSalud = (signal?: AbortSignal) => apiGet<Salud>("/api/v1/salud", {}, signal);

/** One call to initialise the whole UI: datasets, variables, regions, periods. */
export const fetchCatalogo = (signal?: AbortSignal) => apiGet<Catalogo>("/api/v1/catalogo", {}, signal);

export interface DteOptions {
  region: Pick<RegionAnalysisPayload, "regionName" | "triangleVertices" | "outline" | "backendId">;
  inicio: string;
  fin: string;
  mode: DataMode;
  signal?: AbortSignal;
}

function modeParams(mode: DataMode) {
  return {
    sintetico: mode === "sintetico" ? true : undefined,
    descargar: mode === "descargar" ? true : undefined,
    // Never let the backend silently fall back to synthetic data when real data was requested.
    estricto_memoria: mode === "memoria" ? true : undefined,
  };
}

export function dteParams(o: Omit<DteOptions, "signal">) {
  return {
    ...regionParams(o.region),
    inicio: clampPeriod(toYearMonth(o.inicio)),
    fin: clampPeriod(toYearMonth(o.fin)),
    ...modeParams(o.mode),
  };
}

export const fetchDteResult = (o: DteOptions) => apiGet<DteResult>("/demo/result", dteParams(o), o.signal);

export const csvUrl = (freq: "mensual" | "anual", o: Omit<DteOptions, "signal">) =>
  buildUrl(`/demo/csv/${freq}`, dteParams(o));

export function fetchTendencia(variableId: string, o: Omit<DteOptions, "signal"> & { signal?: AbortSignal }) {
  return apiGet<TendenciaRespuesta>(
    `/api/v1/tendencias/${encodeURIComponent(variableId)}`,
    { ...dteParams(o), incluir_serie: true },
    o.signal
  );
}

/** `GET /api/v1/mapas/{id}`: per-pixel trend map (matrices are [lat][lon], null = no data). */
export interface MapaTendencias {
  variable: string;
  nombre_simple?: string;
  unidad_pendiente: string;
  fuente_datos: "sintetico" | "opendap_memoria";
  lat: number[];
  lon: number[];
  pendiente_decada: (number | null)[][];
  p_t: (number | null)[][];
  p_mk: (number | null)[][];
  /** 2 = significant, 1 = hint, 0 = no clear trend. */
  veredicto: (number | null)[][];
  resumen: {
    n_pixeles_total: number;
    n_pixeles_validos: number;
    n_significativos_secos: number;
    n_significativos_humedos: number;
    n_indicio: number;
  };
}

export function fetchMapa(variableId: string, o: Omit<DteOptions, "signal"> & { signal?: AbortSignal }) {
  return apiGet<MapaTendencias>(`/api/v1/mapas/${encodeURIComponent(variableId)}`, dteParams(o), o.signal);
}
