import { ApiFailure, BACKEND_URL, DteResult, DteVariable, ID_TO_DTE, TendenciaRespuesta } from "@/lib/api";

export function failureMessage(f: ApiFailure, t: (k: string) => string) {
  switch (f) {
    case "offline":
      return t("resultsStep.offlineHint").replace("{url}", BACKEND_URL);
    case "no_data_in_memory":
      return t("resultsStep.noData");
    case "series_rejected":
      return t("resultsStep.seriesRejected");
    case "job_failed":
      return t("resultsStep.jobFailed");
    case "job_not_ready":
      return t("resultsStep.jobNotReady");
    case "file_too_large":
      return t("resultsStep.fileTooLarge");
    case "bad_request":
    case "validation":
      return t("resultsStep.badRequest");
    default:
      return t("resultsStep.genericError");
  }
}

/**
 * i18n key for the backend's official label. The label (Spanish) is decided by the Holm-adjusted p:
 * "aumento/disminución con evidencia estadística según este método", "evidencia insuficiente (tras el ajuste)",
 * "sin inferencia: …" or "no evaluable: …". Never "sin cambio".
 */
export function labelKey(label: string): string {
  const l = label.toLowerCase();
  if (l.startsWith("aumento")) return "resultsStep.labelIncrease";
  if (l.startsWith("disminución") || l.startsWith("disminucion")) return "resultsStep.labelDecrease";
  if (l.startsWith("evidencia insuficiente tras el ajuste")) return "resultsStep.labelInsufficientAfter";
  if (l.startsWith("evidencia insuficiente")) return "resultsStep.labelInsufficient";
  if (l.startsWith("sin inferencia")) return "resultsStep.labelNoInference";
  if (l.startsWith("no evaluable")) return "resultsStep.labelNotEvaluable";
  return "resultsStep.labelInsufficient";
}

/** Label text to show: the backend's Spanish label as is, or its translation; the lag note is shown apart. */
export function labelText(v: DteVariable, language: "es" | "en", t: (k: string) => string): string {
  const base = v.label.replace(/;\s*resultado sensible al rezago$/i, "");
  if (language === "es") return base.charAt(0).toUpperCase() + base.slice(1);
  return t(labelKey(base));
}

/** Plain-text digest of the numbers on screen, for the Moody chat. */
export function buildDigest(
  coreIds: string[],
  dte: DteResult | undefined,
  extras: Record<string, TendenciaRespuesta | ApiFailure>
): string | null {
  if (!dte && Object.keys(extras).length === 0) return null;
  const lines: string[] = [];
  if (dte) {
    const span = dte.metadata.trend_span;
    if (span) lines.push(`tramo de tendencias ${span.start}-${span.end} (${span.n_years} años)`);
    for (const id of coreIds) {
      const v = dte.variables[ID_TO_DTE[id]];
      const ci = v.ci95 ? v.ci95.map((x) => (x === null ? "null" : x.toFixed(3))).join(", ") : "null";
      lines.push(
        `${v.name}: ${v.slope_decade?.toFixed(3)} ${v.units.slope_decade}, IC95 [${ci}], p ajustado (Holm) ${v.p_holm === null ? "null" : v.p_holm.toExponential(2)}, ${v.label}`
      );
    }
    lines.push(...dte.joint.pairs_list.map((p) => `${p.pair}: r=${p.r?.toFixed(2)} (n=${p.n}, exploratorio, sin p)`));
    if (dte.metadata.warnings?.length) lines.push(`avisos: ${dte.metadata.warnings.join(" / ")}`);
  }
  for (const r of Object.values(extras)) {
    if (typeof r === "string") continue;
    lines.push(`${r.metadatos.nombre_simple}: ${r.tendencia.pendiente_ols_decada?.toFixed(3)} ${r.metadatos.unidad_pendiente}, ${r.tendencia.veredicto}, ${r.tendencia.direccion}`);
  }
  const src = dte?.metadata.source ?? Object.values(extras).find((r): r is TendenciaRespuesta => typeof r !== "string")?.metadatos.fuente_datos;
  const simulated = dte?.metadata.simulated ? "; DATOS SIMULADOS" : "";
  return `source=${src}${simulated}; ${lines.join(" | ")}`;
}
