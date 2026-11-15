"use client";

import { ArrowTrendingDownIcon, ArrowTrendingUpIcon, MinusIcon } from "@heroicons/react/24/outline";
import { useTranslation } from "@/context/LanguageContext";
import type { BackendVariable, DteVariable, TendenciaRespuesta } from "@/lib/api";
import { MiniChart } from "@/components/charts/MiniChart";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export const prettyUnit = (u: string) => u.replace("degC", "°C").replace("m3/m3", "m³/m³").replace("/anio", "/año").replace("/dia", "/día");

export function fmt(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "–";
  const a = Math.abs(n);
  if (a >= 100) return n.toFixed(0);
  if (a >= 10) return n.toFixed(1);
  if (a >= 1) return n.toFixed(2);
  if (a === 0) return "0";
  return n.toFixed(a >= 0.01 ? 3 : 4);
}

export const signed = (n: number | null | undefined) => (n !== null && n !== undefined && n > 0 ? `+${fmt(n)}` : fmt(n));

export function fmtP(p: number | null | undefined): string {
  if (p === null || p === undefined) return "–";
  if (p < 0.001) return "< 0.001";
  return p.toFixed(3);
}

export function Block({ title, items, empty }: { title: string; items: string[]; empty?: string }) {
  return (
    <div className="space-y-1.5">
      <p className="text-sm font-bold">{title}</p>
      {items.length === 0 ? (
        <p className="text-xs text-muted-foreground">{empty}</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((it, i) => (
            <li key={i} className="text-xs leading-relaxed text-muted-foreground">
              {it}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CardHeader({ info, value, caption, tone }: { info: BackendVariable; value: string; caption: string; tone: "up" | "down" | "flat" }) {
  const Arrow = tone === "up" ? ArrowTrendingUpIcon : tone === "down" ? ArrowTrendingDownIcon : MinusIcon;
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="text-sm font-bold">{info.nombre_simple}</p>
        <p className="text-[11px] text-muted-foreground">{info.short_name ?? info.fuente}</p>
      </div>
      <div className="text-right">
        <p className={`flex items-center justify-end gap-1 text-sm font-bold tabular-nums ${tone === "up" ? "text-brand-red" : tone === "down" ? "text-brand-blue" : "text-muted-foreground"}`}>
          <Arrow className="size-4" />
          {value}
        </p>
        <p className="text-[11px] text-muted-foreground">{caption}</p>
      </div>
    </div>
  );
}

/** One of the four Down to Earth variables (P, T, SM, ET): OLS + HAC + Holm over the annual series. */
export function DteCard({ info, v, language }: { info: BackendVariable; v: DteVariable; language: "es" | "en" }) {
  const { t } = useTranslation();
  const dir = v.direction;
  const dirWord = dir === "aumento" ? t("resultsStep.increase") : dir === "disminucion" ? t("resultsStep.decrease") : t("resultsStep.stable");
  const unit = prettyUnit(v.units.annual);
  const first = v.annual[0]?.year;
  const last = v.annual[v.annual.length - 1]?.year;

  return (
    <Card size="sm" className="gap-0 px-3">
      <CardHeader info={info} value={`${signed(v.slope_decade)} ${unit}`} caption={t("resultsStep.perDecade")} tone={dir === "aumento" ? "up" : dir === "disminucion" ? "down" : "flat"} />
      {first !== undefined && last !== undefined && (
        <MiniChart
          className="mt-2"
          ariaLabel={`${info.nombre_simple}: ${t("resultsStep.annualChart")}`}
          xLabels={[String(first), String(last)]}
          series={[
            { label: "valor", color: "var(--blue)", values: v.annual.map((a) => a.value) },
            { label: "tendencia", color: v.significant ? "var(--red)" : "var(--olive)", values: v.annual.map((a) => a.fitted), dashed: true },
          ]}
        />
      )}
      <div className="mt-2 flex items-center justify-between border-t border-border pt-2 text-xs tabular-nums text-muted-foreground">
        <span>
          {t("resultsStep.ci")} [{signed(v.ci95?.[0])}, {signed(v.ci95?.[1])}]
        </span>
        <span>
          {t("resultsStep.pAdj")} {fmtP(v.p_holm)}
        </span>
      </div>
      <Badge variant="outline" className={`mt-2 w-fit ${v.significant ? "border-brand-red/50 text-brand-red" : "border-brand-olive/60 text-brand-olive"}`}>
        {v.significant ? `${dirWord} · ${t("resultsStep.significant")}` : t("resultsStep.insufficient")}
      </Badge>
      {language === "es" && <p className="mt-2 text-xs leading-snug text-muted-foreground">{v.summary_text}</p>}
      {v.sensible_al_rezago && <p className="mt-1.5 text-xs text-brand-olive">{t("resultsStep.lagSensitive")}</p>}
      {v.quality.warnings.length > 0 && <p className="mt-1.5 text-xs text-brand-red">{v.quality.warnings.join(" · ")}</p>}
    </Card>
  );
}

/** Any other backend variable: trend engine (OLS with effective n + Mann-Kendall) from /api/v1/tendencias. */
export function TrendCard({ info, r }: { info: BackendVariable; r: TendenciaRespuesta }) {
  const { t } = useTranslation();
  const tr = r.tendencia;
  const tone = tr.direccion === "sube" ? "up" : tr.direccion === "baja" ? "down" : "flat";
  const unit = prettyUnit(r.metadatos.unidad_pendiente).replace("/decada", "");
  const significant = tr.veredicto === "significativo";
  const verdict = tr.veredicto === "significativo" ? t("resultsStep.significant") : tr.veredicto === "indicio" ? t("resultsStep.indicio") : t("resultsStep.insufficient");
  const pts = r.puntos ?? [];
  const beta = r.metadatos.recta_ols;
  const anomalies = pts.map((p) => p.anomalia ?? p.valor);
  const fitted = beta ? pts.map((p) => beta.beta0 + beta.beta1_por_paso * p.t) : [];
  const useAnom = pts.some((p) => p.anomalia !== null);

  return (
    <Card size="sm" className="gap-0 px-3">
      <CardHeader info={info} value={`${signed(tr.pendiente_ols_decada)} ${unit}`} caption={t("resultsStep.perDecade")} tone={tone} />
      {pts.length > 1 && (
        <MiniChart
          className="mt-2"
          ariaLabel={`${info.nombre_simple}: ${t("resultsStep.annualChart")}`}
          xLabels={[pts[0].fecha, pts[pts.length - 1].fecha]}
          series={[
            { label: "valor", color: "var(--blue)", values: useAnom ? anomalies : pts.map((p) => p.valor) },
            ...(useAnom && fitted.length ? [{ label: "tendencia", color: significant ? "var(--red)" : "var(--olive)", values: fitted, dashed: true }] : []),
          ]}
        />
      )}
      <div className="mt-2 flex items-center justify-between border-t border-border pt-2 text-xs tabular-nums text-muted-foreground">
        <span>
          {t("resultsStep.ci")} [{signed(tr.ic95_decada?.[0])}, {signed(tr.ic95_decada?.[1])}]
        </span>
        <span>
          p {fmtP(tr.p_t)} · MK {fmtP(tr.p_mk)}
        </span>
      </div>
      <Badge variant="outline" className={`mt-2 w-fit ${significant ? "border-brand-red/50 text-brand-red" : "border-brand-olive/60 text-brand-olive"}`}>
        {verdict}
      </Badge>
      {tr.cambio_pct_decada !== null && (
        <p className="mt-1.5 text-xs text-muted-foreground tabular-nums">
          {signed(tr.cambio_pct_decada)} % {t("resultsStep.perDecade")}
          {tr.anios_faltantes ? ` · ${t("resultsStep.yearsMissing").replace("{n}", fmt(tr.anios_faltantes))}` : ""}
        </p>
      )}
    </Card>
  );
}

export function FailedCard({ info, text }: { info: BackendVariable; text: string }) {
  return (
    <Card size="sm" className="gap-1 px-3">
      <p className="text-sm font-bold">{info.nombre_simple}</p>
      <p className="text-xs text-brand-red">{text}</p>
    </Card>
  );
}
