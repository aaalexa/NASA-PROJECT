"use client";

import { DateRange } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";
import { PERIODS } from "@/lib/catalog";
import { Button } from "@/components/ui/button";
import { ChoiceButton } from "@/components/ui/choice-button";
import { DatePicker } from "@/components/ui/date-picker";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { ArrowLeftIcon, ArrowRightIcon } from "@heroicons/react/24/outline";

interface PeriodStepProps {
  range: DateRange;
  onChangeRange: (range: DateRange) => void;
  onBack: () => void;
  onContinue: () => void;
}

export function PeriodStep({ range, onChangeRange, onBack, onContinue }: PeriodStepProps) {
  const { language, t } = useTranslation();

  return (
    <div className="space-y-5 animate-in fade-in duration-300">
      <div>
        <h2 className="title text-lg">{t("periodStep.title")}</h2>
        <p className="mt-1.5 text-sm text-muted-foreground">{t("periodStep.description")}</p>
      </div>

      <div className="space-y-2">
        <p className="eyebrow">{t("periodStep.presets")}</p>
        {PERIODS.map((p) => (
          <ChoiceButton
            key={p.id}
            selected={range.preset === p.id}
            className="flex-col gap-0.5"
            onClick={() => onChangeRange({ start: p.start, end: p.end, preset: p.id })}
          >
            <span className="text-sm font-bold">{p.label[language]}</span>
            <span className="text-xs text-muted-foreground">{p.desc[language]}</span>
          </ChoiceButton>
        ))}
      </div>

      <Separator />

      <div className="space-y-2">
        <p className="eyebrow">{t("periodStep.dates")}</p>
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">{t("periodStep.from")}</Label>
            <DatePicker
              value={range.start}
              language={language}
              label={t("periodStep.from")}
              max={range.end}
              onChange={(iso) => onChangeRange({ ...range, start: iso, preset: "custom" })}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">{t("periodStep.to")}</Label>
            <DatePicker
              value={range.end}
              language={language}
              label={t("periodStep.to")}
              min={range.start}
              onChange={(iso) => onChangeRange({ ...range, end: iso, preset: "custom" })}
            />
          </div>
        </div>
      </div>

      <div className="flex gap-2 pt-1">
        <Button variant="outline" onClick={onBack}>
          <ArrowLeftIcon className="size-4" />
          {t("periodStep.back")}
        </Button>
        <Button className="flex-1" onClick={onContinue}>
          {t("periodStep.next")}
          <ArrowRightIcon className="size-4" />
        </Button>
      </div>
    </div>
  );
}
