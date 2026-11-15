"use client";

import { useEffect, useMemo, useState } from "react";
import { useBackend } from "@/context/BackendContext";
import {
  ApiFailure,
  DataMode,
  DteJob,
  DteResult,
  ID_TO_DTE,
  TendenciaRespuesta,
  classifyError,
  dteParams,
  failureDetail,
  fetchDteResult,
  fetchTendencia,
  runDteJob,
} from "@/lib/api";
import type { DateRange, RegionAnalysisPayload, VariableId } from "@/types/geo";

export interface AnalysisOutcome {
  key: string;
  /** Down to Earth analysis (only when at least one of P, T, SM, ET is selected). */
  dte?: DteResult;
  /** Per-variable trend for every selected variable outside that family. */
  extras: Record<string, TendenciaRespuesta | ApiFailure>;
  /** True while the extra variables are still loading (the Down to Earth result is already shown). */
  extrasPending?: boolean;
  failure?: ApiFailure;
  /** Backend text for the failure when it gave one (e.g. why a real-data job failed). */
  failureText?: string;
  /** Id of the real-data job that produced `dte` (for its formatted tables). */
  jobId?: string;
}

/** Result of an uploaded CSV (`POST /calcular/csv`): replaces the region view until the user goes back. */
export interface UploadedAnalysis {
  key: string;
  fileName: string;
  result: DteResult;
}

/**
 * Everything the analysis screens need from the backend for the current selection:
 * the joint Down to Earth result for P/T/SM/ET plus one trend per other variable.
 *
 * Data modes:
 * - "sintetico": deterministic demo data from the backend.
 * - "memoria": only what is already in the server RAM (404 otherwise, never a silent synthetic fallback).
 * - "descargar": real NASA data. First the server RAM (instant if precomputed); if absent, a background job
 *   (`POST /down-to-earth/trabajos`) downloads and analyses the region while this hook reports its progress.
 */
export function useAnalysisData(regionData: RegionAnalysisPayload | null, range: DateRange, selected: VariableId[], enabled = true) {
  const backend = useBackend();
  const [modeOverride, setModeOverride] = useState<DataMode | null>(null);
  const [outcome, setOutcome] = useState<AnalysisOutcome | null>(null);
  const [jobProgress, setJobProgress] = useState<{ key: string; job: DteJob } | null>(null);
  const [uploadedState, setUploadedState] = useState<UploadedAnalysis | null>(null);
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
    const signal = ctrl.signal;

    const loadDte = async (): Promise<Pick<AnalysisOutcome, "dte" | "failure" | "failureText" | "jobId">> => {
      if (!coreIds.length) return {};
      try {
        if (request.mode !== "descargar") return { dte: await fetchDteResult({ ...request, signal }) };
        // Real data: the server RAM first (precomputed or an earlier job), then a background job with progress.
        try {
          return { dte: await fetchDteResult({ ...request, mode: "memoria", signal }) };
        } catch (e) {
          if (classifyError(e) !== "no_data_in_memory") throw e;
        }
        const { result, job } = await runDteJob(request, (j) => setJobProgress({ key, job: j }), signal);
        return { dte: result, jobId: job.id };
      } catch (e) {
        return { failure: classifyError(e), failureText: failureDetail(e) };
      }
    };

    const run = async () => {
      const extraPromises = extraIds.map((id) =>
        fetchTendencia(id, { ...request, signal }).then(
          (r): [string, TendenciaRespuesta | ApiFailure] => [id, r],
          (e): [string, TendenciaRespuesta | ApiFailure] => [id, classifyError(e)]
        )
      );
      const dtePart = await loadDte();
      if (signal.aborted || dtePart.failure === "aborted") return;
      // Show the Down to Earth result as soon as it is ready; the other variables follow.
      if (coreIds.length && extraIds.length) setOutcome({ key, ...dtePart, extras: {}, extrasPending: true });
      const extras = Object.fromEntries(await Promise.all(extraPromises));
      if (signal.aborted) return;
      setOutcome({ key, ...dtePart, extras });
    };
    void run();
    return () => ctrl.abort();
    // `key` already captures the request and the selection; re-run only when it changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, ready]);

  const current = outcome?.key === key ? outcome : undefined;
  const uploaded = uploadedState?.key === key ? uploadedState : undefined;
  const extras = uploaded ? {} : (current?.extras ?? {});
  const dte = uploaded ? uploaded.result : current?.dte;
  const job = !uploaded && loading && jobProgress?.key === key ? jobProgress.job : undefined;
  const anyResult = Boolean(dte) || Object.values(extras).some((r) => typeof r !== "string");
  const synthetic =
    Boolean(dte?.metadata.simulated) ||
    dte?.metadata.source === "sintetico" ||
    Object.values(extras).some((r) => typeof r !== "string" && r.metadatos.fuente_datos === "sintetico");

  return {
    mode,
    setModeOverride,
    retry: () => {
      backend.recheck();
      setAttempt((a) => a + 1);
    },
    loading: !uploaded && (loading || (enabled && backend.state === "checking")),
    current,
    dte,
    extras,
    extrasPending: !uploaded && Boolean(current?.extrasPending),
    failure: uploaded ? undefined : current?.failure,
    failureText: uploaded ? undefined : current?.failureText,
    /** Progress of the real-data job while it runs. */
    job,
    /** Id of the finished real-data job behind `dte` (formatted tables: mensual, anual, limpieza, diccionario). */
    jobId: uploaded ? undefined : current?.jobId,
    /** The uploaded CSV currently shown instead of the region, if any. */
    uploaded,
    setUploaded: (result: DteResult | null, fileName = "") =>
      setUploadedState(result ? { key, fileName, result } : null),
    anyResult,
    synthetic,
    coreIds,
    extraIds,
  };
}
