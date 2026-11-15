"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowPathIcon, ChatBubbleLeftRightIcon, MicrophoneIcon, PaperAirplaneIcon, StopIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { useTranslation } from "@/context/LanguageContext";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import type { WorkflowStep } from "@/types/geo";

interface Message {
  role: "user" | "model";
  text: string;
  error?: boolean;
}

export interface MoodyContext {
  phase: string;
  step: WorkflowStep;
  region: string | null;
  period: string | null;
  variables: string[];
  demo: string | null;
  /** Digest of the real analysis results on screen, if any. */
  results?: string | null;
  catalog?: string | null;
  regions?: string | null;
}

const DEFAULT_QUESTIONS: Record<"es" | "en", string[]> = {
  es: [
    "¿Qué es Moody Trends?",
    "¿Cómo elijo una región?",
    "¿Qué variables puedo analizar?",
    "¿Qué significa «p ajustado»?",
    "¿Por qué comparar lluvia con temperatura?",
  ],
  en: [
    "What is Moody Trends?",
    "How do I choose a region?",
    "Which variables can I analyse?",
    "What does “adjusted p” mean?",
    "Why compare rainfall with temperature?",
  ],
};

const STEP_QUESTIONS: Record<"es" | "en", Record<WorkflowStep, string[]>> = {
  es: {
    region: ["¿Puedo decir el lugar con mi voz?", "¿Qué tan grande debe ser la región?"],
    period: ["¿Qué periodo me recomiendas?", "¿Por qué se necesitan tantos años?"],
    variables: ["¿Qué variables me recomiendas?", "¿Qué es la evapotranspiración?"],
    results: ["Explícame estos resultados", "¿Son datos reales?", "¿Esto prueba que el calor causó la sequía?"],
  },
  en: {
    region: ["Can I say the place with my voice?", "How big should the region be?"],
    period: ["Which period do you recommend?", "Why are so many years needed?"],
    variables: ["Which variables do you recommend?", "What is evapotranspiration?"],
    results: ["Explain these results to me", "Is this real data?", "Does this prove heat caused the drought?"],
  },
};

export function MoodyChat({ context }: { context: MoodyContext }) {
  const { language, t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // Voice: Gemini transcribes the recording and the text is sent as a question.
  const askRef = useRef<(text: string) => void>(() => undefined);
  const voice = useVoiceInput({ locale: language, onTranscript: (text) => askRef.current(text) });
  const listening = voice.status === "listening";
  const transcribing = voice.status === "processing";

  useEffect(() => {
    // Wait a tick so the new bubble and suggestion chips are laid out before scrolling.
    const id = setTimeout(() => endRef.current?.scrollIntoView({ block: "end" }), 60);
    return () => clearTimeout(id);
  }, [messages, loading, open]);

  const suggestions = messages.length === 0
    ? [...STEP_QUESTIONS[language][context.step].slice(0, 2), ...DEFAULT_QUESTIONS[language]].slice(0, 6)
    : STEP_QUESTIONS[language][context.step].slice(0, 2);

  async function ask(text: string) {
    const question = text.trim();
    if (!question || loading) return;
    const next: Message[] = [...messages.filter((m) => !m.error), { role: "user", text: question }];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: next, context, locale: language }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.reply) throw new Error(data.error || "chat-failed");
      setMessages([...next, { role: "model", text: data.reply }]);
    } catch (e) {
      const noKey = e instanceof Error && e.message === "no-key";
      setMessages([...next, { role: "model", text: noKey ? t("chat.noKey") : t("chat.error"), error: true }]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    askRef.current = (text: string) => void ask(text);
  });

  return (
    <div className="fixed bottom-6 right-4 z-[60]">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger
          render={
            <Button
              size="icon-lg"
              aria-label={open ? t("chat.close") : t("chat.open")}
              className="bg-brand-olive text-white shadow-lg hover:bg-brand-olive/85"
            />
          }
        >
          {open ? <XMarkIcon className="size-6" /> : <ChatBubbleLeftRightIcon className="size-6" />}
        </PopoverTrigger>

        <PopoverContent side="top" align="end" sideOffset={12} className="flex h-[min(560px,calc(100dvh-8rem))] w-[min(380px,calc(100vw-2rem))] flex-col gap-0 overflow-hidden rounded-3xl p-0">
          {/* Header */}
          <div className="flex items-center gap-3 px-4 py-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-brand-blue text-sm font-bold text-[var(--deep-space-blue)]">M</span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold leading-tight">Moody</p>
              <p className="truncate text-xs text-muted-foreground">{t("chat.subtitle")}</p>
            </div>
            <Badge variant="secondary">IA</Badge>
            {messages.length > 0 && (
              <Button variant="ghost" size="icon-sm" onClick={() => setMessages([])} aria-label={t("chat.reset")} title={t("chat.reset")}>
                <ArrowPathIcon className="size-4" />
              </Button>
            )}
          </div>
          <Separator />

          {/* Conversation */}
          <ScrollArea className="min-h-0 flex-1 [&_[data-slot=scroll-area-viewport]]:max-h-full">
            <div className="space-y-3 p-4">
              {messages.length === 0 && (
                <div className="rounded-3xl rounded-tl-lg bg-muted px-4 py-3 text-sm leading-relaxed">{t("chat.greeting")}</div>
              )}
              {messages.map((m, i) => (
                <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[85%] whitespace-pre-wrap rounded-3xl px-4 py-2.5 text-sm leading-relaxed ${
                      m.role === "user"
                        ? "rounded-br-lg bg-primary text-primary-foreground"
                        : m.error
                        ? "rounded-tl-lg bg-muted text-brand-red"
                        : "rounded-tl-lg bg-muted"
                    }`}
                  >
                    {m.text}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start" role="status" aria-label={t("chat.thinking")}>
                  <div className="flex gap-1 rounded-3xl rounded-tl-lg bg-muted px-4 py-3">
                    {[0, 1, 2].map((d) => (
                      <span key={d} className="size-1.5 animate-bounce rounded-full bg-brand-blue" style={{ animationDelay: `${d * 140}ms` }} />
                    ))}
                  </div>
                </div>
              )}

              {!loading && (
                <div className="flex flex-wrap gap-2 pt-1">
                  {suggestions.map((q) => (
                    <Button key={q} variant="outline" size="sm" className="h-auto whitespace-normal px-3 py-1.5 text-left text-xs font-normal" onClick={() => ask(q)}>
                      {q}
                    </Button>
                  ))}
                </div>
              )}
              <div ref={endRef} />
            </div>
          </ScrollArea>

          {/* Composer */}
          <Separator />
          {voice.error && (
            <button type="button" onClick={voice.clearError} className="px-4 pt-2 text-left text-xs text-brand-red">
              {t(`voice.${voice.error}`)}
            </button>
          )}
          <form
            className="flex gap-2 p-3"
            onSubmit={(e) => {
              e.preventDefault();
              void ask(input);
            }}
          >
            <Button
              type="button"
              size="icon"
              variant={listening ? "default" : "outline"}
              className={`size-10 shrink-0 ${listening ? "bg-brand-red text-white hover:bg-brand-lava" : ""}`}
              onClick={voice.toggle}
              disabled={loading || transcribing}
              aria-pressed={listening}
              aria-label={listening ? t("voice.stop") : t("voice.speak")}
              title={listening ? t("voice.stop") : t("voice.speak")}
              style={listening ? { boxShadow: `0 0 0 ${2 + voice.level * 8}px color-mix(in srgb, var(--red) 30%, transparent)` } : undefined}
            >
              {transcribing ? <ArrowPathIcon className="size-4 animate-spin" /> : listening ? <StopIcon className="size-4" /> : <MicrophoneIcon className="size-4" />}
            </Button>
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={listening ? t("voice.listening") : transcribing ? t("voice.processing") : t("chat.placeholder")}
              aria-label={t("chat.placeholder")}
              maxLength={500}
              disabled={listening || transcribing}
            />
            <Button type="submit" size="icon" className="size-10 shrink-0" disabled={loading || !input.trim()} aria-label={t("chat.send")}>
              <PaperAirplaneIcon className="size-4" />
            </Button>
          </form>
        </PopoverContent>
      </Popover>
    </div>
  );
}
