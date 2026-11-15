"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowPathIcon,
  MoonIcon,
  SpeakerWaveIcon,
  SpeakerXMarkIcon,
  SunIcon,
  UserCircleIcon,
} from "@heroicons/react/24/outline";
// Swap back to CobeGlobePulse to restore the previous globe.
import GlobeGlExplorer from "@/components/globe/GlobeGlExplorer";
import { VoiceController } from "@/components/hud/VoiceController";
import { useBackend } from "@/context/BackendContext";
import { MoodyChat } from "@/components/chat/MoodyChat";
import { AnalysisDrawer } from "@/components/analysis/AnalysisDrawer";
import { ExperienceModal } from "@/components/onboarding/ExperienceModal";
import { GuidedFlow, GuidedStage } from "@/components/guided/GuidedFlow";
import { StepNavigation } from "@/components/nasa/StepNavigation";
import { RegionStep } from "@/components/nasa/RegionStep";
import { PeriodStep } from "@/components/nasa/PeriodStep";
import { VariablesStep } from "@/components/nasa/VariablesStep";
import { ResultsStep } from "@/components/nasa/ResultsStep";
import { periodPresets, rangeFromPreset } from "@/lib/catalog";
import { matchRegion, payloadFromBackendRegion } from "@/lib/regionMatch";
import type { BackendRegion } from "@/lib/api";
import { DEMOS, DemoDef, DemoStep } from "@/lib/demos";
import { useSpeak } from "@/hooks/useSpeak";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useTranslation } from "@/context/LanguageContext";
import { useTheme } from "@/context/ThemeContext";
import type {
  AppPhase,
  DateRange,
  Experience,
  GeoPoint,
  RegionAnalysisPayload,
  VariableId,
  WorkflowStep,
} from "@/types/geo";

/** Backend variable ids selected by default (rain and temperature). */
const DEFAULT_VARIABLES: VariableId[] = ["lluvia_gpcp", "temp_aire"];

interface DemoState {
  def: DemoDef;
  index: number;
  finished: boolean;
}

export default function HomePage() {
  const { language, setLanguage, t } = useTranslation();
  const { theme, toggleTheme } = useTheme();
  const speech = useSpeak(language);
  const backend = useBackend();
  const [digest, setDigest] = useState<string | null>(null);

  const [phase, setPhase] = useState<AppPhase>("onboarding");
  const [activeStep, setActiveStep] = useState<WorkflowStep>("region");
  const [points, setPoints] = useState<GeoPoint[]>([]);
  const [regionData, setRegionData] = useState<RegionAnalysisPayload | null>(null);
  // The default period is the backend's full common period; the user can override it.
  const [rangeOverride, setDateRange] = useState<DateRange | null>(null);
  const defaultRange = useMemo(() => {
    const archive = periodPresets(backend.period).find((p) => p.id === "archive")!;
    return rangeFromPreset(archive);
  }, [backend.period]);
  const dateRange = rangeOverride ?? defaultRange;
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

  useEffect(() => {
    if (!flash) return;
    const id = setTimeout(() => setFlash(null), 4500);
    return () => clearTimeout(id);
  }, [flash]);

  // ---- Region handling ------------------------------------------------------------------

  const applyRegion = useCallback((data: RegionAnalysisPayload) => {
    setRegionData(data);
    setPoints(data.outline ?? data.triangleVertices);
  }, []);

  const selectRegion = useCallback((reg: BackendRegion) => applyRegion(payloadFromBackendRegion(reg)), [applyRegion]);

  const searchRegion = useCallback(
    async (text: string): Promise<boolean> => {
      // Official backend regions: turn the globe instantly, no network round trip.
      const local = matchRegion(text, backend.regions);
      if (local) {
        selectRegion(local);
        return true;
      }
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
    [applyRegion, language, selectRegion, backend.regions]
  );

  // Typing preview: as soon as the text matches a backend region, aim the globe at it.
  const previewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const previewText = useCallback(
    (text: string) => {
      if (previewTimer.current) clearTimeout(previewTimer.current);
      previewTimer.current = setTimeout(() => {
        const m = matchRegion(text, backend.regions);
        if (m) selectRegion(m);
      }, 250);
    },
    [selectRegion, backend.regions]
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
    setDateRange(null);
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
        const reg = backend.regions.find((r) => r.id === step.region);
        if (reg) selectRegion(reg);
      }
      if (step.preset) {
        const p = periodPresets(backend.period).find((x) => x.id === step.preset);
        if (p) setDateRange(rangeFromPreset(p));
      }
      if (step.variables) setSelectedVariables(step.variables);
      if (step.step) setActiveStep(step.step);
    },
    [selectRegion, backend.regions, backend.period]
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

  const editCriteria = () => {
    if (phase === "guided") {
      setGuidedStart("suggest");
      setGuidedKey((k) => k + 1);
      setActiveStep("region");
    } else {
      setActiveStep("variables");
    }
  };

  const renderStep = (readOnly = false) => (
    <>
      {activeStep === "region" && (
        <RegionStep
          regionData={regionData}
          onSelectRegion={selectRegion}
          onSearchManual={searchRegion}
          onPreviewText={previewText}
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
      {activeStep === "results" && regionData && readOnly && (
        <ResultsStep
          regionData={regionData}
          range={dateRange}
          selectedVariables={selectedVariables}
          onDigest={setDigest}
          readOnly={readOnly}
          onEditCriteria={editCriteria}
          onRestart={resetAll}
        />
      )}
    </>
  );

  const drawerOpen = activeStep === "results" && demo === null && regionData !== null && phase !== "onboarding";

  const centerLat = points.length ? points.reduce((s, p) => s + p.lat, 0) / points.length : null;
  const centerLng = points.length ? points.reduce((s, p) => s + p.lng, 0) / points.length : null;

  const showNav = phase === "expert" || (phase === "guided" && demo !== null);
  const currentStepDef = demo ? demo.def.steps[demo.index] : null;

  const voiceHint =
    phase === "guided" ? hint : undefined;

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-background text-foreground">
      <GlobeGlExplorer trianglePoints={points} />

      {/* Header */}
      <header className="pointer-events-none fixed left-4 right-4 top-4 z-30 flex items-center justify-between gap-3">
        <div className="pointer-events-auto flex items-center gap-2.5">
          <span className="size-3 rounded-full bg-brand-red" aria-hidden />
          <span className="text-sm font-bold tracking-tight">{t("system.name")}</span>
          <Badge variant="secondary" className="hidden xl:inline-flex">
            {t("system.badge")}
          </Badge>
        </div>

        {showNav && (
          <div className="pointer-events-auto absolute left-1/2 hidden -translate-x-1/2 lg:block">
            <StepNavigation activeStep={activeStep} onSelectStep={setActiveStep} hasRegion={points.length >= 3} hasVariables={selectedVariables.length > 0} readOnly={demo !== null} />
          </div>
        )}

        <div className="pointer-events-auto flex items-center gap-2">
          {phase !== "onboarding" && (
            <Button variant="outline" size="sm" className="h-9 gap-1.5 bg-card/90 backdrop-blur" onClick={changeMode}>
              <UserCircleIcon className="size-4" />
              <span className="hidden lg:inline">{t("header.changeMode")}</span>
            </Button>
          )}
          {phase === "guided" && (
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    variant="outline"
                    size="icon"
                    className="bg-card/90 backdrop-blur"
                    onClick={() => speech.setEnabled(!speech.enabled)}
                    aria-pressed={speech.enabled}
                    aria-label={speech.enabled ? t("header.voiceGuideOn") : t("header.voiceGuideOff")}
                  />
                }
              >
                {speech.enabled ? <SpeakerWaveIcon className="size-4 text-brand-blue" /> : <SpeakerXMarkIcon className="size-4" />}
              </TooltipTrigger>
              <TooltipContent>{speech.enabled ? t("header.voiceGuideOn") : t("header.voiceGuideOff")}</TooltipContent>
            </Tooltip>
          )}
          <ToggleGroup
            value={[language]}
            onValueChange={(v) => v[0] && setLanguage(v[0] as "es" | "en")}
            variant="outline"
            spacing={0}
            className="rounded-full bg-card/90 backdrop-blur"
            aria-label="Language"
          >
            <ToggleGroupItem value="es" className="rounded-full px-3 text-xs font-bold">
              ES
            </ToggleGroupItem>
            <ToggleGroupItem value="en" className="rounded-full px-3 text-xs font-bold">
              EN
            </ToggleGroupItem>
          </ToggleGroup>
          <Tooltip>
            <TooltipTrigger
              render={
                <Button
                  variant="outline"
                  size="icon"
                  className="bg-card/90 backdrop-blur"
                  onClick={toggleTheme}
                  aria-label={theme === "dark" ? t("header.themeToLight") : t("header.themeToDark")}
                />
              }
            >
              {theme === "dark" ? <SunIcon className="size-4" /> : <MoonIcon className="size-4" />}
            </TooltipTrigger>
            <TooltipContent>{theme === "dark" ? t("header.themeToLight") : t("header.themeToDark")}</TooltipContent>
          </Tooltip>
          {points.length > 0 && phase !== "onboarding" && (
            <Tooltip>
              <TooltipTrigger
                render={<Button variant="outline" size="icon" className="bg-card/90 text-brand-red backdrop-blur" onClick={resetAll} aria-label={t("header.clearButton")} />}
              >
                <ArrowPathIcon className="size-4" />
              </TooltipTrigger>
              <TooltipContent>{t("header.clearButton")}</TooltipContent>
            </Tooltip>
          )}
        </div>
      </header>

      {/* Work panel */}
      {phase !== "onboarding" && !drawerOpen && (
        <Card className="fixed inset-x-4 bottom-[132px] z-20 gap-0 bg-card/95 py-0 backdrop-blur sm:inset-x-auto sm:bottom-auto sm:left-4 sm:top-[68px] sm:w-[400px]">
          <ScrollArea className="[&_[data-slot=scroll-area-viewport]]:max-h-[46dvh] sm:[&_[data-slot=scroll-area-viewport]]:max-h-[calc(100dvh-7.5rem)]">
            <div className="p-5">
              {phase === "expert" && renderStep()}

              {phase === "guided" && demo && currentStepDef && (
                <div className="space-y-4">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <Badge variant="secondary" className="max-w-[75%] truncate">
                        {t("demo.label")} · {demo.def.title[language]}
                      </Badge>
                      <Button variant="ghost" size="sm" onClick={stopDemo}>
                        {t("demo.stop")}
                      </Button>
                    </div>
                    {!demo.finished ? (
                      <>
                        <p className="text-sm font-medium leading-relaxed" aria-live="polite">
                          {currentStepDef.caption[language]}
                        </p>
                        <Progress value={((demo.index + 1) / demo.def.steps.length) * 100} aria-label={t("demo.label")} />
                      </>
                    ) : (
                      <div className="space-y-3">
                        <p className="text-sm font-bold">{t("demo.done")}</p>
                        <div className="flex gap-2">
                          <Button className="flex-1" onClick={tryItYourself}>
                            {t("demo.tryIt")}
                          </Button>
                          <Button variant="outline" className="flex-1" onClick={stopDemo}>
                            {t("demo.another")}
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                  <Separator />
                  <div inert className="select-none">
                    {renderStep(true)}
                  </div>
                  <p className="text-xs text-muted-foreground">{t("demo.note")}</p>
                </div>
              )}

              {phase === "guided" && !demo && activeStep === "results" && renderStep()}

              {phase === "guided" && !demo && activeStep !== "results" && (
                <GuidedFlow
                  key={guidedKey}
                  initialStage={guidedStart}
                  regionData={regionData}
                  isSearching={isSearching}
                  onSelectRegion={selectRegion}
                  onSearchRegion={searchRegion}
                  onPreviewText={previewText}
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
            </div>
          </ScrollArea>
        </Card>
      )}

      {/* Coordinates of the active region */}
      {centerLat !== null && centerLng !== null && phase !== "onboarding" && (
        <div className="pointer-events-none fixed right-4 top-[68px] z-10 hidden text-right text-xs tabular-nums text-muted-foreground sm:block">
          <span className="font-bold text-brand-red">{Math.abs(centerLat).toFixed(2)}° {centerLat >= 0 ? "N" : "S"}</span>
          {"  "}
          <span className="font-bold text-brand-blue">{Math.abs(centerLng).toFixed(2)}° {centerLng >= 0 ? "E" : "W"}</span>
        </div>
      )}

      {phase === "onboarding" && <ExperienceModal onChoose={chooseExperience} registerVoice={registerVoice} speak={speech.speak} />}

      <AnalysisDrawer
        open={drawerOpen}
        regionData={regionData}
        range={dateRange}
        selectedVariables={selectedVariables}
        onClose={editCriteria}
        onRestart={resetAll}
        onDigest={setDigest}
      />

      <MoodyChat
        context={{
          phase,
          step: activeStep,
          region: regionData?.regionName ?? null,
          period: `${dateRange.start.slice(0, 4)}-${dateRange.end.slice(0, 4)}`,
          variables: selectedVariables,
          demo: demo ? demo.def.title.en : null,
          results: digest,
          catalog: backend.analyzable.map((v) => `- ${v.id} (${v.nombre_simple}; ${v.dataset}; ${v.unidad_final}; ${v.frecuencia}): ${v.definicion_simple}`).join("\n"),
          regions: backend.regions.map((r) => `- ${r.id}: ${r.nombre} (${r.zona})`).join("\n"),
        }}
      />

      {!drawerOpen && <VoiceController
        onTranscript={handleTranscript}
        onBeforeListen={speech.cancel}
        hint={flash ?? voiceHint}
      /> }
    </main>
  );
}
