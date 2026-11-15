import { DteResult, ID_TO_DTE, TendenciaRespuesta } from "@/lib/api";

export interface MonthlyCell {
  /** Zero-based index of the year inside the series. */
  yi: number;
  /** Zero-based month (0 = January). */
  m: number;
  year: number;
  /** Standardised anomaly (z-score) used for height and colour. */
  z: number | null;
  /** Value in the variable's own unit, when the backend gives it. */
  value: number | null;
}

export interface AnnualPoint {
  year: number;
  value: number | null;
  fitted: number | null;
}

/** Everything the 3D series view needs about one variable, all of it from backend responses. */
export interface SeriesData {
  id: string;
  name: string;
  unit: string;
  years: number[];
  monthly: MonthlyCell[];
  annual: AnnualPoint[];
  slopeDecade: number | null;
  /** "up" | "down" | "flat" direction of the backend trend. */
  direction: "up" | "down" | "flat";
  significant: boolean;
}

function std(values: number[]) {
  const mean = values.reduce((s, v) => s + v, 0) / values.length;
  return Math.sqrt(values.reduce((s, v) => s + (v - mean) ** 2, 0) / Math.max(1, values.length - 1)) || 1;
}

/** Annual mean of monthly points + the backend's slope drawn through their mean (no re-estimation). */
function annualFromMonthly(cells: { year: number; value: number | null }[], slopeDecade: number | null): AnnualPoint[] {
  const byYear = new Map<number, number[]>();
  for (const c of cells) {
    if (c.value === null || !Number.isFinite(c.value)) continue;
    (byYear.get(c.year) ?? byYear.set(c.year, []).get(c.year)!).push(c.value);
  }
  const years = [...byYear.keys()].sort((a, b) => a - b);
  const means = years.map((y) => byYear.get(y)!.reduce((s, v) => s + v, 0) / byYear.get(y)!.length);
  const meanAll = means.reduce((s, v) => s + v, 0) / (means.length || 1);
  const midYear = (years[0] + years[years.length - 1]) / 2;
  return years.map((year, i) => ({
    year,
    value: means[i],
    fitted: slopeDecade === null ? null : meanAll + (slopeDecade / 10) * (year - midYear),
  }));
}

export function buildSeriesData(
  id: string,
  name: string,
  dte: DteResult | undefined,
  extras: Record<string, TendenciaRespuesta | string>
): SeriesData | null {
  const code = ID_TO_DTE[id];
  if (code && dte) {
    const v = dte.variables[code];
    const years = [...new Set(v.monthly.map((p) => Number(p.date.slice(0, 4))))].sort((a, b) => a - b);
    const monthly: MonthlyCell[] = v.monthly.map((p) => {
      const year = Number(p.date.slice(0, 4));
      return { yi: years.indexOf(year), m: Number(p.date.slice(5, 7)) - 1, year, z: p.z, value: p.value };
    });
    return {
      id,
      name,
      unit: v.units.annual,
      years,
      monthly,
      annual: v.annual.map((a) => ({ year: a.year, value: a.value, fitted: a.fitted })),
      slopeDecade: v.slope_decade,
      direction: v.direction === "aumento" ? "up" : v.direction === "disminucion" ? "down" : "flat",
      significant: v.significant,
    };
  }

  const extra = extras[id];
  if (extra && typeof extra !== "string" && extra.puntos?.length) {
    const tr = extra.tendencia;
    const pts = extra.puntos;
    const slope = tr.pendiente_ols_decada;
    const direction = tr.direccion === "sube" ? "up" : tr.direccion === "baja" ? "down" : "flat";
    const significant = tr.veredicto === "significativo";
    const unit = extra.metadatos.unidad;
    const monthlyPts = pts.filter((p) => p.fecha.length >= 7);

    if (monthlyPts.length) {
      const years = [...new Set(monthlyPts.map((p) => Number(p.fecha.slice(0, 4))))].sort((a, b) => a - b);
      const anomalies = monthlyPts.map((p) => p.anomalia).filter((x): x is number => x !== null);
      const s = anomalies.length ? std(anomalies) : 1;
      const monthly: MonthlyCell[] = monthlyPts.map((p) => {
        const year = Number(p.fecha.slice(0, 4));
        return { yi: years.indexOf(year), m: Number(p.fecha.slice(5, 7)) - 1, year, z: p.anomalia === null ? null : p.anomalia / s, value: p.valor };
      });
      return {
        id,
        name,
        unit,
        years,
        monthly,
        annual: annualFromMonthly(monthly.map((c) => ({ year: c.year, value: c.value })), slope),
        slopeDecade: slope,
        direction,
        significant,
      };
    }

    // Annual indicators (e.g. longest dry spell): one point per year, no monthly carpet.
    const annualPts = pts.map((p) => ({ year: Number(p.fecha.slice(0, 4)), value: p.valor }));
    const vals = annualPts.map((p) => p.value).filter((x): x is number => x !== null);
    const meanAll = vals.reduce((s, v) => s + v, 0) / (vals.length || 1);
    const mid = (annualPts[0].year + annualPts[annualPts.length - 1].year) / 2;
    return {
      id,
      name,
      unit,
      years: annualPts.map((p) => p.year),
      monthly: [],
      annual: annualPts.map((p) => ({ ...p, fitted: slope === null ? null : meanAll + (slope / 10) * (p.year - mid) })),
      slopeDecade: slope,
      direction,
      significant,
    };
  }
  return null;
}
