"use client";

import { VariableId } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";
import { useBackend } from "@/context/BackendContext";
import { GROUP_LABELS } from "@/lib/catalog";
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
  const backend = useBackend();

  // Backend variables grouped by `grupo`, in the backend's own order.
  const groups = backend.analyzable.reduce<Record<string, typeof backend.analyzable>>((acc, v) => {
    (acc[v.grupo] ??= []).push(v);
    return acc;
  }, {});

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

      {backend.analyzable.length === 0 && <p className="text-sm text-brand-red">{t("backend.offlineShort")}</p>}

      {Object.entries(groups).map(([grupo, vars]) => (
        <div key={grupo} className="space-y-2">
          <p className="eyebrow">{GROUP_LABELS[grupo]?.[language] ?? grupo}</p>
          {vars.map((v) => {
            const on = selected.includes(v.id);
            return (
              <ChoiceButton key={v.id} selected={on} aria-pressed={on} onClick={() => onToggleVariable(v.id)}>
                <Checkbox checked={on} tabIndex={-1} className="pointer-events-none mt-0.5" aria-hidden />
                <span>
                  <span className="block text-sm font-bold">
                    {v.nombre_simple} <span className="font-normal text-muted-foreground">· {v.short_name ?? v.fuente}</span>
                  </span>
                  <span className="mt-0.5 block text-xs leading-snug text-muted-foreground">{v.definicion_simple}</span>
                </span>
              </ChoiceButton>
            );
          })}
        </div>
      ))}

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
