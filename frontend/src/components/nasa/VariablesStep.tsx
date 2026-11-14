"use client";

import { VariableId } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  AdjustmentsHorizontalIcon,
  CheckIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
  SparklesIcon,
} from "@heroicons/react/24/outline";

interface VariablesStepProps {
  selected: VariableId[];
  onToggleVariable: (id: VariableId) => void;
  onBack: () => void;
  onContinue: () => void;
}

export function VariablesStep({
  selected,
  onToggleVariable,
  onBack,
  onContinue,
}: VariablesStepProps) {
  const { t } = useTranslation();

  const variablesList: {
    id: VariableId;
    mission: string;
    title: string;
    description: string;
  }[] = [
    {
      id: "precipitation",
      mission: "GPM IMERG",
      title: t("variablesStep.varPrecip"),
      description: t("variablesStep.varPrecipDesc"),
    },
    {
      id: "temperature",
      mission: "MODIS LST",
      title: t("variablesStep.varTemp"),
      description: t("variablesStep.varTempDesc"),
    },
    {
      id: "vegetation",
      mission: "MODIS NDVI",
      title: t("variablesStep.varNdvi"),
      description: t("variablesStep.varNdviDesc"),
    },
    {
      id: "moisture",
      mission: "GLDAS SOILM",
      title: t("variablesStep.varMoisture"),
      description: t("variablesStep.varMoistureDesc"),
    },
  ];

  return (
    <div className="space-y-4 animate-in fade-in duration-300">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <AdjustmentsHorizontalIcon className="w-4 h-4 text-blue-500" />
            <h2 className="text-sm font-bold uppercase tracking-wider text-foreground font-mono">
              {t("variablesStep.title")}
            </h2>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {t("variablesStep.description")}
          </p>
        </div>
        <Badge
          variant="outline"
          className="bg-blue-500/10 text-blue-600 dark:text-blue-300 border-blue-500/30 text-[10px] font-mono shrink-0 py-1"
        >
          {selected.length} {t("variablesStep.selectedCount")}
        </Badge>
      </div>

      {/* Lista de Variables Satelitales */}
      <div className="space-y-2">
        {variablesList.map((item) => {
          const isSelected = selected.includes(item.id);

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onToggleVariable(item.id)}
              className={`w-full p-3 rounded-xl border text-left transition-all cursor-pointer flex items-start justify-between gap-3 ${
                isSelected
                  ? "bg-blue-100 dark:bg-blue-950/60 border-blue-500 text-foreground ring-1 ring-blue-500/50"
                  : "bg-card/80 border-border text-foreground hover:border-blue-500/40 hover:bg-muted/80"
              }`}
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-foreground">
                    {item.title}
                  </span>
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono uppercase">
                    {item.mission}
                  </span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-snug">
                  {item.description}
                </p>
              </div>

              <div
                className={`w-5 h-5 rounded-lg flex items-center justify-center shrink-0 transition-all ${
                  isSelected
                    ? "bg-blue-600 text-white shadow-md shadow-blue-600/40"
                    : "border border-border bg-background"
                }`}
              >
                {isSelected && <CheckIcon className="w-3.5 h-3.5" />}
              </div>
            </button>
          );
        })}
      </div>

      {/* Botones de Navegación del Flujo */}
      <div className="flex items-center gap-2 pt-2">
        <Button
          type="button"
          variant="outline"
          onClick={onBack}
          className="border-border text-foreground hover:bg-muted h-9 px-3 rounded-xl text-xs font-mono cursor-pointer"
        >
          <ArrowLeftIcon className="w-3.5 h-3.5 mr-1" />
          Atrás
        </Button>
        <Button
          type="button"
          disabled={selected.length === 0}
          onClick={onContinue}
          className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold h-9 rounded-xl text-xs cursor-pointer shadow-lg shadow-blue-600/30"
        >
          Ejecutar Análisis Orbital
          <ArrowRightIcon className="w-3.5 h-3.5 ml-1.5" />
        </Button>
      </div>
    </div>
  );
}
