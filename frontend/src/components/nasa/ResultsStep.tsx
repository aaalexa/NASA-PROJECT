"use client";

import { useState } from "react";
import { DateRange, GeoPoint, RegionAnalysisPayload, VariableId } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";
import { VARIABLES } from "@/lib/catalog";
import { ArrowTrendingDownIcon, ArrowTrendingUpIcon } from "@heroicons/react/24/outline";

interface ResultsStepProps {
  regionData: RegionAnalysisPayload;
  range: DateRange;
  selectedVariables: VariableId[];
  userLocation: { lat: number; lng: number; accuracy?: number } | null;
  onEditCriteria: () => void;
  onRestart: () => void;
  readOnly?: boolean;
}

// Illustrative values taken from the project guide (section 03.2). NOT computed from data.
const ILLUSTRATIVE: Record<VariableId, { slope: number; ci: [number, number]; pHolm: number; decimals: number; unit: string }> = {
  precipitation: { slope: -20, ci: [-32, -8], pHolm: 0.012, decimals: 0, unit: "mm" },
  temperature: { slope: 0.3, ci: [0.1, 0.5], pHolm: 0.054, decimals: 1, unit: "°C" },
  moisture: { slope: -0.01, ci: [-0.025, 0.005], pHolm: 0.24, decimals: 3, unit: "m³/m³" },
  evapotranspiration: { slope: 8, ci: [-10, 26], pHolm: 0.4, decimals: 0, unit: "mm" },
  vegetation: { slope: -0.02, ci: [-0.04, 0.0], pHolm: 0.09, decimals: 2, unit: "NDVI" },
};

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export function ResultsStep({ regionData, range, selectedVariables, userLocation, onEditCriteria, onRestart, readOnly }: ResultsStepProps) {
  const { language, t } = useTranslation();
  const [isSending, setIsSending] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string } | null>(null);

  const sign = (n: number, d: number) => `${n > 0 ? "+" : ""}${n.toFixed(d)}`;

  const handleSendBackend = async () => {
    setIsSending(true);
    setFeedback(null);
    const payload = {
      region: regionData.regionName,
      geometry: regionData.geoJsonPolygon,
      timeWindow: { start: range.start, end: range.end },
      variables: selectedVariables,
      observerLocation: userLocation
        ? { latitude: userLocation.lat, longitude: userLocation.lng, accuracyMeters: userLocation.accuracy }
        : null,
      timestamp: new Date().toISOString(),
    };
    try {
      const res = await fetch(`${BACKEND_URL}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setFeedback({ ok: true, text: t("resultsStep.sent") });
    } catch {
      setFeedback({ ok: false, text: t("resultsStep.sendFailed").replace("{url}", BACKEND_URL) });
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="space-y-5 animate-in fade-in duration-300">
      <div>
        <h2 className="title text-lg">{t("resultsStep.title")}</h2>
        <p className="mt-1.5 text-sm text-muted-foreground">{t("resultsStep.description")}</p>
      </div>

      <div className="flex items-start justify-between gap-3 border-l-2 border-primary/70 pl-3">
        <div className="min-w-0">
          <p className="eyebrow">{t("resultsStep.region")}</p>
          <p className="mt-1 truncate text-sm font-bold">{regionData.regionName}</p>
          <p className="text-xs text-muted-foreground tabular-nums">
            {range.start.slice(0, 4)} – {range.end.slice(0, 4)}
          </p>
        </div>
        {!readOnly && (
          <button type="button" onClick={onEditCriteria} className="shrink-0 cursor-pointer text-xs underline underline-offset-4 hover:text-primary">
            {t("resultsStep.edit")}
          </button>
        )}
      </div>

      <ul className="max-h-[38vh] space-y-2 overflow-y-auto pr-1">
        {selectedVariables.map((id) => {
          const s = ILLUSTRATIVE[id];
          const up = s.slope > 0;
          const significant = s.pHolm <= 0.05;
          const Arrow = up ? ArrowTrendingUpIcon : ArrowTrendingDownIcon;
          return (
            <li key={id} className="border border-border p-3" style={{ borderRadius: 16 }}>
              <div className="flex items-start justify-between gap-3">
                <span className="text-sm font-bold">{VARIABLES[id].name[language]}</span>
                <span className={`flex items-center gap-1 text-sm font-bold tabular-nums ${up ? "text-brand-red" : "text-primary"}`}>
                  <Arrow className="h-4 w-4" />
                  {sign(s.slope, s.decimals)} {s.unit}
                </span>
              </div>
              <p className="mt-0.5 text-right text-[11px] text-muted-foreground">{t("resultsStep.perDecade")}</p>
              <div className="mt-2 flex items-center justify-between border-t border-border pt-2 text-xs text-muted-foreground tabular-nums">
                <span>
                  {t("resultsStep.ci")} [{sign(s.ci[0], s.decimals)}, {sign(s.ci[1], s.decimals)}]
                </span>
                <span>
                  {t("resultsStep.pAdj")} {s.pHolm}
                </span>
              </div>
              <p className={`mt-1.5 flex items-center gap-1.5 text-xs font-medium ${significant ? "text-brand-red" : "text-muted-foreground"}`}>
                <span className={`inline-block h-1.5 w-1.5 ${significant ? "bg-brand-red" : "bg-muted-foreground"}`} />
                {significant ? t("resultsStep.significant") : t("resultsStep.insufficient")}
              </p>
            </li>
          );
        })}
      </ul>

      <p className="text-xs leading-relaxed text-muted-foreground">
        {t("resultsStep.illustrative")} {t("resultsStep.limits")}
      </p>

      <details className="text-xs">
        <summary className="eyebrow cursor-pointer">{t("resultsStep.vertices")}</summary>
        <div className="mt-2 grid grid-cols-3 gap-2 tabular-nums">
          {regionData.triangleVertices.map((p: GeoPoint, i: number) => (
            <div key={i} className="border border-border p-2" style={{ borderRadius: 16 }}>
              <span className="font-bold text-brand-red">P{i + 1}</span>
              <span className="block text-muted-foreground">
                {p.lat.toFixed(2)}°, {p.lng.toFixed(2)}°
              </span>
            </div>
          ))}
        </div>
      </details>

      {feedback && (
        <p role="status" className={`text-xs ${feedback.ok ? "text-primary" : "text-brand-red"}`}>
          {feedback.text}
        </p>
      )}

      {!readOnly && (
        <div className="space-y-2">
          <button type="button" className="btn btn-primary w-full" disabled={isSending} onClick={handleSendBackend}>
            {isSending ? t("resultsStep.sending") : t("resultsStep.send")}
          </button>
          <div className="flex gap-2">
            <button type="button" className="btn btn-line flex-1" onClick={onEditCriteria}>
              {t("resultsStep.modify")}
            </button>
            <button type="button" className="btn btn-red flex-1" onClick={onRestart}>
              {t("resultsStep.restart")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
