import { NextResponse } from "next/server";
import { ai, generate } from "@/lib/gemini";

const MAX_AUDIO_CHARS = 4_000_000; // ~3 MB of base64: far more than a 15 s voice command

export async function POST(req: Request) {
  if (!ai) {
    return NextResponse.json({ error: "GEMINI_API_KEY is not configured" }, { status: 503 });
  }

  try {
    const { audio, mimeType = "audio/wav", locale = "es" } = await req.json();
    if (typeof audio !== "string" || !audio || audio.length > MAX_AUDIO_CHARS) {
      return NextResponse.json({ error: "Invalid audio payload" }, { status: 400 });
    }

    const language = locale === "en" ? "English" : "Spanish";
    const response = await generate({
      contents: [
        { inlineData: { mimeType, data: audio } },
        {
          text: `Transcribe this short voice command exactly as spoken. The speaker uses ${language}, and may mention geographic places or Earth-science terms. Reply with the transcript only, no quotes or commentary. Never invent words: tones, noise, music or unintelligible sound are not speech. If there is no intelligible speech, reply with an empty string.`,
        },
      ],
      config: { temperature: 0 },
    });

    return NextResponse.json({ transcript: (response.text ?? "").trim() });
  } catch (error) {
    console.error("[api/transcribe]", error);
    return NextResponse.json({ error: "Transcription failed" }, { status: 500 });
  }
}
