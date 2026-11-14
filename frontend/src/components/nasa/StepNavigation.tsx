"use client";

import { WorkflowStep } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

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
    <Card size="sm" className="flex-row gap-1 rounded-full p-1" aria-label="Workflow" role="navigation">
      {steps.map((step, index) => {
        const isActive = activeStep === step.id;
        const isPast = index < activeIndex;
        return (
          <Button
            key={step.id}
            variant={isActive ? "default" : "ghost"}
            size="sm"
            disabled={!step.enabled || readOnly}
            aria-current={isActive ? "step" : undefined}
            onClick={() => onSelectStep(step.id)}
            className="h-8 gap-2 px-3 text-xs disabled:opacity-100 disabled:text-muted-foreground/60"
          >
            <span className={`tabular-nums ${isActive ? "opacity-70" : isPast ? "text-brand-blue" : ""}`}>
              {String(index + 1).padStart(2, "0")}
            </span>
            <span className="hidden sm:inline">{step.label}</span>
          </Button>
        );
      })}
    </Card>
  );
}
