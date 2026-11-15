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
  /** Individual 95 % CI per decade (b ± 1.96·SE) × 10. */
  ci95: [number | null, number | null] | null;
  p_raw: number | null;
  /** Holm-adjusted p over the fixed family [P, T, SM, ET]: this decides the label. */
  p_holm: number | null;
  significant: boolean | null;
  /** Only set when there is statistical evidence; null otherwise (never "stable"). */
  direction: "aumento" | "disminucion" | null;
  /** Sign of the estimated slope, also when the evidence is insufficient. */
  estimate_sign: "positiva" | "negativa" | "nula" | null;
  /** Official label (Spanish): "aumento/disminución con evidencia estadística según este método", "evidencia insuficiente"… */
  label: string;
  summary_text: string;
  sensible_al_rezago: boolean | null;
  quality: DteQuality;
}

export interface DteCleaningSummary {
  unidad: string;
  limites_fisicos: [number, number];
  n_meses_esperados: number;
  n_meses_validos: number;
  n_meses_faltantes: number;
  anios_incompletos: number[];
  relleno: number;
  fuera_de_rango: number;
  no_finitos: number;
  duplicados_contradictorios: number;
  duplicados_identicos: number;
  meses_ausentes: number;
  ceros_exactos: number;
  fuera_de_periodo: number;
}

export interface DteCleaningEntry {
  fecha: string | null;
  variable: string | null;
  valor_original: number | null;
  accion: string;
  motivo: string;
}

export type DteTable = "mensual" | "anual" | "limpieza" | "diccionario" | "serie_regional";
export type TableRow = Record<string, string | number | null>;

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
    /** "opendap_memoria" (real NASA data), "sintetico", "entrada_usuario" (uploaded CSV)… */
    source: string;
    /** True when any value is synthetic or the user flagged the upload as simulated: label the whole view. */
    simulated: boolean;
    warnings: string[];
    /** Common span of complete, consecutive years used for the four trends. */
    trend_span: { start: number; end: number; n_years: number; criterion: string } | null;
    spatial_weighting?: string;
    months_total: number;
    years_expected: number;
    years_complete_count: number;
    region: { id: string; nombre: string; bbox: [number, number, number, number]; [k: string]: unknown } | null;
    input?: { rows: number; units: string; columns_used: Record<string, string>; missing_variables: string[]; file_name?: string };
    [k: string]: unknown;
  };
  variables: Record<DteCode, DteVariable>;
  data_cleaning: {
    steps: string[];
    summary: Record<DteCode, DteCleaningSummary>;
    log: DteCleaningEntry[];
  };
  /** Only when requested (incluir_tablas): presentation tables already formatted by the backend. */
  tablas?: { mensual: TableRow[]; anual: TableRow[]; diccionario: TableRow[] } | null;
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

/** `POST/GET /api/v1/down-to-earth/trabajos`: real NASA download + analysis running on the server. */
export interface DteJob {
  id: string;
  region: string;
  bbox: [number, number, number, number];
  inicio: string;
  fin: string;
  alfa: number;
  estado: "pendiente" | "ejecutando" | "completado" | "error";
  /** "P" | "T" | "SM" | "ET" | "analisis" | "en cola" | "completado" */
  etapa: string;
  paso_actual: number;
  total_pasos: number;
  porcentaje: number;
  mensaje: string;
  etapas: string[];
  etapas_completadas: string[];
  error: string | null;
  enlaces: { estado: string; resultado: string; tablas: Record<DteTable, string> };
}

export interface Salud {
  estado: string;
  credenciales_earthdata: { listo: boolean };
  dte_precarga?: { id: string; region: string; estado: DteJob["estado"]; porcentaje: number; error: string | null }[];
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

/** A real-data job finished with `estado: "error"` (e.g. a NASA product was unavailable). Never replaced by synthetic data. */
export class JobFailedError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "JobFailedError";
  }
}

export type ApiFailure =
  | "offline"
  | "bad_request"
  | "not_found"
  | "no_data_in_memory"
  | "series_rejected"
  | "validation"
  | "job_failed"
  | "job_not_ready"
  | "file_too_large"
  | "aborted"
  | "unknown";

export function classifyError(e: unknown): ApiFailure {
  if (e instanceof DOMException && e.name === "AbortError") return "aborted";
  if (e instanceof BackendOfflineError) return "offline";
  if (e instanceof JobFailedError) return "job_failed";
  if (e instanceof ApiError) {
    if (e.status === 400) return "bad_request";
    if (e.status === 404) return e.body.error === "datos_no_disponibles_en_memoria" ? "no_data_in_memory" : "not_found";
    if (e.status === 409) {
      const detail = e.body.detail as { error?: string } | undefined;
      return detail?.error === "trabajo_con_error" ? "job_failed" : "job_not_ready";
    }
    if (e.status === 413) return "file_too_large";
    if (e.status === 422) return e.body.error === "serie_rechazada" ? "series_rejected" : "validation";
  }
  return "unknown";
}

/** Human detail of a failure when the backend gave one (job error text, 400 message…). */
export function failureDetail(e: unknown): string | undefined {
  if (e instanceof JobFailedError) return e.message;
  if (e instanceof ApiError) {
    const detail = e.body.detail as { mensaje?: string } | string | undefined;
    return e.body.mensaje ?? (typeof detail === "string" ? detail : detail?.mensaje);
  }
  return undefined;
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

async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new BackendOfflineError();
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, body);
  return body as T;
}

export const apiGet = <T>(path: string, params: Params = {}, signal?: AbortSignal) =>
  request<T>(buildUrl(path, params), { signal });

export const apiPost = <T>(path: string, payload: unknown, signal?: AbortSignal) =>
  request<T>(buildUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });

/** multipart/form-data (file uploads). The browser sets the boundary header itself. */
export const apiPostForm = <T>(path: string, form: FormData, signal?: AbortSignal) =>
  request<T>(buildUrl(path), { method: "POST", body: form, signal });

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

/** `GET /api/v1/down-to-earth/analisis` (same handler as `/demo/result`): instant when the cubes are in RAM. */
export const fetchDteResult = (o: DteOptions) =>
  apiGet<DteResult>("/api/v1/down-to-earth/analisis", dteParams(o), o.signal);

/** Download links never trigger a synchronous NASA download: in "descargar" mode the data is read from RAM. */
export const csvUrl = (freq: "mensual" | "anual", o: Omit<DteOptions, "signal">) =>
  buildUrl(`/api/v1/down-to-earth/csv/${freq}`, dteParams({ ...o, mode: o.mode === "descargar" ? "memoria" : o.mode }));

// ---------------------------------------------------------------------------------------------
// Down to Earth with real NASA data: background jobs (download ~30 min per region the first time)
// ---------------------------------------------------------------------------------------------

type JobRequest = Pick<DteOptions, "region" | "inicio" | "fin">;

/** Body of `POST /trabajos`: an official region id, or a custom slug plus its full bbox. */
export function jobBody(o: JobRequest) {
  const p = regionParams(o.region);
  const bbox = "oeste" in p ? [p.oeste, p.sur, p.este, p.norte] : undefined;
  return { region: p.region, bbox, inicio: clampPeriod(toYearMonth(o.inicio)), fin: clampPeriod(toYearMonth(o.fin)) };
}

/** Starts the job, or returns the existing one with the same parameters (the backend de-duplicates). */
export const startDteJob = (o: JobRequest, signal?: AbortSignal) =>
  apiPost<DteJob>("/api/v1/down-to-earth/trabajos", jobBody(o), signal);

export const fetchDteJob = (id: string, signal?: AbortSignal) =>
  apiGet<DteJob>(`/api/v1/down-to-earth/trabajos/${encodeURIComponent(id)}`, {}, signal);

export const fetchDteJobResult = (id: string, signal?: AbortSignal) =>
  apiGet<DteResult>(`/api/v1/down-to-earth/trabajos/${encodeURIComponent(id)}/resultado`, {}, signal);

export const dteTableUrl = (id: string, tabla: DteTable, formato: "csv" | "json" = "csv") =>
  buildUrl(`/api/v1/down-to-earth/trabajos/${encodeURIComponent(id)}/tablas/${tabla}`, { formato });

export const JOB_POLL_MS = 5000;

function sleep(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException("Aborted", "AbortError"));
    const id = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(id);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });
}

/**
 * Runs a real-data job to the end: start (or reuse) it, poll every JOB_POLL_MS reporting progress, then fetch the
 * result. A 404 while polling means another server worker answered (jobs live in each worker's RAM): the job is
 * requested again and the backend de-duplicates it. Brief network drops are retried. A failed job throws
 * JobFailedError: there is never a synthetic fallback for real data.
 */
export async function runDteJob(o: JobRequest, onProgress: (job: DteJob) => void, signal?: AbortSignal) {
  let job = await startDteJob(o, signal);
  onProgress(job);
  let offlineRetries = 0;
  while (job.estado !== "completado") {
    if (job.estado === "error") throw new JobFailedError(job.error ?? job.mensaje);
    await sleep(JOB_POLL_MS, signal);
    try {
      job = await fetchDteJob(job.id, signal);
      offlineRetries = 0;
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) job = await startDteJob(o, signal);
      else if (e instanceof BackendOfflineError && offlineRetries < 3) {
        offlineRetries += 1;
        continue;
      } else throw e;
    }
    onProgress(job);
  }
  const result = await fetchDteJobResult(job.id, signal);
  return { result, job };
}

// ---------------------------------------------------------------------------------------------
// Exact calculation on data sent by the client
// ---------------------------------------------------------------------------------------------

export interface CalcOptions {
  unidades: "finales" | "originales";
  simulado?: boolean;
  inicio?: string;
  fin?: string;
  region?: string;
}

/** `POST /api/v1/down-to-earth/calcular/csv`: uploads a monthly regional CSV and returns the full analysis + tables. */
export function analyzeCsv(file: File, o: CalcOptions, signal?: AbortSignal) {
  const form = new FormData();
  form.append("archivo", file);
  form.append("unidades", o.unidades);
  form.append("simulado", String(Boolean(o.simulado)));
  form.append("incluir_tablas", "true");
  if (o.inicio) form.append("inicio", o.inicio);
  if (o.fin) form.append("fin", o.fin);
  if (o.region) form.append("region", o.region);
  return apiPostForm<DteResult>("/api/v1/down-to-earth/calcular/csv", form, signal);
}

export interface MonthlyRow {
  fecha: string;
  P?: number | null;
  T?: number | null;
  SM?: number | null;
  ET?: number | null;
}

/** `POST /api/v1/down-to-earth/calcular`: same calculation from rows already in the browser (JSON). */
export const calculateDte = (serie: MonthlyRow[], o: CalcOptions, signal?: AbortSignal) =>
  apiPost<DteResult>("/api/v1/down-to-earth/calcular", { serie, ...o, incluir_tablas: true }, signal);

/** CSV text from table rows (empty cell = missing), for client-side downloads of uploaded results. */
export function rowsToCsv(rows: TableRow[]): string {
  if (rows.length === 0) return "";
  const cols = Object.keys(rows[0]);
  const cell = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [cols.join(","), ...rows.map((r) => cols.map((c) => cell(r[c])).join(","))].join("\n") + "\n";
}

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
