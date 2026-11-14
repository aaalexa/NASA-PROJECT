"use client";

import { useState } from "react";
import { PredefinedRegion, RegionAnalysisPayload } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";
import { PREDEFINED_REGIONS } from "./PredefinedRegions";
import { Button } from "@/components/ui/button";
import { ChoiceButton } from "@/components/ui/choice-button";
import { Input } from "@/components/ui/input";
import { ArrowRightIcon, MagnifyingGlassIcon } from "@heroicons/react/24/outline";

interface RegionStepProps {
  regionData: RegionAnalysisPayload | null;
  onSelectPredefined: (region: PredefinedRegion) => void;
  onSearchManual: (query: string) => Promise<boolean>;
  onPreviewText?: (text: string) => void;
  isSearching: boolean;
  onContinue: () => void;
}

export function RegionStep({ regionData, onSelectPredefined, onSearchManual, onPreviewText, isSearching, onContinue }: RegionStepProps) {
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
          <MagnifyingGlassIcon className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-10"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setNotFound(false);
              onPreviewText?.(e.target.value);
            }}
            placeholder={t("header.searchPlaceholder")}
            aria-label={t("regionStep.title")}
          />
        </div>
        <Button type="submit" disabled={isSearching || !query.trim()} className="h-10">
          {isSearching ? "…" : t("regionStep.searchButton")}
        </Button>
      </form>
      {isSearching && (
        <p role="status" className="-mt-3 animate-pulse text-xs text-brand-blue">
          {t("regionStep.locating")}
        </p>
      )}
      {notFound && (
        <p role="alert" className="-mt-3 text-xs text-brand-red">
          {t("regionStep.notFound")}
        </p>
      )}

      <div className="space-y-2">
        <p className="eyebrow">{t("regionStep.suggestedTitle")}</p>
        <div className="grid grid-cols-2 gap-2">
          {PREDEFINED_REGIONS.map((reg) => (
            <ChoiceButton
              key={reg.id}
              selected={regionData?.regionName === reg.name[language]}
              className="flex-col gap-0.5 !px-3 !py-2"
              onClick={() => {
                setNotFound(false);
                onSelectPredefined(reg);
              }}
            >
              <span className="line-clamp-2 text-xs font-medium leading-snug">{reg.name[language]}</span>
              <span className="text-[11px] text-muted-foreground">{reg.area[language]}</span>
            </ChoiceButton>
          ))}
        </div>
      </div>

      {regionData && (
        <div className="space-y-3 rounded-2xl bg-muted p-4">
          <div>
            <p className="eyebrow">{t("regionStep.delimited")}</p>
            <p className="mt-1 text-sm font-bold">{regionData.regionName}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{regionData.description}</p>
          </div>
          <Button className="w-full" onClick={onContinue}>
            {t("regionStep.continue")}
            <ArrowRightIcon className="size-4" />
          </Button>
        </div>
      )}

      <p className="text-xs text-muted-foreground">{t("regionStep.hint")}</p>
    </div>
  );
}
