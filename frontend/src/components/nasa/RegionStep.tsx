"use client";

import { useState } from "react";
import { PredefinedRegion, RegionAnalysisPayload } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";
import { PREDEFINED_REGIONS } from "./PredefinedRegions";
import { ArrowRightIcon, MagnifyingGlassIcon } from "@heroicons/react/24/outline";

interface RegionStepProps {
  regionData: RegionAnalysisPayload | null;
  onSelectPredefined: (region: PredefinedRegion) => void;
  onSearchManual: (query: string) => Promise<boolean>;
  isSearching: boolean;
  onContinue: () => void;
}

export function RegionStep({ regionData, onSelectPredefined, onSearchManual, isSearching, onContinue }: RegionStepProps) {
  const { language, t } = useTranslation();
  const [query, setQuery] = useState("");
  const [notFound, setNotFound] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setNotFound(!(await onSearchManual(query.trim())));
  };

  return (
    <div className="space-y-5 animate-in fade-in duration-300">
      <div>
        <h2 className="title text-lg">{t("regionStep.title")}</h2>
        <p className="mt-1.5 text-sm text-muted-foreground">{t("regionStep.description")}</p>
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <div className="relative flex-1">
          <MagnifyingGlassIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            className="field pl-9"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("header.searchPlaceholder")}
            aria-label={t("regionStep.title")}
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={isSearching || !query.trim()}>
          {isSearching ? "…" : t("regionStep.searchButton")}
        </button>
      </form>
      {notFound && (
        <p role="alert" className="-mt-3 text-xs text-brand-red">
          {t("regionStep.notFound")}
        </p>
      )}

      <div className="space-y-2">
        <p className="eyebrow">{t("regionStep.suggestedTitle")}</p>
        <div className="grid grid-cols-2 gap-2">
          {PREDEFINED_REGIONS.map((reg) => (
            <button
              key={reg.id}
              type="button"
              className="choice !px-3 !py-2"
              data-selected={regionData?.regionName === reg.name[language]}
              onClick={() => {
                setNotFound(false);
                onSelectPredefined(reg);
              }}
            >
              <span className="line-clamp-2 text-xs font-medium leading-snug">{reg.name[language]}</span>
              <span className="mt-0.5 block text-[11px] text-muted-foreground">{reg.area[language]}</span>
            </button>
          ))}
        </div>
      </div>

      {regionData && (
        <div className="space-y-3 border-l-2 border-primary/70 pl-3">
          <div>
            <p className="eyebrow">{t("regionStep.delimited")}</p>
            <p className="mt-1 text-sm font-bold">{regionData.regionName}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{regionData.description}</p>
          </div>
          <button type="button" className="btn btn-primary w-full" onClick={onContinue}>
            {t("regionStep.continue")}
            <ArrowRightIcon className="h-4 w-4" />
          </button>
        </div>
      )}

      <p className="text-xs text-muted-foreground">{t("regionStep.hint")}</p>
    </div>
  );
}
