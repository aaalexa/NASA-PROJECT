"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { ArrowLeftIcon, ArrowPathIcon, ArrowUturnLeftIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { useTranslation } from "@/context/LanguageContext";
import { useBackend } from "@/context/BackendContext";
import { ApiFailure, DteCode, ID_TO_DTE, MapaTendencias, classifyError, dteParams, fetchMapa } from "@/lib/api";
import { failureMessage } from "@/lib/analysisText";
import { buildSeriesData } from "@/lib/seriesData";
import type { useAnalysisData } from "@/hooks/useAnalysisData";
import type { DateRange, RegionAnalysisPayload, VariableId } from "@/types/geo";
import { AnalysisTabs } from "@/components/analysis/AnalysisTabs";
import type { CarpetHover } from "@/components/analysis/CarpetScene";
import type { MapHover } from "@/components/analysis/MapScene";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

// three.js needs the browser: each scene is loaded on demand, client-side only.
const CarpetScene = dynamic(() => import("@/components/analysis/CarpetScene"), { ssr: false });
const RelationsScene = dynamic(() => import("@/components/analysis/RelationsScene"), { ssr: false });
const MapScene = dynamic(() => import("@/components/analysis/MapScene"), { ssr: false });

type View = "series" | "relations" | "map";

interface MapOutcome {
  key: string;
  mapa?: MapaTendencias;
  failure?: ApiFailure;
}

interface AnalysisDrawerProps {
  open: boolean;
  regionData: RegionAnalysisPayload | null;
  range: DateRange;
  selectedVariables: VariableId[];
  /** Backend data for the selection, fetched once by the page and shared with the side panel. */
  analysis: ReturnType<typeof useAnalysisData>;
  onClose: () => void;
  onRestart: () => void;
}

/** Full-screen analysis: the backend's results as interactive 3D scenes plus the numbers beside them. */
export function AnalysisDrawer({ open, regionData, range, selectedVariables, analysis, onClose, onRestart }: AnalysisDrawerProps) {
  const { language, t } = useTranslation();
  const backend = useBackend();
  const { dte, extras, loading, failure, anyResult, synthetic, mode } = analysis;

  const [view, setView] = useState<View>("series");
  const [pickedVar, setPickedVar] = useState<string | null>(null);
  const [carpetHover, setCarpetHover] = useState<CarpetHover | null>(null);
  const [mapHover, setMapHover] = useState<MapHover | null>(null);
  const [relCode, setRelCode] = useState<DteCode | null>(null);
  // The WebGL scenes mount only after the slide-in finishes, so the animation never stutters.
  const [slideDone, setSlideDone] = useState(false);

  const activeVar = pickedVar && selectedVariables.includes(pickedVar) ? pickedVar : selectedVariables.find((id) => backend.variableById(id)) ?? null;
  const activeInfo = activeVar ? backend.variableById(activeVar) : undefined;

  const series = useMemo(
    () => (activeVar && activeInfo ? buildSeriesData(activeVar, activeInfo.nombre_simple, dte, extras) : null),
    [activeVar, activeInfo, dte, extras]
  );

  // The per-pixel map is fetched on demand, only while its view is open.
  const mapRequest = regionData && activeVar ? { region: regionData, inicio: range.start, fin: range.end, mode } : null;
  const mapKey = mapRequest && activeVar ? `${activeVar}|${JSON.stringify(dteParams(mapRequest))}` : "";
  const [mapOutcome, setMapOutcome] = useState<MapOutcome | null>(null);
  const mapWanted = open && view === "map" && mapRequest !== null && activeVar !== null && backend.variableById(activeVar)?.frecuencia !== "diaria";
  const mapLoading = mapWanted && mapOutcome?.key !== mapKey;

  useEffect(() => {
    if (!mapWanted || !mapRequest || !activeVar) return;
    const ctrl = new AbortController();
    fetchMapa(activeVar, { ...mapRequest, signal: ctrl.signal })
      .then((mapa) => setMapOutcome({ key: mapKey, mapa }))
      .catch((e) => {
        const f = classifyError(e);
        if (f !== "aborted") setMapOutcome({ key: mapKey, failure: f });
      });
    return () => ctrl.abort();
    // `mapKey` captures the request; re-run only when it changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapKey, mapWanted]);

  const mapCurrent = mapOutcome?.key === mapKey ? mapOutcome : undefined;

  const verdictLabel = (v: number | null) => (v === 2 ? t("analysis.verdictSig") : v === 1 ? t("analysis.verdictHint") : t("analysis.verdictNone"));
  const monthName = (m: number) => new Date(2000, m, 1).toLocaleDateString(language === "es" ? "es-ES" : "en-US", { month: "long" });

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()} onOpenChangeComplete={setSlideDone} modal={false}>
      <SheetContent
        side="left"
        showCloseButton={false}
        className="data-[side=left]:w-screen! data-[side=left]:max-w-none! gap-0 overflow-hidden rounded-r-[2rem] border-0 p-0 ring-1 ring-border"
      >
        <SheetTitle className="sr-only">{t("analysis.title")}</SheetTitle>
        <SheetDescription className="sr-only">{t("analysis.hint")}</SheetDescription>

        {/* Toolbar */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-border px-4 py-3 sm:px-6">
          <Button variant="outline" size="sm" onClick={onClose} className="gap-1.5">
            <ArrowLeftIcon className="size-4" />
            <span className="hidden sm:inline">{t("analysis.back")}</span>
          </Button>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-bold">{regionData?.regionName}</p>
            <p className="text-xs tabular-nums text-muted-foreground">
              {range.start.slice(0, 4)} – {range.end.slice(0, 4)}
            </p>
          </div>
          {anyResult && (
            <Badge variant={synthetic ? "secondary" : "default"} className={synthetic ? "" : "bg-brand-blue text-[var(--deep-space-blue)]"}>
              {synthetic ? t("resultsStep.sourceSynthetic") : t("resultsStep.sourceNasa")}
            </Badge>
          )}
          <ToggleGroup
            value={[view]}
            onValueChange={(v) => v[0] && setView(v[0] as View)}
            variant="outline"
            spacing={0}
            className="rounded-full bg-card"
            aria-label={t("analysis.views")}
          >
            <ToggleGroupItem value="series" className="rounded-full px-3 text-xs font-medium">
              {t("analysis.viewSeries")}
            </ToggleGroupItem>
            <ToggleGroupItem value="relations" className="rounded-full px-3 text-xs font-medium" disabled={!dte}>
              {t("analysis.viewRelations")}
            </ToggleGroupItem>
            <ToggleGroupItem value="map" className="rounded-full px-3 text-xs font-medium">
              {t("analysis.viewMap")}
            </ToggleGroupItem>
          </ToggleGroup>
          <Button variant="destructive" size="sm" onClick={onRestart} className="gap-1.5">
            <ArrowUturnLeftIcon className="size-4" />
            <span className="hidden md:inline">{t("resultsStep.restart")}</span>
          </Button>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label={t("analysis.close")}>
            <XMarkIcon className="size-5" />
          </Button>
        </div>

        {/* Variable chips (series and map views) */}
        {view !== "relations" && (
          <div className="flex gap-2 overflow-x-auto border-b border-border px-4 py-2 sm:px-6">
            {selectedVariables.map((id) => {
              const info = backend.variableById(id);
              if (!info) return null;
              const on = id === activeVar;
              return (
                <Button key={id} size="sm" variant={on ? "default" : "outline"} className="shrink-0" onClick={() => setPickedVar(id)} aria-pressed={on}>
                  {info.nombre_simple}
                </Button>
              );
            })}
          </div>
        )}

        {/* Body: 3D scene + numbers */}
        <div className="grid min-h-0 flex-1 grid-rows-[minmax(0,46%)_minmax(0,1fr)] lg:grid-cols-[minmax(0,1fr)_400px] lg:grid-rows-1">
          <div className="relative min-h-0 bg-[var(--deep-space-blue)]">
            {(loading || mapLoading || !slideDone) && (
              <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-background/70 px-8 backdrop-blur-sm" role="status">
                <p className="text-sm text-muted-foreground">{mode === "descargar" ? t("resultsStep.loadingLive") : t("analysis.loading")}</p>
                <Progress value={null} className="w-56" aria-label={t("analysis.loading")} />
              </div>
            )}

            {failure && !loading && (
              <div className="absolute inset-0 z-10 flex items-center justify-center p-6">
                <Card className="max-w-sm gap-3 px-5" role="alert">
                  <p className="text-sm font-bold text-brand-red">{failure === "offline" ? t("resultsStep.offline") : failureMessage(failure, t)}</p>
                  {failure === "offline" && <p className="text-xs text-muted-foreground">{failureMessage(failure, t)}</p>}
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" onClick={analysis.retry}>
                      <ArrowPathIcon className="size-4" />
                      {t("resultsStep.retry")}
                    </Button>
                    {failure === "no_data_in_memory" && (
                      <Button size="sm" variant="outline" onClick={() => analysis.setModeOverride("sintetico")}>
                        {t("resultsStep.useDemo")}
                      </Button>
                    )}
                  </div>
                </Card>
              </div>
            )}

            {/* Scenes */}
            {!loading && slideDone && view === "series" && series && (
              <CarpetScene key={`${activeVar}-${series.annual.length}`} data={series} onHover={setCarpetHover} />
            )}
            {!loading && slideDone && view === "relations" && dte && (
              <RelationsScene dte={dte} selected={relCode ?? (activeVar ? ID_TO_DTE[activeVar] ?? null : null)} onSelect={(c) => { setRelCode(c); const id = Object.keys(ID_TO_DTE).find((k) => ID_TO_DTE[k] === c); if (id && selectedVariables.includes(id)) setPickedVar(id); }} />
            )}
            {!loading && slideDone && view === "map" && mapCurrent?.mapa && <MapScene key={mapKey} mapa={mapCurrent.mapa} onHover={setMapHover} />}

            {view === "map" && mapCurrent?.failure && !mapLoading && (
              <div className="absolute inset-0 z-10 flex items-center justify-center p-6">
                <Card className="max-w-sm gap-2 px-5" role="alert">
                  <p className="text-sm font-bold text-brand-red">{t("analysis.mapError")}</p>
                  <p className="text-xs text-muted-foreground">{failureMessage(mapCurrent.failure, t)}</p>
                </Card>
              </div>
            )}

            {/* Overlays */}
            <div className="pointer-events-none absolute left-4 top-4 z-20 max-w-[min(18rem,70%)] space-y-2">
              <Card size="sm" className="gap-1.5 bg-card/80 px-4 backdrop-blur">
                <p className="text-sm font-bold">
                  {view === "series" ? t("analysis.carpetTitle") : view === "relations" ? t("analysis.relationsTitle") : t("analysis.mapTitle")}
                </p>
                <p className="hidden text-xs leading-snug text-muted-foreground sm:block">
                  {view === "series" ? t("analysis.carpetDesc") : view === "relations" ? t("analysis.relationsDesc") : t("analysis.mapDesc")}
                </p>
                {view !== "relations" && (
                  <div className="space-y-1 pt-1">
                    <div
                      className="h-2 rounded-full"
                      style={{ background: "linear-gradient(90deg,#669bbc,#9c914f,#c1121f,#780000)" }}
                      aria-hidden
                    />
                    <div className="flex justify-between text-[11px] text-muted-foreground">
                      <span>{view === "series" ? t("analysis.below") : t("analysis.falls")}</span>
                      <span>{view === "series" ? t("analysis.above") : t("analysis.rises")}</span>
                    </div>
                  </div>
                )}
              </Card>
            </div>

            <div className="pointer-events-none absolute bottom-3 left-4 z-20 text-[11px] text-[var(--steel-blue)]">{t("analysis.hint")}</div>

            {view === "series" && carpetHover && (
              <Card size="sm" className="pointer-events-none absolute right-4 top-4 z-20 gap-0.5 bg-card/90 px-4 backdrop-blur">
                <p className="text-sm font-bold capitalize">
                  {monthName(carpetHover.month)} {carpetHover.year}
                </p>
                <p className="text-xs tabular-nums text-muted-foreground">
                  {carpetHover.value !== null ? `${carpetHover.value.toFixed(2)} ${series?.unit ?? ""}` : "–"}
                </p>
                <p className="text-xs tabular-nums">
                  z = {carpetHover.z !== null ? `${carpetHover.z >= 0 ? "+" : ""}${carpetHover.z.toFixed(2)}` : "–"}
                </p>
              </Card>
            )}
            {view === "map" && mapHover && (
              <Card size="sm" className="pointer-events-none absolute right-4 top-4 z-20 gap-0.5 bg-card/90 px-4 backdrop-blur">
                <p className="text-sm font-bold tabular-nums">
                  {mapHover.lat.toFixed(2)}°, {mapHover.lon.toFixed(2)}°
                </p>
                <p className="text-xs tabular-nums">
                  {mapHover.slope >= 0 ? "+" : ""}
                  {mapHover.slope.toFixed(2)} {mapCurrent?.mapa?.unidad_pendiente.replace("/decada", "")} {t("resultsStep.perDecade")}
                </p>
                <p className="text-xs text-muted-foreground">{verdictLabel(mapHover.verdict)}</p>
              </Card>
            )}
            {view === "series" && !series && !loading && anyResult && (
              <div className="absolute inset-0 z-10 flex items-center justify-center p-6 text-sm text-muted-foreground">{t("analysis.noSeries")}</div>
            )}
          </div>

          <ScrollArea className="min-h-0 border-t border-border lg:border-l lg:border-t-0 [&_[data-slot=scroll-area-viewport]]:max-h-full">
            <div className="space-y-4 p-4 sm:p-5">
              {anyResult && regionData && (
                <AnalysisTabs
                  analysis={analysis}
                  regionData={regionData}
                  range={range}
                  selectedVariables={selectedVariables}
                  activeVariable={activeVar ?? undefined}
                  onSelectVariable={setPickedVar}
                />
              )}
              {synthetic && <p className="text-xs leading-relaxed text-muted-foreground">{t("resultsStep.syntheticNote")}</p>}
              <p className="text-xs leading-relaxed text-muted-foreground">{t("resultsStep.limits")}</p>
            </div>
          </ScrollArea>
        </div>
      </SheetContent>
    </Sheet>
  );
}
