import type { Experience, TopicId } from "@/types/geo";

function norm(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

function hasAny(text: string, words: string[]): boolean {
  return words.some((w) => text.includes(w));
}

/** "Soy nuevo" / "I have experience" -> experience level. Negations are checked first. */
export function classifyExperience(raw: string): Experience | null {
  const t = norm(raw);
  if (
    hasAny(t, [
      "sin experiencia", "no tengo experiencia", "nuevo", "nueva", "novato", "principiante",
      "primera vez", "empezando", "no se nada", "no se mucho", "desde cero",
      "no experience", "beginner", "novice", "first time", "i'm new", "im new", "new to", " new", "never used", "from scratch",
    ]) ||
    t.trim() === "new"
  ) {
    return "novice";
  }
  if (
    hasAny(t, [
      "experiencia", "experto", "avanzado", "un poco", "algo se", "ya se", "ya conozco", "ya uso", "conozco", "he trabajado",
      "experienced", "expert", "advanced", "i know", "familiar", "a bit", "some", "worked with", "already",
    ])
  ) {
    return "expert";
  }
  return null;
}

export function classifyTopic(raw: string): TopicId | null {
  const t = norm(raw);
  if (hasAny(t, ["lluvia", "sequia", "seco", "precip", "llueve", "inund", "rain", "drought", "dry", "flood", "water"])) return "rain";
  if (hasAny(t, ["calor", "temperatura", "caliente", "calent", "heat", "temperature", "warm", "hot"])) return "heat";
  if (hasAny(t, ["vegetaci", "cultivo", "bosque", "selva", "planta", "verde", "cosecha", "crop", "forest", "plant", "green", "vegetation", "farm"])) return "vegetation";
  if (hasAny(t, ["suelo", "humedad", "tierra", "soil", "moisture", "ground"])) return "soil";
  return null;
}

export function classifyPeriod(raw: string): "5y" | "10y" | "archive" | null {
  const t = norm(raw);
  if (hasAny(t, ["histor", "todo", "largo", "completo", "archivo", "2001", "veinticuatro", "24", "all", "long", "full", "archive", "record"])) return "archive";
  if (hasAny(t, ["diez", "10", "ten"])) return "10y";
  if (hasAny(t, ["cinco", "5", "five", "five years"])) return "5y";
  return null;
}
