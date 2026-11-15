import { ApiFailure, BACKEND_URL, DteResult, ID_TO_DTE, TendenciaRespuesta } from "@/lib/api";

export function failureMessage(f: ApiFailure, t: (k: string) => string) {
  switch (f) {
    case "offline":
      return t("resultsStep.offlineHint").replace("{url}", BACKEND_URL);
    case "no_data_in_memory":
      return t("resultsStep.noData");
    case "series_rejected":
      return t("resultsStep.seriesRejected");
    case "bad_request":
    case "validation":
      return t("resultsStep.badRequest");
    default:
      return t("resultsStep.genericError");
  }
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
    for (const id of coreIds) {
      const v = dte.variables[ID_TO_DTE[id]];
      lines.push(
        `${v.name}: ${v.slope_decade?.toFixed(3)} ${v.units.slope_decade}, IC95 [${v.ci95?.map((x) => x.toFixed(3)).join(", ")}], p ajustado ${v.p_holm?.toExponential(2)}, ${v.significant ? "significativo" : "evidencia insuficiente"}`
      );
    }
    lines.push(...dte.joint.pairs_list.map((p) => `${p.pair}: r=${p.r?.toFixed(2)} (n=${p.n})`));
  }
  for (const r of Object.values(extras)) {
    if (typeof r === "string") continue;
    lines.push(`${r.metadatos.nombre_simple}: ${r.tendencia.pendiente_ols_decada?.toFixed(3)} ${r.metadatos.unidad_pendiente}, ${r.tendencia.veredicto}, ${r.tendencia.direccion}`);
  }
  const src = dte?.metadata.source ?? Object.values(extras).find((r): r is TendenciaRespuesta => typeof r !== "string")?.metadatos.fuente_datos;
  return `source=${src}; ${lines.join(" | ")}`;
}
