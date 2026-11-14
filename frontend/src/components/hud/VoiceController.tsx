"use client";

import { useEffect, useState } from "react";
import { MicrophoneIcon, StopIcon, ArrowPathIcon } from "@heroicons/react/24/solid";
import { useTranslation } from "@/context/LanguageContext";
import { useVoiceInput } from "@/hooks/useVoiceInput";

interface VoiceControllerProps {
  onTranscript: (text: string) => void;
  /** Called when recording begins, e.g. to silence the voice guide. */
  onBeforeListen?: () => void;
  /** Contextual hint shown above the button ("Say: I'm new or I have experience"). */
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

  // The "heard" caption fades after a few seconds.
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
      <div aria-live="polite" className="flex min-h-[22px] max-w-[88vw] flex-col items-center gap-1.5 text-center">
        {error ? (
          <button
            type="button"
            onClick={clearError}
            className="panel px-3 py-1.5 text-xs text-brand-red"
            title="OK"
          >
            {t(`voice.${error}`)}
          </button>
        ) : heard ? (
          <span className="panel px-3 py-1.5 text-xs text-foreground">
            <span className="eyebrow mr-2">{t("voice.heard")}</span>“{heard}”
          </span>
        ) : hint && !listening && !processing ? (
          <span className="text-xs text-muted-foreground">{hint}</span>
        ) : null}
      </div>

      <div className="relative flex h-16 w-16 items-center justify-center">
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
          <span
            aria-hidden
            className="absolute inset-0 rounded-full border border-brand-red"
            style={{ animation: "voice-ring 1.6s ease-out infinite" }}
          />
        )}
        <button
          type="button"
          onClick={toggle}
          disabled={processing}
          aria-label={listening ? t("voice.stop") : t("voice.speak")}
          aria-pressed={listening}
          className={`relative flex h-14 w-14 cursor-pointer items-center justify-center rounded-full text-white transition-colors disabled:cursor-wait ${
            listening ? "bg-brand-red" : "bg-primary hover:brightness-110"
          }`}
        >
          {processing ? (
            <ArrowPathIcon className="h-6 w-6 animate-spin" />
          ) : listening ? (
            <StopIcon className="h-5 w-5" />
          ) : (
            <MicrophoneIcon className="h-6 w-6" />
          )}
        </button>
      </div>

      <span className="eyebrow">{label}</span>
    </div>
  );
}
