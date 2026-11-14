"use client";

import { WorkflowStep } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";
import {
  MapPinIcon,
  CalendarDaysIcon,
  AdjustmentsHorizontalIcon,
  ChartBarSquareIcon,
  CheckIcon,
} from "@heroicons/react/24/outline";

interface StepNavigationProps {
  activeStep: WorkflowStep;
  onSelectStep: (step: WorkflowStep) => void;
  hasRegion: boolean;
  hasVariables: boolean;
}

export function StepNavigation({
  activeStep,
  onSelectStep,
  hasRegion,
  hasVariables,
}: StepNavigationProps) {
  const { t } = useTranslation();

  const steps: { id: WorkflowStep; label: string; icon: any; enabled: boolean }[] = [
    {
      id: "region",
      label: t("nav.step1"),
      icon: MapPinIcon,
      enabled: true,
    },
    {
      id: "period",
      label: t("nav.step2"),
      icon: CalendarDaysIcon,
      enabled: hasRegion,
    },
    {
      id: "variables",
      label: t("nav.step3"),
      icon: AdjustmentsHorizontalIcon,
      enabled: hasRegion,
    },
    {
      id: "results",
      label: t("nav.step4"),
      icon: ChartBarSquareIcon,
      enabled: hasRegion && hasVariables,
    },
  ];

  return (
    <nav className="flex items-center gap-1.5 p-1 rounded-2xl bg-card/90 dark:bg-black/90 border border-border backdrop-blur-md shadow-2xl select-none transition-colors">
      {steps.map((step, index) => {
        const Icon = step.icon;
        const isActive = activeStep === step.id;
        const isPast =
          (step.id === "region" && hasRegion && activeStep !== "region") ||
          (step.id === "period" && activeStep !== "region" && activeStep !== "period") ||
          (step.id === "variables" && activeStep === "results");

        return (
          <button
            key={step.id}
            type="button"
            disabled={!step.enabled}
            onClick={() => onSelectStep(step.id)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-mono transition-all ${
              isActive
                ? "bg-blue-600 text-white font-semibold shadow-lg shadow-blue-600/30 ring-1 ring-blue-400/40"
                : isPast
                ? "text-foreground hover:bg-muted cursor-pointer"
                : step.enabled
                ? "text-muted-foreground hover:text-foreground hover:bg-muted/60 cursor-pointer"
                : "text-muted-foreground/40 cursor-not-allowed opacity-50"
            }`}
          >
            <span
              className={`flex items-center justify-center w-5 h-5 rounded-lg text-[10px] font-bold ${
                isActive
                  ? "bg-black/30 text-white"
                  : isPast
                  ? "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-400 border border-blue-500/30"
                  : "bg-muted text-muted-foreground border border-border"
              }`}
            >
              {isPast ? <CheckIcon className="w-3 h-3 text-blue-600 dark:text-blue-400" /> : `0${index + 1}`}
            </span>
            <span className="hidden sm:inline uppercase tracking-wider">{step.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
