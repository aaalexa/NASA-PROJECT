"use client";

import { CubeTransparentIcon } from "@heroicons/react/24/outline";
import { DateRange, RegionAnalysisPayload, VariableId } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";
import { useBackend } from "@/context/BackendContext";
import { failureMessage } from "@/lib/analysisText";
import type { useAnalysisData } from "@/hooks/useAnalysisData";
import { AnalysisTabs } from "@/components/analysis/AnalysisTabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

interface ResultsStepProps {
  regionData: RegionAnalysisPayload;
  range: DateRange;
  selectedVariables: VariableId[];
  /** Backend data for the current selection (shared with the 3D drawer, so it is fetched once). */
  analysis: ReturnType<typeof useAnalysisData>;
  onEditCriteria: () => void;
  onRestart: () => void;
  /** Opens the full-screen 3D analysis. */
  onOpen3d?: () => void;
  readOnly?: boolean;
}

/** Results in the side panel: charts and numbers, with a button to open the full-screen 3D view. */
export function ResultsStep({ regionData, range, selectedVariables, analysis, onEditCriteria, onRestart, onOpen3d, readOnly }: ResultsStepProps) {
  const { t } = useTranslation();
  const backend = useBackend();
  const { dte, failure, anyResult, synthetic, mode, loading } = analysis;

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
            <Button size="sm" onClick={analysis.retry}>
              {t("resultsStep.retry")}
            </Button>
            {failure === "no_data_in_memory" && (
              <Button size="sm" variant="outline" onClick={() => analysis.setModeOverride("sintetico")}>
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

          {onOpen3d && !readOnly && (
            <Button size="lg" className="w-full gap-2" onClick={onOpen3d}>
              <CubeTransparentIcon className="size-5" />
              {t("resultsStep.open3d")}
            </Button>
          )}

          <AnalysisTabs analysis={analysis} regionData={regionData} range={range} selectedVariables={selectedVariables} />

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
