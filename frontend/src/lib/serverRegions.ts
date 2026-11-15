import type { BackendRegion } from "@/lib/api";

// Node resolves "localhost" to IPv6 first, while uvicorn listens on 127.0.0.1: use the IPv4 address.
const BACKEND = (process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000").replace("//localhost", "//127.0.0.1");
const TTL_MS = 5 * 60 * 1000;

let cache: { at: number; regions: BackendRegion[] } | null = null;

/** Official regions from the backend (server-side, cached 5 min). Empty when the backend is down. */
export async function backendRegions(): Promise<BackendRegion[]> {
  if (cache && Date.now() - cache.at < TTL_MS) return cache.regions;
  try {
    const res = await fetch(`${BACKEND}/api/v1/regiones`, { signal: AbortSignal.timeout(4000) });
    if (!res.ok) return cache?.regions ?? [];
    const data = (await res.json()) as { regiones?: BackendRegion[] };
    cache = { at: Date.now(), regions: data.regiones ?? [] };
    return cache.regions;
  } catch {
    return cache?.regions ?? [];
  }
}
