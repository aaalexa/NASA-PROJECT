"use client";

import { VariableId } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";
import { ALL_VARIABLES, VARIABLES } from "@/lib/catalog";
import { ArrowLeftIcon, ArrowRightIcon, CheckIcon } from "@heroicons/react/24/outline";

interface VariablesStepProps {
  selected: VariableId[];
  onToggleVariable: (id: VariableId) => void;
  onBack: () => void;
  onContinue: () => void;
}

export function VariablesStep({ selected, onToggleVariable, onBack, onContinue }: VariablesStepProps) {
  const { language, t } = useTranslation();

  return (
    <div className="space-y-5 animate-in fade-in duration-300">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="title text-lg">{t("variablesStep.title")}</h2>
          <p className="mt-1.5 text-sm text-muted-foreground">{t("variablesStep.description")}</p>
        </div>
        <span className="eyebrow shrink-0 pt-1 tabular-nums">
          {selected.length} {t("variablesStep.selectedCount")}
        </span>
      </div>

      <div className="space-y-2">
        {ALL_VARIABLES.map((id) => {
          const info = VARIABLES[id];
          const on = selected.includes(id);
          return (
            <button key={id} type="button" className="choice flex items-start gap-3" data-selected={on} aria-pressed={on} onClick={() => onToggleVariable(id)}>
              <span
                className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${
                  on ? "border-primary bg-primary text-white" : "border-border"
                }`}
              >
                {on && <CheckIcon className="h-3.5 w-3.5" />}
              </span>
              <span>
                <span className="block text-sm font-bold">
                  {info.name[language]} <span className="font-normal text-muted-foreground">· {info.product}</span>
                </span>
                <span className="mt-0.5 block text-xs leading-snug text-muted-foreground">{info.desc[language]}</span>
              </span>
            </button>
          );
        })}
      </div>

      <div className="flex gap-2 pt-1">
        <button type="button" className="btn btn-line" onClick={onBack}>
          <ArrowLeftIcon className="h-4 w-4" />
          {t("variablesStep.back")}
        </button>
        <button type="button" className="btn btn-primary flex-1" disabled={selected.length === 0} onClick={onContinue}>
          {t("variablesStep.run")}
          <ArrowRightIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
