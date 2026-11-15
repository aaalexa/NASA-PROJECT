"use client";

import { ArrowDownTrayIcon } from "@heroicons/react/24/outline";
import { useTranslation } from "@/context/LanguageContext";
import { useBackend } from "@/context/BackendContext";
import { DTE_CODES, ID_TO_DTE, csvUrl } from "@/lib/api";
import type { RegionAnalysisPayload, DateRange, VariableId } from "@/types/geo";
import type { useAnalysisData } from "@/hooks/useAnalysisData";
import { failureMessage } from "@/lib/analysisText";
import { MiniChart } from "@/components/charts/MiniChart";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Block, DteCard, FailedCard, TrendCard, signed } from "@/components/nasa/analysisCards";

const SERIES_COLORS = { P: "var(--blue)", T: "var(--red)", SM: "var(--olive)", ET: "var(--lava)" } as const;

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
  const { dte, extras, mode } = analysis;
  const csvReq = { region: regionData, inicio: range.start, fin: range.end, mode };

  return (
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
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px]">
            {DTE_CODES.map((c) => (
              <span key={c} className="flex items-center gap-1.5">
                <span className="size-2 rounded-full" style={{ background: SERIES_COLORS[c] }} />
                {c}
              </span>
            ))}
          </div>
          <Separator />
          <p className="text-xs text-muted-foreground">{t("resultsStep.relationsNote")}</p>
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
          <Block title={t("resultsStep.limitsTitle")} items={dte.conclusion.methodological_limits} />
          <Separator />
          <div className="space-y-2">
            <p className="eyebrow">{t("resultsStep.download")}</p>
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
          </div>
        </TabsContent>
      )}
    </Tabs>
  );
}
