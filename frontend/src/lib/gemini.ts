import { GoogleGenAI, type GenerateContentParameters, type GenerateContentResponse } from "@google/genai";

const apiKey = process.env.GEMINI_API_KEY || "";

/** Shared Google GenAI client (server only). Null when no key is configured. */
export const ai = apiKey ? new GoogleGenAI({ apiKey }) : null;

/**
 * Models are tried in order. Availability varies per key and moment (older versions get retired,
 * newer ones hit demand/quota limits), so the chain falls through on 404/429/503.
 * Override the first choice with GEMINI_MODEL in .env.local.
 */
export const GEMINI_MODELS = [
  ...(process.env.GEMINI_MODEL ? [process.env.GEMINI_MODEL] : []),
  "gemini-3.1-flash-lite",
  "gemini-3.5-flash-lite",
  "gemini-3.8-flash",
  "gemini-3.7-flash",
  "gemini-3.5-flash",
];

const ATTEMPT_TIMEOUT_MS = 12_000;

function isTimeout(err: unknown): boolean {
  const e = err as { name?: string; message?: string };
  return e?.name === "AbortError" || /timed? ?out|abort/i.test(e?.message ?? "");
}

function isTransient(err: unknown): boolean {
  const status = (err as { status?: number })?.status;
  return status === 503 || status === 429 || status === 500;
}

/** generateContent that moves to the next model when one is overloaded (503/429) or retired (404). */
export async function generate(
  params: Omit<GenerateContentParameters, "model">,
  models: string[] = GEMINI_MODELS
): Promise<GenerateContentResponse> {
  if (!ai) throw new Error("GEMINI_API_KEY is not configured");
  let lastError: unknown;
  for (const model of models) {
    try {
      return await ai.models.generateContent({
        ...params,
        model,
        config: { ...params.config, httpOptions: { timeout: ATTEMPT_TIMEOUT_MS } },
      });
    } catch (err) {
      lastError = err;
      const status = (err as { status?: number })?.status;
      if (!isTransient(err) && status !== 404 && !isTimeout(err)) throw err;
    }
  }
  throw lastError;
}
