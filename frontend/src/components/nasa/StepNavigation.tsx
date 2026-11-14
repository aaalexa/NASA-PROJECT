"use client";

import { WorkflowStep } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";

interface StepNavigationProps {
  activeStep: WorkflowStep;
  onSelectStep: (step: WorkflowStep) => void;
  hasRegion: boolean;
  hasVariables: boolean;
  readOnly?: boolean;
}

const ORDER: WorkflowStep[] = ["region", "period", "variables", "results"];

export function StepNavigation({ activeStep, onSelectStep, hasRegion, hasVariables, readOnly }: StepNavigationProps) {
  const { t } = useTranslation();
  const activeIndex = ORDER.indexOf(activeStep);

  const steps = [
    { id: "region" as const, label: t("nav.step1"), enabled: true },
    { id: "period" as const, label: t("nav.step2"), enabled: hasRegion },
    { id: "variables" as const, label: t("nav.step3"), enabled: hasRegion },
    { id: "results" as const, label: t("nav.step4"), enabled: hasRegion && hasVariables },
  ];

  return (
    <nav aria-label="Workflow" className="panel flex items-center gap-1 p-1">
      {steps.map((step, index) => {
        const isActive = activeStep === step.id;
        const isPast = index < activeIndex;
        return (
          <button
            key={step.id}
            type="button"
            disabled={!step.enabled || readOnly}
            aria-current={isActive ? "step" : undefined}
            onClick={() => onSelectStep(step.id)}
            className={`flex h-8 items-center gap-2 rounded-full px-3 text-xs font-medium transition-colors disabled:cursor-default ${
              isActive
                ? "bg-foreground text-background"
                : step.enabled
                ? "cursor-pointer text-foreground hover:bg-muted"
                : "text-muted-foreground/50"
            }`}
          >
            <span className={`tabular-nums ${isActive ? "text-brand-red" : isPast ? "text-primary" : "text-muted-foreground"}`}>
              {String(index + 1).padStart(2, "0")}
            </span>
            <span className="hidden sm:inline">{step.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
