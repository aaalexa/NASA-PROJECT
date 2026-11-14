"use client";

import { useEffect, useState } from "react";
import { AcademicCapIcon, BeakerIcon } from "@heroicons/react/24/outline";
import { useTranslation } from "@/context/LanguageContext";
import { classifyExperience } from "@/lib/intent";
import type { Experience } from "@/types/geo";

interface ExperienceModalProps {
  onChoose: (level: Experience) => void;
  registerVoice: (fn: ((text: string) => void) | null) => void;
  speak: (text: string) => void;
}

export function ExperienceModal({ onChoose, registerVoice, speak }: ExperienceModalProps) {
  const { t } = useTranslation();
  const [misheard, setMisheard] = useState(false);

  useEffect(() => {
    registerVoice((text: string) => {
      const level = classifyExperience(text);
      if (level) {
        setMisheard(false);
        onChoose(level);
      } else {
        setMisheard(true);
        speak(t("onboarding.notUnderstood"));
      }
    });
    return () => registerVoice(null);
  });

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="exp-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 px-4 pb-32 backdrop-blur-sm animate-in fade-in duration-300"
    >
      <div className="panel w-full max-w-xl p-6 sm:p-8 animate-in fade-in zoom-in-95 duration-300">
        <p className="eyebrow mb-3 flex items-center gap-2">
          <span className="rounded-full inline-block h-2 w-2 bg-brand-red" />
          {t("onboarding.eyebrow")}
        </p>
        <h1 id="exp-title" className="title text-2xl sm:text-3xl">
          {t("onboarding.title")}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">{t("onboarding.subtitle")}</p>

        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          <button type="button" className="choice" onClick={() => onChoose("novice")}>
            <AcademicCapIcon className="mb-4 h-6 w-6 text-primary" />
            <span className="block text-base font-bold">{t("onboarding.newTitle")}</span>
            <span className="mt-1 block text-sm text-muted-foreground">{t("onboarding.newDesc")}</span>
          </button>
          <button type="button" className="choice" onClick={() => onChoose("expert")}>
            <BeakerIcon className="mb-4 h-6 w-6 text-brand-red" />
            <span className="block text-base font-bold">{t("onboarding.expertTitle")}</span>
            <span className="mt-1 block text-sm text-muted-foreground">{t("onboarding.expertDesc")}</span>
          </button>
        </div>

        <p
          aria-live="polite"
          className={`mt-5 text-xs ${misheard ? "text-brand-red" : "text-muted-foreground"}`}
        >
          {misheard ? t("onboarding.notUnderstood") : t("onboarding.voiceHint")}
        </p>
      </div>
    </div>
  );
}
