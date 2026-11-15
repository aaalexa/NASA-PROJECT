import { NextResponse } from "next/server";
import { Type } from "@google/genai";
import { ai, generate } from "@/lib/gemini";
import { TOPICS } from "@/lib/catalog";
import type { TopicId } from "@/types/geo";

interface CatalogEntry {
  id: string;
  nombre: string;
  definicion?: string;
  pregunta?: string;
  dataset?: string;
  unidad?: string;
}

interface Ranked {
  id: string;
  reason: string;
}

const clip = (s: unknown, n: number) => String(s ?? "").slice(0, n);

/**
 * Ranks the backend's variables (sent by the client from GET /api/v1/catalogo) by how likely they
 * are to show a trend for the user's topic and region, with a plain-language reason each.
 */
export async function POST(req: Request) {
  try {
    const { topic, regionName, locale = "es", catalog } = (await req.json()) as {
      topic: TopicId;
      regionName: string;
      locale?: "es" | "en";
      catalog?: CatalogEntry[];
    };
    const lang = locale === "en" ? "en" : "es";
    const topicInfo = TOPICS.find((t) => t.id === topic) ?? TOPICS[0];
    const entries = (Array.isArray(catalog) ? catalog : []).filter((c) => c && typeof c.id === "string").slice(0, 40);
    const ids = entries.map((c) => c.id);

    if (!entries.length) {
      return NextResponse.json({ error: "catalog-required" }, { status: 400 });
    }

    if (ai && typeof regionName === "string" && regionName) {
      try {
        const list = entries
          .map((c) => `- ${c.id}: ${clip(c.nombre, 80)} (${clip(c.dataset, 80)}, ${clip(c.unidad, 20)}) — ${clip(c.definicion, 160)}`)
          .join("\n");
        const prompt = `You help beginners explore NASA Earth-science data.
The user wants to investigate: "${topicInfo.name.en}" in the region "${clip(regionName, 120)}".
Available variables (from the project's backend):
${list}

Rank ALL variables from most to least useful for detecting a long-term trend (data 2001-2024) for this topic in this region. Use the region's characteristics (climate, vegetation, season, known regional changes, e.g. a desert, rainforest, estuary, or city atmosphere) and what is known from recent climate literature.
For each give one plain sentence (max 25 words, no jargon) in ${lang === "en" ? "English" : "Spanish"} saying what it could reveal there. Do not claim causes; describe what to look for. Also give a one-sentence "summary".`;

        const response = await generate({
          contents: prompt,
          config: {
            responseMimeType: "application/json",
            responseSchema: {
              type: Type.OBJECT,
              properties: {
                summary: { type: Type.STRING },
                ranked: {
                  type: Type.ARRAY,
                  items: {
                    type: Type.OBJECT,
                    properties: {
                      id: { type: Type.STRING, enum: ids },
                      reason: { type: Type.STRING },
                    },
                    required: ["id", "reason"],
                  },
                },
              },
              required: ["summary", "ranked"],
            },
          },
        });

        const parsed = JSON.parse(response.text || "{}") as { summary: string; ranked: Ranked[] };
        const seen = new Set<string>();
        const ranked = (parsed.ranked ?? []).filter((r) => {
          if (!ids.includes(r.id) || seen.has(r.id)) return false;
          seen.add(r.id);
          return true;
        });
        if (ranked.length >= 2) {
          return NextResponse.json({ source: "gemini", summary: parsed.summary ?? "", ranked });
        }
      } catch (err) {
        console.warn("[api/guide] Gemini unavailable, using topic defaults:", err);
      }
    }

    // Deterministic fallback: the topic's preferred variables that the backend actually serves.
    const byId = new Map(entries.map((c) => [c.id, c]));
    const ranked: Ranked[] = topicInfo.variables
      .filter((id) => byId.has(id))
      .map((id) => ({ id, reason: byId.get(id)?.pregunta ?? byId.get(id)?.definicion ?? "" }));
    return NextResponse.json({ source: "local", summary: "", ranked });
  } catch (error) {
    console.error("[api/guide]", error);
    return NextResponse.json({ error: "guide-failed" }, { status: 500 });
  }
}
