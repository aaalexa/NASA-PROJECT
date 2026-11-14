"use client";

import { DateRange } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";
import { PERIODS } from "@/lib/catalog";
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
          <button
            key={p.id}
            type="button"
            className="choice"
            data-selected={range.preset === p.id}
            onClick={() => onChangeRange({ start: p.start, end: p.end, preset: p.id })}
          >
            <span className="block text-sm font-bold">{p.label[language]}</span>
            <span className="mt-0.5 block text-xs text-muted-foreground">{p.desc[language]}</span>
          </button>
        ))}
      </div>

      <div className="space-y-2">
        <p className="eyebrow">{t("periodStep.dates")}</p>
        <div className="grid grid-cols-2 gap-2">
          <label className="block text-xs text-muted-foreground">
            {t("periodStep.from")}
            <input
              type="date"
              className="field mt-1"
              value={range.start}
              onChange={(e) => onChangeRange({ ...range, start: e.target.value, preset: "custom" })}
            />
          </label>
          <label className="block text-xs text-muted-foreground">
            {t("periodStep.to")}
            <input
              type="date"
              className="field mt-1"
              value={range.end}
              onChange={(e) => onChangeRange({ ...range, end: e.target.value, preset: "custom" })}
            />
          </label>
        </div>
      </div>

      <div className="flex gap-2 pt-1">
        <button type="button" className="btn btn-line" onClick={onBack}>
          <ArrowLeftIcon className="h-4 w-4" />
          {t("periodStep.back")}
        </button>
        <button type="button" className="btn btn-primary flex-1" onClick={onContinue}>
          {t("periodStep.next")}
          <ArrowRightIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
