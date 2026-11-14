import { NextResponse } from "next/server";
import { Type } from "@google/genai";
import { ai, generate } from "@/lib/gemini";
import { findMatchingPredefinedRegion } from "@/components/nasa/PredefinedRegions";
import type { GeoPoint } from "@/types/geo";

function toPolygon(v: GeoPoint[]) {
  return {
    type: "Polygon" as const,
    coordinates: [[
      [v[0].lng, v[0].lat],
      [v[1].lng, v[1].lat],
      [v[2].lng, v[2].lat],
      [v[0].lng, v[0].lat],
    ]],
  };
}

function validTriangle(v: unknown): v is GeoPoint[] {
  return (
    Array.isArray(v) &&
    v.length >= 3 &&
    v.slice(0, 3).every(
      (p) =>
        typeof p?.lat === "number" &&
        typeof p?.lng === "number" &&
        Math.abs(p.lat) <= 90 &&
        Math.abs(p.lng) <= 180
    )
  );
}

export async function POST(req: Request) {
  try {
    const { prompt, locale = "es" } = await req.json();
    if (!prompt || typeof prompt !== "string") {
      return NextResponse.json({ error: "No prompt provided" }, { status: 400 });
    }
    const lang = locale === "en" ? "en" : "es";

    if (ai) {
      try {
        const instruction =
          lang === "en"
            ? `The user wants to investigate environmental change in a place on Earth. User input: "${prompt}".
1. Identify the geographic region mentioned. If no real place is mentioned, set found=false.
2. Give exactly 3 [lat, lng] points forming a balanced triangle that covers the LAND area of that region (lat -90..90, lng -180..180).
3. Name the region in English and describe in one plain sentence why it is interesting for studying rainfall, heat or soil water.`
            : `El usuario quiere investigar cambios ambientales en un lugar de la Tierra. Entrada: "${prompt}".
1. Identifica la región geográfica mencionada. Si no menciona un lugar real, found=false.
2. Da exactamente 3 puntos [lat, lng] que formen un triángulo equilibrado que cubra el área TERRESTRE de esa región (lat -90..90, lng -180..180).
3. Nombra la región en español y describe en una frase simple por qué es interesante para estudiar lluvia, calor o agua del suelo.`;

        const response = await generate({
          contents: instruction,
          config: {
            responseMimeType: "application/json",
            responseSchema: {
              type: Type.OBJECT,
              properties: {
                found: { type: Type.BOOLEAN },
                regionName: { type: Type.STRING },
                description: { type: Type.STRING },
                triangleVertices: {
                  type: Type.ARRAY,
                  items: {
                    type: Type.OBJECT,
                    properties: { lat: { type: Type.NUMBER }, lng: { type: Type.NUMBER } },
                    required: ["lat", "lng"],
                  },
                },
              },
              required: ["found", "regionName", "description", "triangleVertices"],
            },
          },
        });

        const parsed = JSON.parse(response.text || "{}");
        if (parsed.found === false) {
          return NextResponse.json({ error: "region-not-found" }, { status: 404 });
        }
        if (validTriangle(parsed.triangleVertices)) {
          const v = parsed.triangleVertices.slice(0, 3);
          return NextResponse.json({
            regionName: parsed.regionName,
            description: parsed.description,
            triangleVertices: v,
            geoJsonPolygon: toPolygon(v),
            suggestedVariables: [],
          });
        }
      } catch (err) {
        console.warn("[api/parse-voice] Gemini unavailable, using local regions:", err);
      }
    }

    // Local fallback: only answers for known regions instead of silently guessing one.
    const preset = findMatchingPredefinedRegion(prompt);
    if (!preset) {
      return NextResponse.json({ error: "region-not-found" }, { status: 404 });
    }
    return NextResponse.json({
      regionName: preset.name[lang],
      description: preset.area[lang],
      triangleVertices: preset.triangle,
      geoJsonPolygon: toPolygon(preset.triangle),
      suggestedVariables: [],
    });
  } catch (error) {
    console.error("[api/parse-voice]", error);
    return NextResponse.json({ error: "parse-failed" }, { status: 500 });
  }
}
