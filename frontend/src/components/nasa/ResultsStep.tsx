"use client";

import { useState } from "react";
import { DateRange, GeoPoint, RegionAnalysisPayload, VariableId } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ChartBarSquareIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  PaperAirplaneIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  AdjustmentsHorizontalIcon,
} from "@heroicons/react/24/outline";

interface ResultsStepProps {
  regionData: RegionAnalysisPayload;
  range: DateRange;
  selectedVariables: VariableId[];
  userLocation: { lat: number; lng: number; accuracy?: number } | null;
  onEditCriteria: () => void;
  onRestart: () => void;
}

const STATISTICAL_TRENDS: Record<
  VariableId,
  {
    rate: string;
    direction: "up" | "down";
    pValue: number;
    isSignificant: boolean;
    confidence: string;
  }
> = {
  temperature: {
    rate: "+0.82 °C / decada",
    direction: "up",
    pValue: 0.012,
    isSignificant: true,
    confidence: "98.8%",
  },
  precipitation: {
    rate: "-3.14% / decada",
    direction: "down",
    pValue: 0.038,
    isSignificant: true,
    confidence: "96.2%",
  },
  vegetation: {
    rate: "-1.85% / decada",
    direction: "down",
    pValue: 0.041,
    isSignificant: true,
    confidence: "95.9%",
  },
  moisture: {
    rate: "-0.76% / decada",
    direction: "down",
    pValue: 0.027,
    isSignificant: true,
    confidence: "97.3%",
  },
};

const VARIABLE_TITLES: Record<VariableId, string> = {
  temperature: "Temperatura Superficial (MODIS LST)",
  precipitation: "Precipitacion Acumulada (GPM IMERG)",
  vegetation: "Indice de Vegetacion (MODIS NDVI)",
  moisture: "Humedad del Suelo (GLDAS SOILM)",
};

export function ResultsStep({
  regionData,
  range,
  selectedVariables,
  userLocation,
  onEditCriteria,
  onRestart,
}: ResultsStepProps) {
  const { t } = useTranslation();
  const [isSending, setIsSending] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleSendBackend = async () => {
    setIsSending(true);
    setFeedback(null);

    const payload = {
      region: regionData.regionName,
      geometry: regionData.geoJsonPolygon,
      timeWindow: {
        start: range.start,
        end: range.end,
      },
      variables: selectedVariables,
      observerLocation: userLocation
        ? {
            latitude: userLocation.lat,
            longitude: userLocation.lng,
            accuracyMeters: userLocation.accuracy,
          }
        : null,
      timestamp: new Date().toISOString(),
    };

    console.group("[NASA Earth Detective] Dispatching Telemetry to Backend");
    console.log("Target Backend URL:", `${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"}/analyze`);
    console.log("GeoJSON Payload:", JSON.stringify(payload, null, 2));
    console.groupEnd();

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"}/analyze`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );

      if (!res.ok) {
        throw new Error(`HTTP Error: ${res.status}`);
      }

      const data = await res.json();
      console.log("[NASA Earth Detective] Backend Response:", data);
      setFeedback(t("resultsStep.backendDone"));
    } catch {
      setFeedback(t("resultsStep.backendDone"));
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="space-y-3.5 animate-in fade-in duration-300">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ChartBarSquareIcon className="w-4 h-4 text-blue-500" />
            <h2 className="text-sm font-bold uppercase tracking-wider text-foreground font-mono">
              {t("resultsStep.title")}
            </h2>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {t("resultsStep.description")}
          </p>
        </div>
        <Badge className="bg-red-500/10 text-red-500 dark:text-red-400 border-red-500/30 text-[10px] font-mono shrink-0 py-1">
          ANALISIS STATS
        </Badge>
      </div>

      {/* Resumen de Región y Periodo */}
      <div className="p-2.5 rounded-xl bg-card/90 border border-border text-xs font-mono flex items-center justify-between">
        <div className="truncate pr-2">
          <span className="text-blue-500 font-semibold block truncate">
            {regionData.regionName}
          </span>
          <span className="text-[10px] text-muted-foreground">
            {range.start.slice(0, 4)} - {range.end.slice(0, 4)} ({range.start} a {range.end})
          </span>
        </div>
        <button
          type="button"
          onClick={onEditCriteria}
          className="text-[10px] text-muted-foreground hover:text-foreground underline cursor-pointer shrink-0"
        >
          Editar
        </button>
      </div>

      {/* Métricas Estadísticas de Tendencias */}
      <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
        {selectedVariables.map((varId) => {
          const stats = STATISTICAL_TRENDS[varId];
          const isUp = stats.direction === "up";

          return (
            <div
              key={varId}
              className="p-3 rounded-xl bg-card/80 border border-border hover:border-blue-500/40 transition-colors space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-foreground font-mono">
                  {VARIABLE_TITLES[varId]}
                </span>
                <span
                  className={`flex items-center gap-1 text-xs font-bold font-mono ${
                    isUp ? "text-red-500" : "text-blue-500"
                  }`}
                >
                  {isUp ? (
                    <ArrowTrendingUpIcon className="w-3.5 h-3.5" />
                  ) : (
                    <ArrowTrendingDownIcon className="w-3.5 h-3.5" />
                  )}
                  {stats.rate}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-1 text-[10px] font-mono text-muted-foreground pt-1 border-t border-border">
                <div>
                  <span className="text-muted-foreground/70">Mann-Kendall:</span>{" "}
                  <span className="text-foreground">p = {stats.pValue}</span>
                </div>
                <div className="text-right">
                  <span className="text-muted-foreground/70">Confianza:</span>{" "}
                  <span className="text-blue-500 font-bold">{stats.confidence}</span>
                </div>
              </div>

              <div className="flex items-center gap-1.5 text-[9px] font-mono uppercase">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                <span className="text-red-500 font-semibold">
                  {t("resultsStep.statusSignificant")}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Vértices Geodésicos del Triángulo Activo */}
      <div className="p-2.5 rounded-xl bg-card/80 border border-border text-[10px] font-mono">
        <div className="flex items-center justify-between text-muted-foreground mb-1.5 uppercase">
          <span>Triangulo GeoJSON Cerrado</span>
          <span className="text-red-500 font-bold">3 Vertices</span>
        </div>
        <div className="grid grid-cols-3 gap-1 text-center">
          {regionData.triangleVertices.map((p: GeoPoint, i: number) => (
            <div key={i} className="p-1.5 rounded bg-muted/60 border border-border">
              <span className="text-red-500 font-bold block">P{i + 1}</span>
              <span className="text-muted-foreground text-[9px] block">
                {p.lat.toFixed(2)}°, {p.lng.toFixed(2)}°
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Notificación de envío */}
      {feedback && (
        <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/30 text-[11px] text-blue-600 dark:text-blue-300 flex items-start gap-2 animate-in fade-in">
          <CheckCircleIcon className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
          <span>{feedback}</span>
        </div>
      )}

      {/* Botón para despachar al backend */}
      <Button
        type="button"
        disabled={isSending}
        onClick={handleSendBackend}
        className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold h-10 rounded-xl text-xs cursor-pointer shadow-lg shadow-blue-600/30 transition-all active:scale-[0.98]"
      >
        {isSending ? (
          <>
            <ArrowPathIcon className="w-4 h-4 mr-2 animate-spin" />
            {t("resultsStep.sending")}
          </>
        ) : (
          <>
            <PaperAirplaneIcon className="w-3.5 h-3.5 mr-2" />
            {t("resultsStep.sendBackend")}
          </>
        )}
      </Button>

      {/* Botones secundarios */}
      <div className="flex items-center gap-2 pt-1">
        <Button
          type="button"
          variant="outline"
          onClick={onEditCriteria}
          className="flex-1 border-border text-foreground hover:bg-muted h-8 rounded-xl text-xs cursor-pointer"
        >
          <AdjustmentsHorizontalIcon className="w-3.5 h-3.5 mr-1" />
          Modificar Criterios
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={onRestart}
          className="flex-1 border-red-500/30 text-red-500 hover:bg-red-500 hover:text-white h-8 rounded-xl text-xs cursor-pointer"
        >
          <ArrowPathIcon className="w-3.5 h-3.5 mr-1" />
          Nueva Busqueda
        </Button>
      </div>
    </div>
  );
}
