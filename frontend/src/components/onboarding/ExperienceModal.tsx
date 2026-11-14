"use client";

import { useEffect, useState } from "react";
import { AcademicCapIcon, BeakerIcon } from "@heroicons/react/24/outline";
import { useTranslation } from "@/context/LanguageContext";
import { classifyExperience } from "@/lib/intent";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ChoiceButton } from "@/components/ui/choice-button";
import { Badge } from "@/components/ui/badge";
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

  // The dialog is non-modal so the floating microphone stays usable; it cannot be dismissed.
  return (
    <Dialog open modal={false}>
      <DialogContent showCloseButton={false} className="top-[44%] gap-6 p-8 sm:max-w-xl">
        <DialogHeader className="gap-3">
          <Badge variant="secondary" className="w-fit">
            {t("onboarding.eyebrow")}
          </Badge>
          <DialogTitle className="title text-3xl">{t("onboarding.title")}</DialogTitle>
          <DialogDescription className="text-sm">{t("onboarding.subtitle")}</DialogDescription>
        </DialogHeader>

        <div className="grid gap-3 sm:grid-cols-2">
          <ChoiceButton className="flex-col gap-3 p-5" onClick={() => onChoose("novice")}>
            <AcademicCapIcon className="size-6 text-brand-blue" />
            <span>
              <span className="block text-base font-bold">{t("onboarding.newTitle")}</span>
              <span className="mt-1 block text-sm text-muted-foreground">{t("onboarding.newDesc")}</span>
            </span>
          </ChoiceButton>
          <ChoiceButton className="flex-col gap-3 p-5" onClick={() => onChoose("expert")}>
            <BeakerIcon className="size-6 text-brand-red" />
            <span>
              <span className="block text-base font-bold">{t("onboarding.expertTitle")}</span>
              <span className="mt-1 block text-sm text-muted-foreground">{t("onboarding.expertDesc")}</span>
            </span>
          </ChoiceButton>
        </div>

        <p aria-live="polite" className={`text-xs ${misheard ? "text-brand-red" : "text-muted-foreground"}`}>
          {misheard ? t("onboarding.notUnderstood") : t("onboarding.voiceHint")}
        </p>
      </DialogContent>
    </Dialog>
  );
}
