"use client";

import { useEffect } from "react";
import { ArrowDownTrayIcon } from "@heroicons/react/24/outline";
import { DateRange, RegionAnalysisPayload, VariableId } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";
import { useBackend } from "@/context/BackendContext";
import { DTE_CODES, ID_TO_DTE, csvUrl } from "@/lib/api";
import { buildDigest, failureMessage } from "@/lib/analysisText";
import { useAnalysisData } from "@/hooks/useAnalysisData";
import { MiniChart } from "@/components/charts/MiniChart";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Block, DteCard, FailedCard, TrendCard, signed } from "@/components/nasa/analysisCards";

interface ResultsStepProps {
  regionData: RegionAnalysisPayload;
  range: DateRange;
  selectedVariables: VariableId[];
  onEditCriteria: () => void;
  onRestart: () => void;
  /** Plain-text digest of the real results, so the Moody chat can explain them. */
  onDigest?: (digest: string | null) => void;
  readOnly?: boolean;
}

const SERIES_COLORS = { P: "var(--blue)", T: "var(--red)", SM: "var(--olive)", ET: "var(--lava)" } as const;

/** Compact 2D results (used inside the side panel, e.g. while a demo plays). */
export function ResultsStep({ regionData, range, selectedVariables, onEditCriteria, onRestart, onDigest, readOnly }: ResultsStepProps) {
  const { language, t } = useTranslation();
  const backend = useBackend();
  const a = useAnalysisData(regionData, range, selectedVariables);
  const { dte, extras, failure, anyResult, synthetic, mode, current, loading } = a;
  const csvReq = { region: regionData, inicio: range.start, fin: range.end, mode };

  useEffect(() => {
    if (!onDigest) return;
    onDigest(buildDigest(a.coreIds, dte, extras));
    return () => onDigest(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current]);

  return (
    <div className="space-y-5 animate-in fade-in duration-300">
      <div>
        <h2 className="title text-lg">{t("resultsStep.title")}</h2>
        <p className="mt-1.5 text-sm text-muted-foreground">{t("resultsStep.description")}</p>
      </div>

      <div className="flex items-start justify-between gap-3 rounded-2xl bg-muted p-4">
        <div className="min-w-0">
          <p className="eyebrow">{t("resultsStep.region")}</p>
          <p className="mt-1 truncate text-sm font-bold">{regionData.regionName}</p>
          <p className="text-xs tabular-nums text-muted-foreground">
            {range.start.slice(0, 4)} – {range.end.slice(0, 4)}
          </p>
        </div>
        {!readOnly && (
          <Button variant="ghost" size="sm" onClick={onEditCriteria} className="shrink-0">
            {t("resultsStep.edit")}
          </Button>
        )}
      </div>

      {loading && (
        <div className="space-y-3" role="status" aria-live="polite">
          <p className="text-sm text-muted-foreground">{mode === "descargar" ? t("resultsStep.loadingLive") : t("resultsStep.loading")}</p>
          <Progress value={null} aria-label={t("resultsStep.loading")} />
        </div>
      )}

      {backend.state === "offline" && !loading && !failure && (
        <Card className="gap-3 px-4" role="alert">
          <p className="text-sm font-bold text-brand-red">{t("resultsStep.offline")}</p>
          <p className="text-xs text-muted-foreground">{failureMessage("offline", t)}</p>
          <Button size="sm" className="w-fit" onClick={backend.recheck}>
            {t("resultsStep.retry")}
          </Button>
        </Card>
      )}

      {failure && !loading && (
        <Card className="gap-3 px-4" role="alert">
          <p className="text-sm font-bold text-brand-red">{failure === "offline" ? t("resultsStep.offline") : failureMessage(failure, t)}</p>
          {failure === "offline" && <p className="text-xs text-muted-foreground">{failureMessage(failure, t)}</p>}
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={a.retry}>
              {t("resultsStep.retry")}
            </Button>
            {failure === "no_data_in_memory" && (
              <Button size="sm" variant="outline" onClick={() => a.setModeOverride("sintetico")}>
                {t("resultsStep.useDemo")}
              </Button>
            )}
          </div>
        </Card>
      )}

      {anyResult && !loading && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={synthetic ? "secondary" : "default"} className={synthetic ? "" : "bg-brand-blue text-[var(--deep-space-blue)]"}>
              {synthetic ? t("resultsStep.sourceSynthetic") : t("resultsStep.sourceNasa")}
            </Badge>
            {dte && (
              <span className="text-xs tabular-nums text-muted-foreground">
                {dte.metadata.period[0]} → {dte.metadata.period[1]} · {dte.metadata.years_complete_count}/{dte.metadata.years_expected}
              </span>
            )}
          </div>

          <Tabs defaultValue="vars" className="flex-col">
            <TabsList className="h-9 w-full">
              <TabsTrigger value="vars">{t("resultsStep.tabVars")}</TabsTrigger>
              {dte && <TabsTrigger value="rel">{t("resultsStep.tabRelations")}</TabsTrigger>}
              {dte && <TabsTrigger value="sum">{t("resultsStep.tabSummary")}</TabsTrigger>}
            </TabsList>

            <TabsContent value="vars" className="mt-3 space-y-2">
              {selectedVariables.map((id) => {
                const info = backend.variableById(id);
                if (!info) return null;
                const code = ID_TO_DTE[id];
                if (code && dte) return <DteCard key={id} info={info} v={dte.variables[code]} language={language} />;
                const extra = extras[id];
                if (extra && typeof extra !== "string") return <TrendCard key={id} info={info} r={extra} />;
                if (typeof extra === "string") return <FailedCard key={id} info={info} text={failureMessage(extra, t)} />;
                return null;
              })}
              {dte && <p className="px-1 pt-1 text-xs text-muted-foreground">{t("resultsStep.familyNote")}</p>}
            </TabsContent>

            {dte && (
              <TabsContent value="rel" className="mt-3 space-y-3">
                <div>
                  <p className="text-sm font-bold">{t("resultsStep.anomaliesTitle")}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">{t("resultsStep.anomaliesNote")}</p>
                </div>
                <MiniChart
                  ariaLabel={t("resultsStep.anomaliesTitle")}
                  height={96}
                  xLabels={[dte.metadata.period[0], dte.metadata.period[1]]}
                  series={DTE_CODES.map((c) => ({ label: c, color: SERIES_COLORS[c], values: dte.joint.standardized_anomalies.map((p) => p[c]) }))}
                />
                <Separator />
                {dte.joint.pairs_list.map((p) => (
                  <Card key={p.pair} size="sm" className="gap-1 px-3">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-sm font-bold">{p.pair.replace("-", " · ")}</span>
                      <span className="text-sm font-bold tabular-nums">r = {p.r === null ? "–" : signed(p.r)}</span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {p.n} {t("resultsStep.months")}
                      {p.direction_description ? ` · ${p.direction_description}` : ""}
                    </p>
                  </Card>
                ))}
              </TabsContent>
            )}

            {dte && (
              <TabsContent value="sum" className="mt-3 space-y-4">
                <Block title={t("resultsStep.jointReading")} items={[dte.conclusion.joint_reading]} />
                <Block title={t("resultsStep.withEvidence")} items={dte.conclusion.changes_with_statistical_evidence} empty={t("resultsStep.none")} />
                <Block title={t("resultsStep.limitsTitle")} items={dte.conclusion.methodological_limits} />
                <Separator />
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" className="flex-1" render={<a href={csvUrl("anual", csvReq)} download />}>
                    <ArrowDownTrayIcon className="size-4" />
                    {t("resultsStep.downloadAnnual")}
                  </Button>
                  <Button variant="outline" size="sm" className="flex-1" render={<a href={csvUrl("mensual", csvReq)} download />}>
                    <ArrowDownTrayIcon className="size-4" />
                    {t("resultsStep.downloadMonthly")}
                  </Button>
                </div>
              </TabsContent>
            )}
          </Tabs>

          {synthetic && <p className="text-xs leading-relaxed text-muted-foreground">{t("resultsStep.syntheticNote")}</p>}
          <p className="text-xs leading-relaxed text-muted-foreground">{t("resultsStep.limits")}</p>
        </>
      )}

      {!readOnly && (
        <div className="flex gap-2">
          <Button variant="outline" className="flex-1" onClick={onEditCriteria}>
            {t("resultsStep.modify")}
          </Button>
          <Button variant="destructive" className="flex-1" onClick={onRestart}>
            {t("resultsStep.restart")}
          </Button>
        </div>
      )}
    </div>
  );
}
