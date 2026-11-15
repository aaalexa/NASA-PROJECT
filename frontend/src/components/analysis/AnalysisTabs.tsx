"use client";

import { ArrowDownTrayIcon } from "@heroicons/react/24/outline";
import { useTranslation } from "@/context/LanguageContext";
import { useBackend } from "@/context/BackendContext";
import { ID_TO_DTE, TableRow, csvUrl, dteTableUrl, rowsToCsv } from "@/lib/api";
import type { RegionAnalysisPayload, DateRange, VariableId } from "@/types/geo";
import type { useAnalysisData } from "@/hooks/useAnalysisData";
import { failureMessage } from "@/lib/analysisText";
import { AnomalyChart, CorrelationBars } from "@/components/charts/RelationCharts";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Block, DataQuality, DteCard, FailedCard, TrendCard, signed } from "@/components/nasa/analysisCards";

type Analysis = ReturnType<typeof useAnalysisData>;

/** The numbers behind the 3D views: per-variable cards, relations and the written summary. */
export function AnalysisTabs({
  analysis,
  regionData,
  range,
  selectedVariables,
  activeVariable,
  onSelectVariable,
}: {
  analysis: Analysis;
  regionData: RegionAnalysisPayload;
  range: DateRange;
  selectedVariables: VariableId[];
  activeVariable?: string;
  onSelectVariable?: (id: string) => void;
}) {
  const { language, t } = useTranslation();
  const backend = useBackend();
  const { dte, extras, mode, jobId, uploaded } = analysis;
  const csvReq = { region: regionData, inicio: range.start, fin: range.end, mode };
  // An uploaded CSV always carries the four Down to Earth variables; otherwise show the user's selection.
  const ids = uploaded ? Object.keys(ID_TO_DTE) : selectedVariables;

  /** Download links: tables of the real-data job, client-side CSV of an uploaded result, or the cached analysis. */
  const downloads: { label: string; href?: string; rows?: TableRow[]; file: string }[] = uploaded
    ? [
        { label: t("resultsStep.downloadAnnual"), rows: uploaded.result.tablas?.anual ?? [], file: "anual.csv" },
        { label: t("resultsStep.downloadMonthly"), rows: uploaded.result.tablas?.mensual ?? [], file: "mensual.csv" },
        {
          label: t("resultsStep.downloadCleaning"),
          rows: uploaded.result.data_cleaning.log as unknown as TableRow[],
          file: "registro_limpieza.csv",
        },
        { label: t("resultsStep.downloadDictionary"), rows: uploaded.result.tablas?.diccionario ?? [], file: "diccionario_datos.csv" },
      ]
    : jobId
      ? [
          { label: t("resultsStep.downloadAnnual"), href: dteTableUrl(jobId, "anual"), file: "anual.csv" },
          { label: t("resultsStep.downloadMonthly"), href: dteTableUrl(jobId, "mensual"), file: "mensual.csv" },
          { label: t("resultsStep.downloadCleaning"), href: dteTableUrl(jobId, "limpieza"), file: "registro_limpieza.csv" },
          { label: t("resultsStep.downloadDictionary"), href: dteTableUrl(jobId, "diccionario"), file: "diccionario_datos.csv" },
        ]
      : [
          { label: t("resultsStep.downloadAnnual"), href: csvUrl("anual", csvReq), file: "anual.csv" },
          { label: t("resultsStep.downloadMonthly"), href: csvUrl("mensual", csvReq), file: "mensual.csv" },
        ];

  const saveRows = (rows: TableRow[], file: string) => {
    const url = URL.createObjectURL(new Blob([rowsToCsv(rows)], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = file;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Tabs defaultValue="vars" className="flex-col">
      <TabsList className="h-9 w-full">
        <TabsTrigger value="vars">{t("resultsStep.tabVars")}</TabsTrigger>
        {dte && <TabsTrigger value="rel">{t("resultsStep.tabRelations")}</TabsTrigger>}
        {dte && <TabsTrigger value="sum">{t("resultsStep.tabSummary")}</TabsTrigger>}
      </TabsList>

      <TabsContent value="vars" className="mt-3 space-y-2">
        {ids.map((id) => {
          const info = backend.variableById(id);
          if (!info) return null;
          const code = ID_TO_DTE[id];
          const extra = extras[id];
          let card: React.ReactNode = null;
          if (code && dte) card = <DteCard info={info} v={dte.variables[code]} language={language} />;
          else if (extra && typeof extra !== "string") card = <TrendCard info={info} r={extra} />;
          else if (typeof extra === "string") card = <FailedCard info={info} text={failureMessage(extra, t)} />;
          if (!card) return null;
          const active = activeVariable === id;
          return (
            <div
              key={id}
              role="button"
              tabIndex={0}
              aria-pressed={active}
              onClick={() => onSelectVariable?.(id)}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelectVariable?.(id)}
              className={`cursor-pointer rounded-3xl outline-none transition-shadow focus-visible:ring-2 focus-visible:ring-ring ${active ? "ring-2 ring-brand-blue" : "hover:ring-1 hover:ring-border"}`}
            >
              {card}
            </div>
          );
        })}
        {analysis.extrasPending && (
          <p className="px-1 pt-1 text-xs text-muted-foreground" role="status">
            {t("resultsStep.extrasPending")}
          </p>
        )}
        {dte && <p className="px-1 pt-1 text-xs text-muted-foreground">{t("resultsStep.familyNote")}</p>}
      </TabsContent>

      {dte && (
        <TabsContent value="rel" className="mt-3 space-y-3">
          <div>
            <p className="text-sm font-bold">{t("resultsStep.anomaliesTitle")}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{t("resultsStep.anomaliesNote")}</p>
          </div>
          <AnomalyChart dte={dte} />
          <Separator />
          <p className="text-xs text-muted-foreground">{t("resultsStep.relationsNote")}</p>
          <p className="text-sm font-bold">{t("resultsStep.correlationsTitle")}</p>
          <CorrelationBars dte={dte} />
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
              <p className="text-xs leading-snug">{p.question}</p>
            </Card>
          ))}
        </TabsContent>
      )}

      {dte && (
        <TabsContent value="sum" className="mt-3 space-y-4">
          <Block title={t("resultsStep.jointReading")} items={[dte.conclusion.joint_reading]} />
          <Block title={t("resultsStep.withEvidence")} items={dte.conclusion.changes_with_statistical_evidence} empty={t("resultsStep.none")} />
          <Block title={t("resultsStep.withoutEvidence")} items={dte.conclusion.inconclusive_or_insufficient_evidence} empty={t("resultsStep.none")} />
          {dte.metadata.warnings?.length > 0 && (
            <Block title={t("resultsStep.warningsTitle")} items={dte.metadata.warnings} />
          )}
          <Block title={t("resultsStep.limitsTitle")} items={dte.conclusion.methodological_limits} />
          {dte.data_cleaning && (
            <>
              <Separator />
              <DataQuality summary={dte.data_cleaning.summary} steps={dte.data_cleaning.steps} />
            </>
          )}
          <Separator />
          <div className="space-y-2">
            <p className="eyebrow">{t("resultsStep.download")}</p>
            <div className="grid grid-cols-2 gap-2">
              {downloads.map((d) =>
                d.href ? (
                  <Button key={d.file} variant="outline" size="sm" render={<a href={d.href} download={d.file} />}>
                    <ArrowDownTrayIcon className="size-4" />
                    {d.label}
                  </Button>
                ) : (
                  <Button key={d.file} variant="outline" size="sm" onClick={() => saveRows(d.rows ?? [], d.file)}>
                    <ArrowDownTrayIcon className="size-4" />
                    {d.label}
                  </Button>
                )
              )}
            </div>
          </div>
        </TabsContent>
      )}
    </Tabs>
  );
}
