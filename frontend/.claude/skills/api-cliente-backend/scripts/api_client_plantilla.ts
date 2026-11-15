/**
 * Plantilla de cliente HTTP tipado para conectar el frontend Next.js con la API FastAPI.
 * Copiar a: frontend/src/lib/api.ts
 */
import type { GeoPoint, VariableId } from "@/types/geo";

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export type DteCode = "P" | "T" | "SM" | "ET";

export const FRONT_TO_DTE_CODE: Partial<Record<VariableId, DteCode>> = {
  precipitation: "P",
  temperature: "T",
  moisture: "SM",
  evapotranspiration: "ET",
  // "vegetation" (NDVI) no está en el catálogo del backend v0.2.0
};

export const FRONT_TO_BACKEND_VAR: Partial<Record<VariableId, string>> = {
  precipitation: "lluvia_gpcp",
  temperature: "temp_aire",
  moisture: "humedad_suelo",
  evapotranspiration: "evapotranspiracion",
};

export interface BBoxParams {
  oeste: number;
  sur: number;
  este: number;
  norte: number;
}

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
    },
  ) {
    super(body?.mensaje ?? `Error HTTP ${status}`);
    this.name = "ApiError";
  }
}

/** Recorta cualquier fecha ISO ("2001-01-01" o "2001-01") al formato obligatorio "AAAA-MM". */
export function toYearMonth(dateStr: string): string {
  return dateStr.trim().slice(0, 7);
}

/** Calcula el bounding box [oeste, sur, este, norte] a partir de los 3 vértices del triángulo del frontend. */
export function bboxFromTriangle(vertices: GeoPoint[]): BBoxParams {
  const lats = vertices.map((v) => v.lat);
  const lngs = vertices.map((v) => v.lng);
  return {
    oeste: Number(Math.min(...lngs).toFixed(4)),
    sur: Number(Math.min(...lats).toFixed(4)),
    este: Number(Math.max(...lngs).toFixed(4)),
    norte: Number(Math.max(...lats).toFixed(4)),
  };
}

/** Convierte un nombre libre de región en un slug seguro para el parámetro `region`. */
export function toRegionSlug(name: string): string {
  return (
    name
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_|_$/g, "")
      .slice(0, 48) || "region_personalizada"
  );
}

export async function apiGet<T>(
  path: string,
  params: Record<string, string | number | boolean | undefined> = {},
  signal?: AbortSignal,
): Promise<T> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") {
      qs.set(k, String(v));
    }
  }
  const url = `${BACKEND_URL}${path}${qs.size ? `?${qs.toString()}` : ""}`;
  const res = await fetch(url, { method: "GET", signal });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError(res.status, body);
  }
  return body as T;
}

export async function apiPost<T>(
  path: string,
  payload: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError(res.status, body);
  }
  return body as T;
}

