import { NextResponse } from "next/server";
import { Type } from "@google/genai";
import { ai, generate } from "@/lib/gemini";
import { ALL_VARIABLES, TOPICS, VARIABLES } from "@/lib/catalog";
import type { TopicId, VariableId } from "@/types/geo";

interface Ranked {
  id: VariableId;
  reason: string;
}

/**
 * Given the user's answers (topic + region), ranks the catalog variables by how likely they are
 * to show a trend there, with a one-sentence plain-language reason each.
 */
export async function POST(req: Request) {
  try {
    const { topic, regionName, locale = "es" } = (await req.json()) as {
      topic: TopicId;
      regionName: string;
      locale?: "es" | "en";
    };
    const lang = locale === "en" ? "en" : "es";
    const topicInfo = TOPICS.find((t) => t.id === topic) ?? TOPICS[0];

    if (ai && typeof regionName === "string" && regionName) {
      try {
        const catalog = ALL_VARIABLES.map(
          (id) => `- ${id}: ${VARIABLES[id].name.en} (${VARIABLES[id].product}) — ${VARIABLES[id].desc.en}`
        ).join("\n");
        const prompt = `You help beginners explore NASA Earth-science data.
The user wants to investigate: "${topicInfo.name.en}" in the region "${regionName}".
Available variables:
${catalog}

Rank ALL variables from most to least useful for detecting a long-term trend (monthly data, 2001-2024) for this topic in this region. Use the region's characteristics (climate, vegetation, season, known regional changes, e.g. a desert, rainforest, estuary, or city atmosphere) and what is known from recent climate literature.
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
                      id: { type: Type.STRING, enum: ALL_VARIABLES },
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
          if (!ALL_VARIABLES.includes(r.id) || seen.has(r.id)) return false;
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

    // Deterministic fallback from the topic table.
    const ranked: Ranked[] = topicInfo.variables.map((id) => ({ id, reason: VARIABLES[id].question[lang] }));
    return NextResponse.json({ source: "local", summary: "", ranked });
  } catch (error) {
    console.error("[api/guide]", error);
    return NextResponse.json({ error: "guide-failed" }, { status: 500 });
  }
}
