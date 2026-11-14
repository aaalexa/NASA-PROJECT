"use client";

import { useState, useEffect } from "react";
import CobeGlobePulse from "@/components/globe/CobeGlobePulse";
import {
  DateRange,
  GeoPoint,
  PredefinedRegion,
  RegionAnalysisPayload,
  VariableId,
  WorkflowStep,
} from "@/types/geo";
import { VoiceController } from "@/components/hud/VoiceController";
import { StepNavigation } from "@/components/nasa/StepNavigation";
import { RegionStep } from "@/components/nasa/RegionStep";
import { PeriodStep } from "@/components/nasa/PeriodStep";
import { VariablesStep } from "@/components/nasa/VariablesStep";
import { ResultsStep } from "@/components/nasa/ResultsStep";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/context/LanguageContext";
import { useTheme } from "@/context/ThemeContext";
import {
  GlobeAmericasIcon,
  LanguageIcon,
  ArrowPathIcon,
  ViewfinderCircleIcon,
  ServerIcon,
  ChartBarIcon,
  SunIcon,
  MoonIcon,
} from "@heroicons/react/24/outline";

export default function HomePage() {
  const { language, toggleLanguage, t } = useTranslation();
  const { theme, toggleTheme } = useTheme();

  // Workflow state
  const [activeStep, setActiveStep] = useState<WorkflowStep>("region");
  const [points, setPoints] = useState<GeoPoint[]>([]);
  const [regionData, setRegionData] = useState<RegionAnalysisPayload | null>(null);
  const [dateRange, setDateRange] = useState<DateRange>({
    start: "2019-01-01",
    end: "2024-12-31",
    preset: "5y",
  });
  const [selectedVariables, setSelectedVariables] = useState<VariableId[]>([
    "temperature",
    "precipitation",
  ]);
  const [isSearchingText, setIsSearchingText] = useState(false);

  // User Geolocation tracking
  const [userLocation, setUserLocation] = useState<{
    lat: number;
    lng: number;
    accuracy?: number;
  } | null>(null);
  const [locationStatus, setLocationStatus] = useState<
    "locating" | "detected" | "denied" | "unsupported"
  >("locating");

  // Capturar y registrar la ubicación del usuario en consola (sin emojis)
  useEffect(() => {
    if (typeof window === "undefined" || !("geolocation" in navigator)) {
      setLocationStatus("unsupported");
      console.warn("[NASA Earth Detective] Geolocation API is not supported by this browser.");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const coords = {
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          accuracy: position.coords.accuracy,
        };
        setUserLocation(coords);
        setLocationStatus("detected");

        console.group("[NASA Earth Detective] User Geolocation Captured");
        console.log("Latitude:", coords.lat);
        console.log("Longitude:", coords.lng);
        console.log("Accuracy:", coords.accuracy ? `${coords.accuracy.toFixed(1)} meters` : "N/A");
        console.log("Timestamp:", new Date(position.timestamp).toISOString());
        console.log("Geodetic Reference: WGS 84");
        console.log("Status: Spatial Geospatial Correlation Active");
        console.groupEnd();
      },
      (error) => {
        setLocationStatus("denied");
        console.group("[NASA Earth Detective] Geolocation Notice");
        console.warn("User location permission status:", error.message);
        console.log("Operating under standard Earth orbital coordinates.");
        console.groupEnd();
      },
      {
        enableHighAccuracy: true,
        timeout: 12000,
        maximumAge: 60000,
      }
    );
  }, []);

  const handleRegionParsed = (data: RegionAnalysisPayload) => {
    setRegionData(data);
    setPoints(data.triangleVertices);

    console.group("[NASA Earth Detective] Region Triangle Generated");
    console.log("Region Name:", data.regionName);
    console.log("Description:", data.description);
    console.log("Vertices:", data.triangleVertices);
    console.log("GeoJSON Polygon:", data.geoJsonPolygon);
    console.log("Suggested Variables:", data.suggestedVariables);
    console.groupEnd();
  };

  const handleSelectPredefined = (reg: PredefinedRegion) => {
    const v = reg.triangle;
    const payload: RegionAnalysisPayload = {
      regionName: reg.name[language],
      description: `Analisis cientifico de tendencias para la zona de ${reg.name[language]} (${reg.area[language]}).`,
      triangleVertices: [v[0], v[1], v[2]],
      geoJsonPolygon: {
        type: "Polygon",
        coordinates: [
          [
            [v[0].lng, v[0].lat],
            [v[1].lng, v[1].lat],
            [v[2].lng, v[2].lat],
            [v[0].lng, v[0].lat],
          ],
        ],
      },
      suggestedVariables: [
        {
          id: "GPM_PRECIP",
          name: "Precipitacion (GPM)",
          simpleExplanation: "Mide acumulacion de precipitaciones para detectar sequias.",
        },
        {
          id: "MODIS_LST",
          name: "Temperatura Superficial (MODIS)",
          simpleExplanation: "Evalua anomalias termicas y estres de calor en ecosistemas.",
        },
      ],
    };

    handleRegionParsed(payload);
  };

  const handleManualSearch = async (queryText: string) => {
    setIsSearchingText(true);
    try {
      const res = await fetch("/api/parse-voice", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: queryText, locale: language }),
      });
      const data = await res.json();
      if (!data.error) {
        handleRegionParsed(data);
      } else {
        alert(data.error);
      }
    } catch (err) {
      console.error("[NASA Earth Detective] Search error:", err);
    } finally {
      setIsSearchingText(false);
    }
  };

  const toggleVariable = (id: VariableId) => {
    setSelectedVariables((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id]
    );
  };

  const resetAll = () => {
    setPoints([]);
    setRegionData(null);
    setActiveStep("region");
    setSelectedVariables(["temperature", "precipitation"]);
    setDateRange({ start: "2019-01-01", end: "2024-12-31", preset: "5y" });
  };

  // Coordenadas para visualización en el visor
  const centerLat =
    points.length > 0
      ? points.reduce((sum, p) => sum + p.lat, 0) / points.length
      : null;
  const centerLng =
    points.length > 0
      ? points.reduce((sum, p) => sum + p.lng, 0) / points.length
      : null;

  return (
    <main className="relative w-screen h-screen overflow-hidden bg-background text-foreground font-sans select-none transition-colors duration-300">
      {/* Globo 3D WebGL (cobe) con vértices rojos y aristas azules */}
      <CobeGlobePulse trianglePoints={points} />

      {/* Barra Superior - Header HUD de Misión */}
      <header className="fixed top-4 left-4 right-4 z-20 flex flex-wrap items-center justify-between gap-3 pointer-events-none">
        {/* Identidad de la estación */}
        <div className="pointer-events-auto flex items-center gap-3 bg-card/90 dark:bg-black/90 backdrop-blur-md border border-border px-4 py-2.5 rounded-2xl shadow-2xl transition-colors">
          <span className="flex h-2.5 w-2.5 rounded-full bg-blue-600 ring-4 ring-blue-600/30" />
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs sm:text-sm font-bold tracking-wider uppercase text-foreground font-mono">
                {t("system.name")}
              </span>
              <Badge
                variant="outline"
                className="text-[9px] bg-blue-500/10 dark:bg-blue-950/70 text-blue-600 dark:text-blue-400 border-blue-500/30 py-0 px-1.5 h-4 font-mono font-semibold"
              >
                {t("system.badge")}
              </Badge>
            </div>
            <p className="text-[10px] text-muted-foreground font-mono hidden sm:block">
              {t("system.subline")}
            </p>
          </div>
        </div>

        {/* Navegación por Pasos Centrada */}
        <div className="pointer-events-auto">
          <StepNavigation
            activeStep={activeStep}
            onSelectStep={setActiveStep}
            hasRegion={points.length === 3}
            hasVariables={selectedVariables.length > 0}
          />
        </div>

        {/* Acciones de Cabecera: Ubicación, Tema, Idioma, Reset */}
        <div className="pointer-events-auto flex items-center gap-2">
          {/* Geolocation del Detective */}
          <div className="hidden xl:flex items-center gap-1.5 bg-card/90 dark:bg-black/90 backdrop-blur-md border border-border px-3 py-1.5 rounded-xl text-[10px] text-muted-foreground font-mono transition-colors">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                userLocation ? "bg-blue-500 animate-pulse" : "bg-muted-foreground"
              }`}
            />
            {userLocation ? (
              <span>
                {t("header.userLocPrefix")}: {userLocation.lat.toFixed(2)}°, {userLocation.lng.toFixed(2)}°
              </span>
            ) : (
              <span>COORDENADAS ORBITALES</span>
            )}
          </div>

          {/* Selector de Modo Claro / Modo Oscuro */}
          <Button
            variant="outline"
            size="sm"
            onClick={toggleTheme}
            className="bg-card/90 dark:bg-black/90 border-border text-foreground hover:bg-muted h-9 px-3 rounded-xl cursor-pointer font-mono font-bold text-xs transition-colors"
            title={theme === "dark" ? "Cambiar a modo claro / Switch to light mode" : "Cambiar a modo oscuro / Switch to dark mode"}
            aria-label="Toggle theme"
          >
            {theme === "dark" ? (
              <SunIcon className="w-4 h-4 text-amber-400" />
            ) : (
              <MoonIcon className="w-4 h-4 text-blue-600" />
            )}
            <span className="hidden sm:inline text-[11px]">
              {theme === "dark" ? "CLARO" : "OSCURO"}
            </span>
          </Button>

          {/* Selector Bilingüe ES / EN */}
          <Button
            variant="outline"
            size="sm"
            onClick={toggleLanguage}
            className="bg-card/90 dark:bg-black/90 border-border text-foreground hover:bg-muted h-9 px-3 rounded-xl cursor-pointer font-mono font-bold text-xs transition-colors"
            title="Cambiar idioma / Switch language"
          >
            <LanguageIcon className="w-4 h-4 mr-1.5 text-blue-500" />
            <span>{t("header.langToggle")}</span>
          </Button>

          {/* Botón Reiniciar si hay datos activos */}
          {points.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={resetAll}
              className="bg-card/90 dark:bg-black/90 border-red-500/40 text-red-500 hover:bg-red-600 hover:text-white hover:border-red-600 h-9 px-3 rounded-xl cursor-pointer text-xs font-mono transition-all"
            >
              <ArrowPathIcon className="w-3.5 h-3.5 mr-1" />
              <span>{t("header.clearButton")}</span>
            </Button>
          )}
        </div>
      </header>

      {/* Panel Lateral de Trabajo Científico (Workflow) */}
      <section className="fixed top-20 left-4 z-20 w-[92vw] max-w-[400px] max-h-[calc(100vh-145px)] overflow-y-auto bg-card/90 dark:bg-black/90 backdrop-blur-md border border-border p-4 text-foreground rounded-2xl shadow-2xl transition-colors">
        {activeStep === "region" && (
          <RegionStep
            regionData={regionData}
            onSelectPredefined={handleSelectPredefined}
            onSearchManual={handleManualSearch}
            isSearching={isSearchingText}
            onContinue={() => setActiveStep("period")}
          />
        )}

        {activeStep === "period" && (
          <PeriodStep
            range={dateRange}
            onChangeRange={setDateRange}
            onBack={() => setActiveStep("region")}
            onContinue={() => setActiveStep("variables")}
          />
        )}

        {activeStep === "variables" && (
          <VariablesStep
            selected={selectedVariables}
            onToggleVariable={toggleVariable}
            onBack={() => setActiveStep("period")}
            onContinue={() => setActiveStep("results")}
          />
        )}

        {activeStep === "results" && regionData && (
          <ResultsStep
            regionData={regionData}
            range={dateRange}
            selectedVariables={selectedVariables}
            userLocation={userLocation}
            onEditCriteria={() => setActiveStep("variables")}
            onRestart={resetAll}
          />
        )}
      </section>

      {/* Rótulo Geodésico Flotante sobre el Globo */}
      {points.length === 3 && centerLat !== null && centerLng !== null && (
        <div className="fixed top-20 right-4 z-10 hidden sm:flex flex-col gap-1.5 pointer-events-none">
          <div className="bg-card/85 dark:bg-black/85 backdrop-blur-md border border-border px-3 py-1.5 rounded-xl text-[10px] font-mono text-foreground transition-colors">
            <span className="text-red-500 font-bold mr-1">LAT:</span>
            {Math.abs(centerLat).toFixed(2)}° {centerLat >= 0 ? "N" : "S"}
          </div>
          <div className="bg-card/85 dark:bg-black/85 backdrop-blur-md border border-border px-3 py-1.5 rounded-xl text-[10px] font-mono text-foreground transition-colors">
            <span className="text-blue-500 font-bold mr-1">LON:</span>
            {Math.abs(centerLng).toFixed(2)}° {centerLng >= 0 ? "E" : "W"}
          </div>
        </div>
      )}

      {/* Control de Voz Principal */}
      <VoiceController onRegionParsed={handleRegionParsed} />

      {/* Barra Inferior Derecha de Telemetría */}
      <footer className="fixed bottom-4 right-4 z-10 hidden lg:flex items-center gap-3 bg-card/90 dark:bg-black/90 backdrop-blur-md border border-border px-3 py-1.5 rounded-xl text-[10px] font-mono text-muted-foreground select-none transition-colors">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
          <span>{t("globe.resolution")}</span>
        </div>
        <div className="w-px h-3 bg-border" />
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
          <span>DATUM: WGS 84</span>
        </div>
        <div className="w-px h-3 bg-border" />
        <div className="flex items-center gap-1.5">
          <ServerIcon className="w-3 h-3 text-muted-foreground" />
          <span>STAC API / FASTAPI READY</span>
        </div>
      </footer>
    </main>
  );
}
