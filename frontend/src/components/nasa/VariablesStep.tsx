"use client";

import { VariableId } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";
import { ALL_VARIABLES, VARIABLES } from "@/lib/catalog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ChoiceButton } from "@/components/ui/choice-button";
import { ArrowLeftIcon, ArrowRightIcon } from "@heroicons/react/24/outline";

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
        <Badge variant="secondary" className="shrink-0 tabular-nums">
          {selected.length} {t("variablesStep.selectedCount")}
        </Badge>
      </div>

      <div className="space-y-2">
        {ALL_VARIABLES.map((id) => {
          const info = VARIABLES[id];
          const on = selected.includes(id);
          return (
            <ChoiceButton key={id} selected={on} aria-pressed={on} onClick={() => onToggleVariable(id)}>
              <Checkbox checked={on} tabIndex={-1} className="pointer-events-none mt-0.5" aria-hidden />
              <span>
                <span className="block text-sm font-bold">
                  {info.name[language]} <span className="font-normal text-muted-foreground">· {info.product}</span>
                </span>
                <span className="mt-0.5 block text-xs leading-snug text-muted-foreground">{info.desc[language]}</span>
              </span>
            </ChoiceButton>
          );
        })}
      </div>

      <div className="flex gap-2 pt-1">
        <Button variant="outline" onClick={onBack}>
          <ArrowLeftIcon className="size-4" />
          {t("variablesStep.back")}
        </Button>
        <Button className="flex-1" disabled={selected.length === 0} onClick={onContinue}>
          {t("variablesStep.run")}
          <ArrowRightIcon className="size-4" />
        </Button>
      </div>
    </div>
  );
}
