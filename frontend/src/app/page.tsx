"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowPathIcon,
  MoonIcon,
  SpeakerWaveIcon,
  SpeakerXMarkIcon,
  SunIcon,
  UserCircleIcon,
} from "@heroicons/react/24/outline";
import CobeGlobePulse from "@/components/globe/CobeGlobePulse";
import { VoiceController } from "@/components/hud/VoiceController";
import { ExperienceModal } from "@/components/onboarding/ExperienceModal";
import { GuidedFlow, GuidedStage } from "@/components/guided/GuidedFlow";
import { StepNavigation } from "@/components/nasa/StepNavigation";
import { RegionStep } from "@/components/nasa/RegionStep";
import { PeriodStep } from "@/components/nasa/PeriodStep";
import { VariablesStep } from "@/components/nasa/VariablesStep";
import { ResultsStep } from "@/components/nasa/ResultsStep";
import { PREDEFINED_REGIONS } from "@/components/nasa/PredefinedRegions";
import { PERIODS } from "@/lib/catalog";
import { DEMOS, DemoDef, DemoStep } from "@/lib/demos";
import { useSpeak } from "@/hooks/useSpeak";
import { useTranslation } from "@/context/LanguageContext";
import { useTheme } from "@/context/ThemeContext";
import type {
  AppPhase,
  DateRange,
  Experience,
  GeoPoint,
  PredefinedRegion,
  RegionAnalysisPayload,
  VariableId,
  WorkflowStep,
} from "@/types/geo";

const DEFAULT_RANGE: DateRange = { start: "2019-01-01", end: "2024-12-31", preset: "5y" };
const DEFAULT_VARIABLES: VariableId[] = ["precipitation", "temperature"];

interface DemoState {
  def: DemoDef;
  index: number;
  finished: boolean;
}

function buildPayload(name: string, description: string, v: [GeoPoint, GeoPoint, GeoPoint]): RegionAnalysisPayload {
  return {
    regionName: name,
    description,
    triangleVertices: v,
    geoJsonPolygon: {
      type: "Polygon",
      coordinates: [[[v[0].lng, v[0].lat], [v[1].lng, v[1].lat], [v[2].lng, v[2].lat], [v[0].lng, v[0].lat]]],
    },
    suggestedVariables: [],
  };
}

export default function HomePage() {
  const { language, toggleLanguage, t } = useTranslation();
  const { theme, toggleTheme } = useTheme();
  const speech = useSpeak(language);

  const [phase, setPhase] = useState<AppPhase>("onboarding");
  const [activeStep, setActiveStep] = useState<WorkflowStep>("region");
  const [points, setPoints] = useState<GeoPoint[]>([]);
  const [regionData, setRegionData] = useState<RegionAnalysisPayload | null>(null);
  const [dateRange, setDateRange] = useState<DateRange>(DEFAULT_RANGE);
  const [selectedVariables, setSelectedVariables] = useState<VariableId[]>(DEFAULT_VARIABLES);
  const [isSearching, setIsSearching] = useState(false);

  const voiceHandlerRef = useRef<((text: string) => void) | null>(null);
  const registerVoice = useCallback((fn: ((text: string) => void) | null) => {
    voiceHandlerRef.current = fn;
  }, []);
  const demoTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [hint, setHint] = useState<string | undefined>();
  const [flash, setFlash] = useState<string | null>(null);

  const [demo, setDemo] = useState<DemoState | null>(null);
  const [guidedKey, setGuidedKey] = useState(0);
  const [guidedStart, setGuidedStart] = useState<GuidedStage>("intro");

  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number; accuracy?: number } | null>(null);

  // Observer geolocation (used only as context for the analysis payload).
  useEffect(() => {
    if (typeof navigator === "undefined" || !("geolocation" in navigator)) return;
    navigator.geolocation.getCurrentPosition(
      (p) => setUserLocation({ lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy }),
      () => undefined,
      { enableHighAccuracy: false, timeout: 12000, maximumAge: 60000 }
    );
  }, []);

  useEffect(() => {
    if (!flash) return;
    const id = setTimeout(() => setFlash(null), 4500);
    return () => clearTimeout(id);
  }, [flash]);

  // ---- Region handling ------------------------------------------------------------------

  const applyRegion = useCallback((data: RegionAnalysisPayload) => {
    setRegionData(data);
    setPoints(data.triangleVertices);
  }, []);

  const selectPredefined = useCallback(
    (reg: PredefinedRegion) => applyRegion(buildPayload(reg.name[language], reg.area[language], reg.triangle)),
    [applyRegion, language]
  );

  const searchRegion = useCallback(
    async (text: string): Promise<boolean> => {
      setIsSearching(true);
      try {
        const res = await fetch("/api/parse-voice", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt: text, locale: language }),
        });
        if (!res.ok) return false;
        applyRegion(await res.json());
        return true;
      } catch {
        return false;
      } finally {
        setIsSearching(false);
      }
    },
    [applyRegion, language]
  );

  // ---- Voice ------------------------------------------------------------------------------

  const handleTranscript = useCallback(
    (text: string) => {
      if (phase === "expert") {
        setActiveStep("region");
        void searchRegion(text).then((ok) => !ok && setFlash(t("regionStep.notFound")));
      } else {
        voiceHandlerRef.current?.(text);
      }
    },
    [phase, searchRegion, t]
  );

  // ---- Mode ---------------------------------------------------------------------------------

  const resetAll = () => {
    clearDemoTimer();
    setDemo(null);
    setPoints([]);
    setRegionData(null);
    setActiveStep("region");
    setSelectedVariables(DEFAULT_VARIABLES);
    setDateRange(DEFAULT_RANGE);
    setGuidedStart("intro");
    setGuidedKey((k) => k + 1);
  };

  const chooseExperience = (level: Experience) => {
    clearDemoTimer();
    setDemo(null);
    speech.setEnabled(level === "novice");
    setPhase(level === "novice" ? "guided" : "expert");
    setActiveStep("region");
    setGuidedStart("intro");
    setGuidedKey((k) => k + 1);
  };

  const changeMode = () => {
    speech.cancel();
    clearDemoTimer();
    setDemo(null);
    setPhase("onboarding");
  };

  // ---- Demo runner --------------------------------------------------------------------------

  const applyDemoStep = useCallback(
    (step: DemoStep) => {
      if (step.region) {
        const reg = PREDEFINED_REGIONS.find((r) => r.id === step.region);
        if (reg) selectPredefined(reg);
      }
      if (step.preset) {
        const p = PERIODS.find((x) => x.id === step.preset);
        if (p) setDateRange({ start: p.start, end: p.end, preset: p.id });
      }
      if (step.variables) setSelectedVariables(step.variables);
      if (step.step) setActiveStep(step.step);
    },
    [selectPredefined]
  );

  const clearDemoTimer = () => {
    if (demoTimer.current) clearTimeout(demoTimer.current);
    demoTimer.current = null;
  };

  useEffect(() => clearDemoTimer, []);

  const runDemoStep = (def: DemoDef, index: number) => {
    const step = def.steps[index];
    applyDemoStep(step);
    speech.speak(step.caption[language]);
    setDemo({ def, index, finished: false });
    demoTimer.current = setTimeout(() => {
      if (index + 1 >= def.steps.length) setDemo({ def, index, finished: true });
      else runDemoStep(def, index + 1);
    }, step.duration);
  };

  const startDemo = (id: string) => {
    const def = DEMOS.find((d) => d.id === id);
    if (!def) return;
    clearDemoTimer();
    setPoints([]);
    setRegionData(null);
    runDemoStep(def, 0);
  };

  const stopDemo = () => {
    speech.cancel();
    clearDemoTimer();
    setDemo(null);
    setGuidedStart("intro");
    setGuidedKey((k) => k + 1);
    setActiveStep("region");
  };

  const tryItYourself = () => {
    speech.cancel();
    clearDemoTimer();
    setDemo(null);
    setPoints([]);
    setRegionData(null);
    setActiveStep("region");
    setGuidedStart("topic");
    setGuidedKey((k) => k + 1);
  };

  // ---- Rendering ----------------------------------------------------------------------------

  const toggleVariable = (id: VariableId) =>
    setSelectedVariables((cur) => (cur.includes(id) ? cur.filter((v) => v !== id) : [...cur, id]));

  const renderStep = (readOnly = false) => (
    <>
      {activeStep === "region" && (
        <RegionStep
          regionData={regionData}
          onSelectPredefined={selectPredefined}
          onSearchManual={searchRegion}
          isSearching={isSearching}
          onContinue={() => setActiveStep("period")}
        />
      )}
      {activeStep === "period" && (
        <PeriodStep range={dateRange} onChangeRange={setDateRange} onBack={() => setActiveStep("region")} onContinue={() => setActiveStep("variables")} />
      )}
      {activeStep === "variables" && (
        <VariablesStep selected={selectedVariables} onToggleVariable={toggleVariable} onBack={() => setActiveStep("period")} onContinue={() => setActiveStep("results")} />
      )}
      {activeStep === "results" && regionData && (
        <ResultsStep
          regionData={regionData}
          range={dateRange}
          selectedVariables={selectedVariables}
          userLocation={userLocation}
          readOnly={readOnly}
          onEditCriteria={() => (phase === "guided" ? (setGuidedStart("suggest"), setGuidedKey((k) => k + 1), setActiveStep("region")) : setActiveStep("variables"))}
          onRestart={resetAll}
        />
      )}
    </>
  );

  const centerLat = points.length ? points.reduce((s, p) => s + p.lat, 0) / points.length : null;
  const centerLng = points.length ? points.reduce((s, p) => s + p.lng, 0) / points.length : null;

  const showNav = phase === "expert" || (phase === "guided" && demo !== null);
  const currentStepDef = demo ? demo.def.steps[demo.index] : null;

  const voiceHint =
    phase === "onboarding" ? undefined : phase === "expert" ? t("regionStep.hint") : hint;

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-background text-foreground">
      <CobeGlobePulse trianglePoints={points} />

      {/* Header */}
      <header className="pointer-events-none fixed left-4 right-4 top-4 z-30 flex items-center justify-between gap-3">
        <div className="pointer-events-auto flex items-center gap-2.5">
          <span className="h-3 w-3 rounded-full bg-brand-red" aria-hidden />
          <span className="text-sm font-bold tracking-tight">{t("system.name")}</span>
          <span className="eyebrow hidden md:inline">{t("system.badge")}</span>
        </div>

        {showNav && (
          <div className="pointer-events-auto absolute left-1/2 hidden -translate-x-1/2 sm:block">
            <StepNavigation activeStep={activeStep} onSelectStep={setActiveStep} hasRegion={points.length === 3} hasVariables={selectedVariables.length > 0} readOnly={demo !== null} />
          </div>
        )}

        <div className="pointer-events-auto flex items-center gap-2">
          {phase !== "onboarding" && (
            <button type="button" className="icon-btn !w-auto gap-1.5 px-3 text-xs font-medium" onClick={changeMode}>
              <UserCircleIcon className="h-4 w-4" />
              <span className="hidden md:inline">{t("header.changeMode")}</span>
            </button>
          )}
          {phase === "guided" && (
            <button
              type="button"
              className="icon-btn"
              onClick={() => speech.setEnabled(!speech.enabled)}
              aria-pressed={speech.enabled}
              title={speech.enabled ? t("header.voiceGuideOn") : t("header.voiceGuideOff")}
              aria-label={speech.enabled ? t("header.voiceGuideOn") : t("header.voiceGuideOff")}
            >
              {speech.enabled ? <SpeakerWaveIcon className="h-4 w-4 text-primary" /> : <SpeakerXMarkIcon className="h-4 w-4" />}
            </button>
          )}
          <button type="button" className="icon-btn text-xs font-bold" onClick={toggleLanguage} aria-label="Language">
            {t("header.langToggle")}
          </button>
          <button
            type="button"
            className="icon-btn"
            onClick={toggleTheme}
            title={theme === "dark" ? t("header.themeToLight") : t("header.themeToDark")}
            aria-label={theme === "dark" ? t("header.themeToLight") : t("header.themeToDark")}
          >
            {theme === "dark" ? <SunIcon className="h-4 w-4" /> : <MoonIcon className="h-4 w-4" />}
          </button>
          {points.length > 0 && phase !== "onboarding" && (
            <button type="button" className="icon-btn text-brand-red" onClick={resetAll} title={t("header.clearButton")} aria-label={t("header.clearButton")}>
              <ArrowPathIcon className="h-4 w-4" />
            </button>
          )}
        </div>
      </header>

      {/* Work panel */}
      {phase !== "onboarding" && (
        <section className="panel fixed left-4 top-[68px] z-20 max-h-[calc(100dvh-15rem)] w-[calc(100vw-2rem)] max-w-[400px] overflow-y-auto p-5 sm:max-h-[calc(100dvh-6.5rem)]">
          {phase === "expert" && renderStep()}

          {phase === "guided" && demo && currentStepDef && (
            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between">
                  <p className="eyebrow flex items-center gap-2">
                    <span className="rounded-full inline-block h-2 w-2 bg-brand-red" />
                    {t("demo.label")} · {demo.def.title[language]}
                  </p>
                  <button type="button" className="text-xs underline underline-offset-4 hover:text-brand-red" onClick={stopDemo}>
                    {t("demo.stop")}
                  </button>
                </div>
                {!demo.finished ? (
                  <>
                    <p className="mt-3 text-sm font-medium leading-relaxed" aria-live="polite">
                      {currentStepDef.caption[language]}
                    </p>
                    <div className="mt-3 h-0.5 bg-border" aria-hidden>
                      <div
                        key={`${demo.def.id}-${demo.index}`}
                        className="h-full origin-left bg-brand-red"
                        style={{ animation: `demo-progress ${currentStepDef.duration}ms linear forwards` }}
                      />
                    </div>
                  </>
                ) : (
                  <div className="mt-3 space-y-3">
                    <p className="text-sm font-bold">{t("demo.done")}</p>
                    <div className="flex gap-2">
                      <button type="button" className="btn btn-primary flex-1" onClick={tryItYourself}>
                        {t("demo.tryIt")}
                      </button>
                      <button type="button" className="btn btn-line flex-1" onClick={stopDemo}>
                        {t("demo.another")}
                      </button>
                    </div>
                  </div>
                )}
              </div>
              <div className="border-t border-border pt-4">
                <div inert className="select-none">
                  {renderStep(true)}
                </div>
                <p className="mt-3 text-xs text-muted-foreground">{t("demo.note")}</p>
              </div>
            </div>
          )}

          {phase === "guided" && !demo && activeStep === "results" && renderStep()}

          {phase === "guided" && !demo && activeStep !== "results" && (
            <GuidedFlow
              key={guidedKey}
              initialStage={guidedStart}
              regionData={regionData}
              isSearching={isSearching}
              onSelectPredefined={selectPredefined}
              onSearchRegion={searchRegion}
              onSetRange={setDateRange}
              selectedVariables={selectedVariables}
              onSetVariables={setSelectedVariables}
              onFinish={() => setActiveStep("results")}
              onStartDemo={startDemo}
              registerVoice={registerVoice}
              speak={speech.speak}
              onHint={setHint}
            />
          )}
        </section>
      )}

      {/* Coordinates of the active region */}
      {centerLat !== null && centerLng !== null && phase !== "onboarding" && (
        <div className="pointer-events-none fixed right-4 top-[68px] z-10 hidden text-right text-xs tabular-nums text-muted-foreground sm:block">
          <span className="font-bold text-brand-red">{Math.abs(centerLat).toFixed(2)}° {centerLat >= 0 ? "N" : "S"}</span>
          {"  "}
          <span className="font-bold text-primary">{Math.abs(centerLng).toFixed(2)}° {centerLng >= 0 ? "E" : "W"}</span>
        </div>
      )}

      {phase === "onboarding" && <ExperienceModal onChoose={chooseExperience} registerVoice={registerVoice} speak={speech.speak} />}

      <VoiceController
        onTranscript={handleTranscript}
        onBeforeListen={speech.cancel}
        hint={flash ?? voiceHint}
      />
    </main>
  );
}
