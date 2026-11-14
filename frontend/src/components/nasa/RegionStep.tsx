"use client";

import { useState } from "react";
import { GeoPoint, PredefinedRegion, RegionAnalysisPayload } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";
import { PREDEFINED_REGIONS } from "./PredefinedRegions";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  MapPinIcon,
  MagnifyingGlassIcon,
  ArrowRightIcon,
  InformationCircleIcon,
  GlobeAmericasIcon,
  SparklesIcon,
} from "@heroicons/react/24/outline";

interface RegionStepProps {
  regionData: RegionAnalysisPayload | null;
  onSelectPredefined: (region: PredefinedRegion) => void;
  onSearchManual: (query: string) => Promise<void>;
  isSearching: boolean;
  onContinue: () => void;
}

export function RegionStep({
  regionData,
  onSelectPredefined,
  onSearchManual,
  isSearching,
  onContinue,
}: RegionStepProps) {
  const { language, t } = useTranslation();
  const [query, setQuery] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSearchManual(query.trim());
    }
  };

  return (
    <div className="space-y-4 animate-in fade-in duration-300">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <MapPinIcon className="w-4 h-4 text-red-500" />
          <h2 className="text-sm font-bold uppercase tracking-wider text-foreground font-mono">
            {t("regionStep.title")}
          </h2>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">
          {t("regionStep.description")}
        </p>
      </div>

      {/* Formulario de búsqueda escrita (complementaria a la voz) */}
      <form onSubmit={handleSubmit} className="flex items-center gap-1.5">
        <div className="relative flex-1">
          <MagnifyingGlassIcon className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("header.searchPlaceholder")}
            className="w-full bg-background border-border pl-9 pr-3 h-10 text-foreground placeholder:text-muted-foreground text-xs rounded-xl focus-visible:ring-blue-600 focus-visible:border-blue-600 font-mono"
          />
        </div>
        <Button
          type="submit"
          disabled={isSearching || !query.trim()}
          className="bg-blue-600 hover:bg-blue-700 text-white h-10 px-4 rounded-xl text-xs font-semibold cursor-pointer shadow-lg shadow-blue-600/20 shrink-0"
        >
          {isSearching ? "..." : t("regionStep.searchButton")}
        </Button>
      </form>

      {/* Regiones científicas predefinidas */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground uppercase tracking-wider">
          <span>{t("regionStep.suggestedTitle")}</span>
          <span className="text-blue-500 font-semibold">NASA DATASETS</span>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {PREDEFINED_REGIONS.map((reg) => {
            const isSelected = regionData?.regionName === reg.name[language];

            return (
              <button
                key={reg.id}
                type="button"
                onClick={() => onSelectPredefined(reg)}
                className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between ${
                  isSelected
                    ? "bg-blue-100 dark:bg-blue-950/70 border-blue-500 text-foreground ring-1 ring-blue-500/50"
                    : "bg-card/70 border-border text-foreground hover:border-blue-500/40 hover:bg-muted/70"
                }`}
              >
                <span className="text-xs font-semibold leading-tight line-clamp-1">
                  {reg.name[language]}
                </span>
                <span className="text-[10px] text-muted-foreground font-mono mt-1">
                  {reg.area[language]}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Indicador de región delimitada */}
      {regionData && (
        <div className="p-3 rounded-xl bg-blue-50 dark:bg-blue-950/50 border border-blue-500/40 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-blue-600 dark:text-blue-300 font-bold font-mono">
              REGION DELIMITADA
            </span>
            <span className="text-[10px] text-red-500 font-mono font-semibold">
              3 VERTICES ACTIVOS
            </span>
          </div>
          <div className="text-xs font-semibold text-foreground">
            {regionData.regionName}
          </div>
          <p className="text-[11px] text-muted-foreground leading-snug">
            {regionData.description}
          </p>

          <Button
            type="button"
            onClick={onContinue}
            className="w-full mt-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold h-9 rounded-xl text-xs cursor-pointer shadow-lg shadow-blue-600/30"
          >
            Continuar a Seleccion de Periodo
            <ArrowRightIcon className="w-3.5 h-3.5 ml-1.5" />
          </Button>
        </div>
      )}

      {/* Pista de voz */}
      <div className="flex items-start gap-2 p-2.5 rounded-xl bg-card/70 border border-border text-[11px] text-muted-foreground leading-snug">
        <InformationCircleIcon className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
        <span>{t("regionStep.hint")}</span>
      </div>
    </div>
  );
}
