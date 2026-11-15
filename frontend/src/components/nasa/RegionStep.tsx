"use client";

import { useState } from "react";
import { RegionAnalysisPayload } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";
import { useBackend } from "@/context/BackendContext";
import { ZONE_LABELS } from "@/lib/catalog";
import type { BackendRegion } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChoiceButton } from "@/components/ui/choice-button";
import { Input } from "@/components/ui/input";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ArrowRightIcon, ChevronDownIcon, MagnifyingGlassIcon } from "@heroicons/react/24/outline";

interface RegionStepProps {
  regionData: RegionAnalysisPayload | null;
  onSelectRegion: (region: BackendRegion) => void;
  onSearchManual: (query: string) => Promise<boolean>;
  onPreviewText?: (text: string) => void;
  isSearching: boolean;
  onContinue: () => void;
}

export function RegionStep({ regionData, onSelectRegion, onSearchManual, onPreviewText, isSearching, onContinue }: RegionStepProps) {
  const { language, t } = useTranslation();
  const backend = useBackend();
  const [query, setQuery] = useState("");
  const [notFound, setNotFound] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setNotFound(!(await onSearchManual(query.trim())));
  };

  // Regions grouped by zone, in the backend's order.
  const zones = backend.regions.reduce<Record<string, BackendRegion[]>>((acc, r) => {
    (acc[r.zona] ??= []).push(r);
    return acc;
  }, {});
  const activeZone = regionData?.backendId ? backend.regions.find((r) => r.id === regionData.backendId)?.zona : undefined;

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

      <div className="space-y-3">
        <p className="eyebrow">{t("regionStep.suggestedTitle")}</p>
        {backend.state === "offline" && (
          <div className="space-y-2 rounded-2xl bg-muted p-4">
            <p className="text-sm text-brand-red">{t("backend.offlineShort")}</p>
            <Button size="sm" variant="outline" onClick={backend.recheck}>
              {t("resultsStep.retry")}
            </Button>
          </div>
        )}
        <div className="space-y-2">
          {Object.entries(zones).map(([zona, regs], i) => (
            <Collapsible key={zona} defaultOpen={activeZone ? activeZone === zona : i === 0} className="group/zone rounded-3xl border border-border bg-card/60 p-1.5">
              <CollapsibleTrigger
                render={<Button variant="ghost" className="h-10 w-full justify-between rounded-full px-4 text-sm font-medium hover:bg-muted" />}
              >
                <span className="flex items-center gap-2">
                  {ZONE_LABELS[zona]?.[language] ?? zona}
                  <Badge variant="secondary" className="tabular-nums">
                    {regs.length}
                  </Badge>
                </span>
                <ChevronDownIcon className="size-4 text-muted-foreground transition-transform group-data-[open]/zone:rotate-180" />
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="grid grid-cols-2 gap-2 px-1.5 pb-2 pt-2">
                  {regs.map((r) => (
                    <ChoiceButton
                      key={r.id}
                      selected={regionData?.backendId === r.id}
                      className="min-h-16 flex-col justify-center gap-0.5 !px-3 !py-2.5"
                      onClick={() => {
                        setNotFound(false);
                        onSelectRegion(r);
                      }}
                    >
                      <span className="line-clamp-2 text-xs font-medium leading-snug">{r.nombre}</span>
                      <span className="line-clamp-1 text-[11px] text-muted-foreground">{r.pais ?? r.zona}</span>
                    </ChoiceButton>
                  ))}
                </div>
              </CollapsibleContent>
            </Collapsible>
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
