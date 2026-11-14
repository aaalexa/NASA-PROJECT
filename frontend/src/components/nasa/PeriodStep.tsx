"use client";

import { DateRange } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";
import { Button } from "@/components/ui/button";
import {
  CalendarDaysIcon,
  InformationCircleIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
  ClockIcon,
} from "@heroicons/react/24/outline";

interface PeriodStepProps {
  range: DateRange;
  onChangeRange: (range: DateRange) => void;
  onBack: () => void;
  onContinue: () => void;
}

export function PeriodStep({
  range,
  onChangeRange,
  onBack,
  onContinue,
}: PeriodStepProps) {
  const { t } = useTranslation();

  const presets = [
    {
      id: "5y",
      label: t("periodStep.preset5"),
      start: "2019-01-01",
      end: "2024-12-31",
      desc: "2019 - 2024",
    },
    {
      id: "10y",
      label: t("periodStep.preset10"),
      start: "2014-01-01",
      end: "2024-12-31",
      desc: "2014 - 2024",
    },
    {
      id: "archive",
      label: t("periodStep.presetArchive"),
      start: "2001-01-01",
      end: "2024-12-31",
      desc: "2001 - 2024",
    },
  ];

  return (
    <div className="space-y-4 animate-in fade-in duration-300">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <CalendarDaysIcon className="w-4 h-4 text-blue-500" />
          <h2 className="text-sm font-bold uppercase tracking-wider text-foreground font-mono">
            {t("periodStep.title")}
          </h2>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">
          {t("periodStep.description")}
        </p>
      </div>

      {/* Presets de Ventana Temporal */}
      <div className="space-y-2">
        <label className="text-[11px] font-mono text-muted-foreground uppercase tracking-wider block">
          Intervalos Predefinidos
        </label>
        <div className="grid grid-cols-1 gap-2">
          {presets.map((preset) => {
            const isSelected =
              range.preset === preset.id ||
              (range.start === preset.start && range.end === preset.end);

            return (
              <button
                key={preset.id}
                type="button"
                onClick={() =>
                  onChangeRange({
                    start: preset.start,
                    end: preset.end,
                    preset: preset.id,
                  })
                }
                className={`flex items-center justify-between p-3 rounded-xl border text-left transition-all cursor-pointer ${
                  isSelected
                    ? "bg-blue-100 dark:bg-blue-950/60 border-blue-500 text-foreground ring-1 ring-blue-500/50"
                    : "bg-card/80 border-border text-foreground hover:border-blue-500/40 hover:bg-muted/80"
                }`}
              >
                <div>
                  <div className="text-xs font-semibold">{preset.label}</div>
                  <div className="text-[10px] text-muted-foreground font-mono mt-0.5">
                    {preset.desc}
                  </div>
                </div>
                {isSelected && (
                  <span className="flex h-2 w-2 rounded-full bg-blue-600 ring-4 ring-blue-500/30" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Rango Manual Personalizado */}
      <div className="p-3 rounded-xl bg-card/60 border border-border space-y-2">
        <div className="flex items-center gap-1.5 text-[11px] font-mono text-muted-foreground uppercase">
          <ClockIcon className="w-3.5 h-3.5 text-blue-500" />
          <span>Fechas de Observación</span>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <label className="text-[10px] text-muted-foreground font-mono block mb-1">
              INICIO
            </label>
            <input
              type="date"
              value={range.start}
              onChange={(e) =>
                onChangeRange({ ...range, start: e.target.value, preset: "custom" })
              }
              className="w-full bg-background border border-border rounded-lg px-2 py-1 text-foreground font-mono text-xs focus:ring-1 focus:ring-blue-500 outline-none"
            />
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground font-mono block mb-1">
              FIN
            </label>
            <input
              type="date"
              value={range.end}
              onChange={(e) =>
                onChangeRange({ ...range, end: e.target.value, preset: "custom" })
              }
              className="w-full bg-background border border-border rounded-lg px-2 py-1 text-foreground font-mono text-xs focus:ring-1 focus:ring-blue-500 outline-none"
            />
          </div>
        </div>
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
          onClick={onContinue}
          className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-semibold h-9 rounded-xl text-xs cursor-pointer shadow-lg shadow-blue-600/30"
        >
          Variables Satelitales
          <ArrowRightIcon className="w-3.5 h-3.5 ml-1.5" />
        </Button>
      </div>
    </div>
  );
}
