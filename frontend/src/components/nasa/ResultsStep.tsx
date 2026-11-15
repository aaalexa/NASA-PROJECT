"use client";

import { CubeTransparentIcon } from "@heroicons/react/24/outline";
import { DateRange, RegionAnalysisPayload, VariableId } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";
import { useBackend } from "@/context/BackendContext";
import { failureMessage } from "@/lib/analysisText";
import { BACKEND_URL } from "@/lib/api";
import type { useAnalysisData } from "@/hooks/useAnalysisData";
import { AnalysisTabs } from "@/components/analysis/AnalysisTabs";
import { CsvUploadCard } from "@/components/analysis/CsvUploadCard";
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
  const { dte, failure, failureText, anyResult, synthetic, mode, loading, job, uploaded } = analysis;
  const span = dte?.metadata.trend_span;
  const stageKey = (etapa: string) =>
    ["P", "T", "SM", "ET", "analisis"].includes(etapa) ? `resultsStep.stages.${etapa}` : "resultsStep.stages.pending";

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

      {uploaded && (
        <Card size="sm" className="gap-2 px-4" role="status">
          <p className="text-sm font-bold">{t("resultsStep.uploadedBanner").replace("{file}", uploaded.fileName)}</p>
          <Button size="sm" variant="outline" className="w-fit" onClick={() => analysis.setUploaded(null)}>
            {t("resultsStep.backToRegion")}
          </Button>
        </Card>
      )}

      {loading && job && (
        <div className="space-y-2 rounded-2xl bg-muted p-4" role="status" aria-live="polite">
          <p className="text-sm font-bold">{t("resultsStep.jobTitle")}</p>
          <div className="flex items-baseline justify-between gap-2 text-xs tabular-nums">
            <span>{t(stageKey(job.etapa))}</span>
            <span className="font-bold">{Math.round(job.porcentaje)} %</span>
          </div>
          <Progress value={job.porcentaje} aria-label={t("resultsStep.jobTitle")} />
          <p className="truncate text-xs text-muted-foreground">{job.mensaje}</p>
          <p className="text-xs leading-relaxed text-muted-foreground">{t("resultsStep.jobNote")}</p>
        </div>
      )}

      {loading && !job && (
        <div className="space-y-3" role="status" aria-live="polite">
          <p className="text-sm text-muted-foreground">{mode === "descargar" ? t("resultsStep.checkingMemory") : t("resultsStep.loading")}</p>
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
          {failure !== "offline" && failureText && <p className="text-xs text-muted-foreground">{failureText}</p>}
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
          {span && (
            <p className="text-xs tabular-nums text-muted-foreground">
              {t("resultsStep.trendSpan")
                .replace("{start}", String(span.start))
                .replace("{end}", String(span.end))
                .replace("{n}", String(span.n_years))}
            </p>
          )}

          {onOpen3d && !readOnly && !uploaded && (
            <Button size="lg" className="w-full gap-2" onClick={onOpen3d}>
              <CubeTransparentIcon className="size-5" />
              {t("resultsStep.open3d")}
            </Button>
          )}

          <AnalysisTabs analysis={analysis} regionData={regionData} range={range} selectedVariables={selectedVariables} />

          {synthetic && !uploaded && !backend.earthdata && (
            <Card size="sm" className="gap-1 px-4" role="note">
              <p className="text-sm font-bold text-brand-red">{t("resultsStep.noCredentialsTitle")}</p>
              <p className="text-xs leading-relaxed text-muted-foreground">{t("resultsStep.noCredentials").replace("{url}", BACKEND_URL)}</p>
            </Card>
          )}
          {synthetic && <p className="text-xs leading-relaxed text-muted-foreground">{t("resultsStep.syntheticNote")}</p>}
          <p className="text-xs leading-relaxed text-muted-foreground">{t("resultsStep.limits")}</p>
        </>
      )}

      {!readOnly && !loading && <CsvUploadCard onResult={(result, fileName) => analysis.setUploaded(result, fileName)} />}

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
