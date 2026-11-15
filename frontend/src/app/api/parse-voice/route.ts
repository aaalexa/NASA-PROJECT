import { NextResponse } from "next/server";
import { Type } from "@google/genai";
import { ai, generate } from "@/lib/gemini";
import { backendRegions } from "@/lib/serverRegions";
import { matchRegion, payloadFromBackendRegion } from "@/lib/regionMatch";
import { bboxFromPoints, outlineFromBBox } from "@/lib/api";
import type { GeoPoint } from "@/types/geo";

const sideDeg = (p: GeoPoint, q: GeoPoint) =>
  Math.hypot(p.lat - q.lat, (p.lng - q.lng) * Math.cos(((p.lat + q.lat) / 2) * (Math.PI / 180)));

/** A usable study triangle: valid coordinates, not degenerate, not absurdly large or tiny. */
function validTriangle(v: unknown): v is GeoPoint[] {
  if (!Array.isArray(v) || v.length < 3) return false;
  const pts = v.slice(0, 3) as GeoPoint[];
  const ok = pts.every(
    (p) => typeof p?.lat === "number" && typeof p?.lng === "number" && Math.abs(p.lat) <= 90 && Math.abs(p.lng) <= 180
  );
  if (!ok) return false;
  const [a, b, c] = pts;
  const area = Math.abs((b.lng - a.lng) * (c.lat - a.lat) - (c.lng - a.lng) * (b.lat - a.lat)) / 2;
  const longest = Math.max(sideDeg(a, b), sideDeg(b, c), sideDeg(c, a));
  return area > 0.002 && longest > 0.15 && longest < 120;
}

async function locateWithGemini(prompt: string, lang: "es" | "en", retryNote = "") {
  const language = lang === "en" ? "English" : "Spanish";
  const response = await generate({
    contents: `Task: locate a place on Earth for a climate-trend study.
User text (may come from speech recognition, so tolerate typos and homophones): "${prompt}"

Rules:
- Identify the single most likely real place (country, region, basin, desert, lake, mountain range, city...). If the text is not a real place, set found=false.
- Give exactly 3 vertices (lat, lng in decimal degrees; south and west are negative) of a triangle that encloses the main LAND area of that place. The triangle should match the true extent of the place: a city about 0.3-0.6 degrees across, a country or large region its real size. Do not pad it with ocean when avoidable, and never make it a thin sliver.
- regionName: the official, short name in ${language}, with the country or continent after a comma when helpful.
- description: ONE plain sentence in ${language} (max 22 words) about why this place is interesting for rainfall, heat or soil-water trends. No causal claims.
- confidence: 0 to 1 for how sure you are about the place.${retryNote}`,
    config: {
      temperature: 0,
      responseMimeType: "application/json",
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          found: { type: Type.BOOLEAN },
          regionName: { type: Type.STRING },
          description: { type: Type.STRING },
          confidence: { type: Type.NUMBER },
          triangleVertices: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: { lat: { type: Type.NUMBER }, lng: { type: Type.NUMBER } },
              required: ["lat", "lng"],
            },
          },
        },
        required: ["found", "regionName", "description", "confidence", "triangleVertices"],
      },
    },
  });
  return JSON.parse(response.text || "{}");
}

export async function POST(req: Request) {
  try {
    const { prompt, locale = "es" } = await req.json();
    if (!prompt || typeof prompt !== "string") {
      return NextResponse.json({ error: "No prompt provided" }, { status: 400 });
    }
    const lang = locale === "en" ? "en" : "es";

    // Official backend regions answer instantly and exactly (and reuse the backend's warm cache).
    const official = matchRegion(prompt, await backendRegions());
    if (official) {
      const payload = payloadFromBackendRegion(official);
      return NextResponse.json({ ...payload, suggestedVariables: [], source: "backend" });
    }

    if (ai) {
      try {
        let parsed = await locateWithGemini(prompt, lang);
        if (parsed.found !== false && !validTriangle(parsed.triangleVertices)) {
          parsed = await locateWithGemini(
            prompt,
            lang,
            "\n- Your previous triangle was degenerate or the wrong size. Return a proper non-degenerate triangle covering the place."
          );
        }
        if (parsed.found === false || (typeof parsed.confidence === "number" && parsed.confidence < 0.35)) {
          return NextResponse.json({ error: "region-not-found" }, { status: 404 });
        }
        if (validTriangle(parsed.triangleVertices)) {
          const v = parsed.triangleVertices.slice(0, 3);
          // The backend analyses a bounding box, so that box (not the triangle) is what we show.
          const box = bboxFromPoints(v);
          const outline = outlineFromBBox([box.oeste, box.sur, box.este, box.norte]);
          return NextResponse.json({
            regionName: parsed.regionName,
            description: parsed.description,
            triangleVertices: v,
            outline,
            geoJsonPolygon: { type: "Polygon", coordinates: [[...outline.map((p) => [p.lng, p.lat]), [outline[0].lng, outline[0].lat]]] },
            source: "gemini",
          });
        }
      } catch (err) {
        console.warn("[api/parse-voice] Gemini unavailable:", err);
      }
    }

    return NextResponse.json({ error: "region-not-found" }, { status: 404 });
  } catch (error) {
    console.error("[api/parse-voice]", error);
    return NextResponse.json({ error: "parse-failed" }, { status: 500 });
  }
}
