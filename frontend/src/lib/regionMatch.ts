import type { BackendRegion } from "@/lib/api";
import type { GeoPoint, RegionAnalysisPayload } from "@/types/geo";
import { outlineFromBBox } from "@/lib/api";

const norm = (s: string) =>
  s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();

const STOP = new Set(["del", "los", "las", "una", "uno", "the", "and", "cuenca", "region", "zona", "para", "con"]);

function words(s: string) {
  return norm(s)
    .split(/[^a-z0-9]+/)
    .filter(Boolean);
}

/**
 * Matches free text ("ama", "noreste mexico", "sahel") against the backend's regions.
 * Every meaningful word the user typed must be the start of a word of the region's name,
 * id or country. The best (shortest) match wins. No match -> null (ask Gemini instead).
 */
export function matchRegion(text: string, regions: BackendRegion[]): BackendRegion | null {
  const tokens = words(text).filter((w) => w.length >= 3 && !STOP.has(w));
  if (!tokens.length) return null;
  let best: { region: BackendRegion; score: number } | null = null;
  for (const r of regions) {
    const hay = [...words(r.nombre), ...words(r.id), ...words(r.pais ?? "")];
    if (!tokens.every((t) => hay.some((h) => h.startsWith(t)))) continue;
    // exact id/name hits first, then shorter names (more specific)
    const exact = norm(r.nombre) === norm(text) || r.id === norm(text).replace(/\s+/g, "_") ? 100 : 0;
    const score = exact - r.nombre.length;
    if (!best || score > best.score) best = { region: r, score };
  }
  return best?.region ?? null;
}

/** Payload for an official backend region: the globe draws its bbox and the API gets the id. */
export function payloadFromBackendRegion(r: BackendRegion): RegionAnalysisPayload {
  const outline = outlineFromBBox(r.bbox);
  const [oeste, sur, este, norte] = r.bbox;
  const mid: GeoPoint = { lat: norte, lng: (oeste + este) / 2 };
  const tri: [GeoPoint, GeoPoint, GeoPoint] = [outline[0], outline[1], mid];
  return {
    regionName: r.nombre,
    description: r.descripcion ?? r.pais ?? r.zona,
    triangleVertices: tri,
    outline,
    geoJsonPolygon: {
      type: "Polygon",
      coordinates: [[[oeste, sur], [este, sur], [este, norte], [oeste, norte], [oeste, sur]]],
    },
    backendId: r.id,
  };
}
