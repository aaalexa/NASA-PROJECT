"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiError, BACKEND_URL, BackendRegion, BackendVariable, Catalogo, DataMode, fetchCatalogo, fetchSalud } from "@/lib/api";

export type BackendState = "checking" | "online" | "offline";

/**
 * Why the backend could not be used:
 * - `network`: no answer at all (server down, wrong URL, CORS or mixed content).
 * - `http`: the server answered with an error status.
 * - `invalid`: something answered, but it is not the Moody Trends API (wrong URL pointing elsewhere).
 */
export interface BackendFailure {
  kind: "network" | "http" | "invalid";
  status?: number;
}

/** Thrown when the URL answers but the payload is not our catalog. */
class InvalidBackendError extends Error {
  constructor() {
    super("Unexpected response: not the Moody Trends API");
    this.name = "InvalidBackendError";
  }
}

export interface BackendInfo {
  state: BackendState;
  /** NASA Earthdata credentials are configured on the server, so live OPeNDAP queries can work. */
  earthdata: boolean;
  /** Every variable the backend serves (analysable or not). */
  variables: BackendVariable[];
  /** Variables the UI can analyse (`analizable`). */
  analyzable: BackendVariable[];
  variableById: (id: string) => BackendVariable | undefined;
  regions: BackendRegion[];
  /** Period every source covers, e.g. ["2001-01", "2024-12"]. */
  period: [string, string];
  /** Data mode the results screen should request by default. */
  defaultMode: DataMode;
  /** Last failure, kept while a retry is in flight; null once the backend answers correctly. */
  failure: BackendFailure | null;
  /** Backend base URL the app is configured with (NEXT_PUBLIC_BACKEND_URL). */
  url: string;
  recheck: () => void;
}

/** Only used until the first answer arrives; the real period comes from the backend. */
const FALLBACK_PERIOD: [string, string] = ["2001-01", "2024-12"];
const FORCED = process.env.NEXT_PUBLIC_DATA_MODE as DataMode | undefined;

const BackendContext = createContext<BackendInfo | undefined>(undefined);

/**
 * Loads the backend once (health + catalog): variables, regions and periods all come from
 * `GET /api/v1/catalogo`. Without Earthdata credentials the server cannot download NASA data, so
 * the default data mode is the deterministic synthetic one.
 */
export function BackendProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<BackendState>("checking");
  const [earthdata, setEarthdata] = useState(false);
  const [catalogo, setCatalogo] = useState<Catalogo | null>(null);
  const [failure, setFailure] = useState<BackendFailure | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    const ctrl = new AbortController();
    Promise.all([fetchSalud(ctrl.signal), fetchCatalogo(ctrl.signal)])
      .then(([salud, cat]) => {
        // Validate the shape: a wrong URL can answer 200 with something else (HTML, another API).
        if (!cat || !Array.isArray(cat.variables) || !Array.isArray(cat.regiones)) throw new InvalidBackendError();
        setEarthdata(Boolean(salud?.credenciales_earthdata?.listo));
        setCatalogo(cat);
        setFailure(null);
        setState("online");
      })
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setFailure(
          e instanceof ApiError
            ? { kind: "http", status: e.status }
            : e instanceof InvalidBackendError
              ? { kind: "invalid" }
              : { kind: "network" }
        );
        setState((cur) => (cur === "online" ? cur : "offline"));
      });
    return () => ctrl.abort();
  }, [nonce]);

  const recheck = useCallback(() => {
    setState((cur) => (cur === "online" ? cur : "checking"));
    setNonce((n) => n + 1);
  }, []);

  const value = useMemo<BackendInfo>(() => {
    const variables = catalogo?.variables ?? [];
    const byId = new Map(variables.map((v) => [v.id, v]));
    return {
      state,
      earthdata,
      variables,
      analyzable: variables.filter((v) => v.analizable),
      variableById: (id) => byId.get(id),
      regions: catalogo?.regiones ?? [],
      period: catalogo?.periodos?.comun ?? FALLBACK_PERIOD,
      defaultMode: FORCED ?? (earthdata ? "descargar" : "sintetico"),
      failure,
      url: BACKEND_URL,
      recheck,
    };
  }, [state, earthdata, catalogo, failure, recheck]);

  return <BackendContext.Provider value={value}>{children}</BackendContext.Provider>;
}

export function useBackend(): BackendInfo {
  const ctx = useContext(BackendContext);
  if (!ctx) throw new Error("useBackend must be used within a BackendProvider");
  return ctx;
}
