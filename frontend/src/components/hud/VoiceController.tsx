"use client";

import { useEffect, useState } from "react";
import { MicrophoneIcon, StopIcon, ArrowPathIcon } from "@heroicons/react/24/solid";
import { useTranslation } from "@/context/LanguageContext";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface VoiceControllerProps {
  onTranscript: (text: string) => void;
  /** Called when recording begins, e.g. to silence the voice guide. */
  onBeforeListen?: () => void;
  /** Contextual hint shown above the button. */
  hint?: string;
  className?: string;
}

export function VoiceController({ onTranscript, onBeforeListen, hint, className }: VoiceControllerProps) {
  const { language, t } = useTranslation();
  const [heard, setHeard] = useState("");

  const { status, level, error, toggle, clearError } = useVoiceInput({
    locale: language,
    onTranscript: (text) => {
      setHeard(text);
      onTranscript(text);
    },
    onStart: () => {
      setHeard("");
      onBeforeListen?.();
    },
  });

  useEffect(() => {
    if (!heard) return;
    const id = setTimeout(() => setHeard(""), 6000);
    return () => clearTimeout(id);
  }, [heard]);

  const listening = status === "listening";
  const processing = status === "processing";
  const label = listening ? t("voice.listening") : processing ? t("voice.processing") : t("voice.speak");

  return (
    <div className={`fixed bottom-6 left-1/2 z-[60] flex -translate-x-1/2 flex-col items-center gap-2 select-none ${className ?? ""}`}>
      <div aria-live="polite" className="flex min-h-[26px] max-w-[88vw] flex-col items-center gap-1.5 text-center">
        {error ? (
          <Button variant="destructive" size="sm" className="h-auto max-w-full whitespace-normal px-4 py-1.5 text-xs" onClick={clearError}>
            {t(`voice.${error}`)}
          </Button>
        ) : heard ? (
          <Badge variant="secondary" className="h-auto max-w-full whitespace-normal px-3 py-1">
            <span className="text-muted-foreground">{t("voice.heard")}</span> “{heard}”
          </Badge>
        ) : hint && !listening && !processing ? (
          <span className="hidden text-xs text-muted-foreground sm:inline">{hint}</span>
        ) : null}
      </div>

      <div className="relative flex size-[72px] items-center justify-center">
        {listening && (
          <span
            aria-hidden
            className="absolute inset-0 rounded-full bg-brand-red"
            style={{
              transform: `scale(${1 + level * 0.9})`,
              opacity: 0.18 + level * 0.3,
              transition: "transform 80ms linear, opacity 80ms linear",
            }}
          />
        )}
        {listening && (
          <span aria-hidden className="absolute inset-0 rounded-full border border-brand-red" style={{ animation: "voice-ring 1.6s ease-out infinite" }} />
        )}
        <Button
          size="icon-lg"
          onClick={toggle}
          disabled={processing}
          aria-label={listening ? t("voice.stop") : t("voice.speak")}
          aria-pressed={listening}
          className={`relative ${listening ? "bg-brand-red text-white hover:bg-brand-red" : ""}`}
        >
          {processing ? <ArrowPathIcon className="size-6 animate-spin" /> : listening ? <StopIcon className="size-5" /> : <MicrophoneIcon className="size-6" />}
        </Button>
      </div>

      <span className="eyebrow">{label}</span>
    </div>
  );
}
