"use client";

import { useEffect, useMemo, useState } from "react";
import { useBackend } from "@/context/BackendContext";
import {
  ApiFailure,
  DataMode,
  DteResult,
  ID_TO_DTE,
  TendenciaRespuesta,
  classifyError,
  dteParams,
  fetchDteResult,
  fetchTendencia,
} from "@/lib/api";
import type { DateRange, RegionAnalysisPayload, VariableId } from "@/types/geo";

export interface AnalysisOutcome {
  key: string;
  /** Down to Earth analysis (only when at least one of P, T, SM, ET is selected). */
  dte?: DteResult;
  /** Per-variable trend for every selected variable outside that family. */
  extras: Record<string, TendenciaRespuesta | ApiFailure>;
  failure?: ApiFailure;
}

/**
 * Everything the analysis screens need from the backend for the current selection:
 * the joint Down to Earth result for P/T/SM/ET plus one trend per other variable.
 */
export function useAnalysisData(regionData: RegionAnalysisPayload | null, range: DateRange, selected: VariableId[], enabled = true) {
  const backend = useBackend();
  const [modeOverride, setModeOverride] = useState<DataMode | null>(null);
  const [outcome, setOutcome] = useState<AnalysisOutcome | null>(null);
  const [attempt, setAttempt] = useState(0);

  const mode: DataMode = modeOverride ?? backend.defaultMode;
  const coreIds = selected.filter((id) => ID_TO_DTE[id]);
  const extraIds = selected.filter((id) => !ID_TO_DTE[id] && backend.variableById(id));

  const request = useMemo(
    () => (regionData ? { region: regionData, inicio: range.start, fin: range.end, mode } : null),
    [regionData, range.start, range.end, mode]
  );
  const key = request ? `${JSON.stringify(dteParams(request))}|${coreIds.join(",")}|${extraIds.join(",")}#${attempt}` : "";
  const ready = enabled && backend.state !== "checking" && request !== null;
  const loading = ready && outcome?.key !== key;

  useEffect(() => {
    if (!ready || !request) return;
    const ctrl = new AbortController();
    const run = async () => {
      const dtePromise = coreIds.length ? fetchDteResult({ ...request, signal: ctrl.signal }) : Promise.resolve(undefined);
      const extraPromises = extraIds.map((id) =>
        fetchTendencia(id, { ...request, signal: ctrl.signal }).then(
          (r): [string, TendenciaRespuesta | ApiFailure] => [id, r],
          (e): [string, TendenciaRespuesta | ApiFailure] => [id, classifyError(e)]
        )
      );
      let dte: DteResult | undefined;
      let failure: ApiFailure | undefined;
      try {
        dte = await dtePromise;
      } catch (e) {
        failure = classifyError(e);
      }
      const extras = Object.fromEntries(await Promise.all(extraPromises));
      if (ctrl.signal.aborted || failure === "aborted") return;
      setOutcome({ key, dte, extras, failure });
    };
    void run();
    return () => ctrl.abort();
    // `key` already captures the request and the selection; re-run only when it changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, ready]);

  const current = outcome?.key === key ? outcome : undefined;
  const extras = current?.extras ?? {};
  const anyResult = Boolean(current?.dte) || Object.values(extras).some((r) => typeof r !== "string");
  const synthetic =
    current?.dte?.metadata.source === "sintetico" ||
    Object.values(extras).some((r) => typeof r !== "string" && r.metadatos.fuente_datos === "sintetico");

  return {
    mode,
    setModeOverride,
    retry: () => {
      backend.recheck();
      setAttempt((a) => a + 1);
    },
    loading: loading || (enabled && backend.state === "checking"),
    current,
    dte: current?.dte,
    extras,
    failure: current?.failure,
    anyResult,
    synthetic,
    coreIds,
    extraIds,
  };
}
