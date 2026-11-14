"use client";

import { useEffect, useState } from "react";
import { ArrowLeftIcon, ArrowRightIcon, MagnifyingGlassIcon, PlayIcon } from "@heroicons/react/24/outline";
import { useTranslation } from "@/context/LanguageContext";
import { ALL_VARIABLES, PERIODS, TOPICS, VARIABLES } from "@/lib/catalog";
import { DEMOS } from "@/lib/demos";
import { classifyPeriod, classifyTopic } from "@/lib/intent";
import { PREDEFINED_REGIONS } from "@/components/nasa/PredefinedRegions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ChoiceButton } from "@/components/ui/choice-button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import type { DateRange, PredefinedRegion, RegionAnalysisPayload, TopicId, VariableId } from "@/types/geo";

export type GuidedStage = "intro" | "topic" | "region" | "period" | "suggest";
const STAGES: GuidedStage[] = ["topic", "region", "period", "suggest"];

interface GuidedFlowProps {
  initialStage?: GuidedStage;
  regionData: RegionAnalysisPayload | null;
  isSearching: boolean;
  onSelectPredefined: (reg: PredefinedRegion) => void;
  /** Resolves true when the text was turned into a region. */
  onSearchRegion: (text: string) => Promise<boolean>;
  onPreviewText?: (text: string) => void;
  onSetRange: (range: DateRange) => void;
  selectedVariables: VariableId[];
  onSetVariables: (ids: VariableId[]) => void;
  onFinish: () => void;
  onStartDemo: (demoId: string) => void;
  registerVoice: (fn: ((text: string) => void) | null) => void;
  speak: (text: string) => void;
  onHint: (hint: string | undefined) => void;
}

interface GuideResult {
  key: string;
  source: "gemini" | "local";
  summary: string;
  ranked: { id: VariableId; reason: string }[];
}

export function GuidedFlow({
  initialStage = "intro",
  regionData,
  isSearching,
  onSelectPredefined,
  onSearchRegion,
  onPreviewText,
  onSetRange,
  selectedVariables,
  onSetVariables,
  onFinish,
  onStartDemo,
  registerVoice,
  speak,
  onHint,
}: GuidedFlowProps) {
  const { language, t } = useTranslation();
  const [stage, setStage] = useState<GuidedStage>(initialStage);
  const [topic, setTopic] = useState<TopicId | null>(null);
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [guide, setGuide] = useState<GuideResult | null>(null);

  const go = (next: GuidedStage) => {
    setNotice(null);
    setStage(next);
  };

  // Voice prompt + hint for each stage.
  useEffect(() => {
    const prompts: Partial<Record<GuidedStage, string>> = {
      intro: t("guided.spokenIntro"),
      topic: t("guided.spokenQ1"),
      region: t("guided.spokenQ2"),
      period: t("guided.spokenQ3"),
      suggest: t("guided.spokenSuggest"),
    };
    const hints: Partial<Record<GuidedStage, string>> = {
      topic: t("guided.q1Hint"),
      region: t("guided.q2Hint"),
      period: t("guided.q3Hint"),
    };
    onHint(hints[stage]);
    if (prompts[stage]) speak(prompts[stage] as string);
    return () => onHint(undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage, language]);

  const chooseTopic = (id: TopicId) => {
    setTopic(id);
    go("region");
  };

  const choosePeriod = (id: (typeof PERIODS)[number]["id"]) => {
    const p = PERIODS.find((x) => x.id === id)!;
    onSetRange({ start: p.start, end: p.end, preset: p.id });
    go("suggest");
  };

  async function submitRegion(text: string) {
    setNotice(null);
    const ok = await onSearchRegion(text);
    if (!ok) setNotice(t("guided.regionNotFound"));
  }

  // Spoken answers are routed by the current stage (the parent calls the registered handler).
  useEffect(() => {
    registerVoice((text: string) => {
      if (stage === "topic") {
        const id = classifyTopic(text);
        if (id) chooseTopic(id);
        else setNotice(t("guided.topicNotUnderstood"));
      } else if (stage === "region") {
        void submitRegion(text);
      } else if (stage === "period") {
        const id = classifyPeriod(text);
        if (id) choosePeriod(id);
        else setNotice(t("guided.periodNotUnderstood"));
      }
    });
    return () => registerVoice(null);
  });

  // Fetch AI-ranked variables when we reach the suggestion stage.
  const guideKey = `${topic}|${regionData?.regionName}|${language}`;
  const loadingGuide = stage === "suggest" && guide?.key !== guideKey;

  useEffect(() => {
    if (stage !== "suggest" || !topic || !regionData) return;
    let cancelled = false;
    const done = (result: Omit<GuideResult, "key">) => {
      if (cancelled) return;
      setGuide({ ...result, key: guideKey });
      onSetVariables(result.ranked.slice(0, 3).map((r) => r.id));
    };
    fetch("/api/guide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic, regionName: regionData.regionName, locale: language }),
    })
      .then((r) => r.json())
      .then((data: Omit<GuideResult, "key">) => {
        if (!data.ranked) throw new Error("bad guide response");
        done(data);
      })
      .catch(() => {
        const fallback = TOPICS.find((x) => x.id === topic)!.variables;
        done({
          source: "local",
          summary: "",
          ranked: fallback.map((id) => ({ id, reason: VARIABLES[id].question[language] })),
        });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage, guideKey]);

  const toggle = (id: VariableId) =>
    onSetVariables(selectedVariables.includes(id) ? selectedVariables.filter((v) => v !== id) : [...selectedVariables, id]);

  const stageIndex = STAGES.indexOf(stage);

  const back = () => {
    if (stage === "suggest") go("period");
    else if (stage === "period") go("region");
    else if (stage === "region") go("topic");
    else if (stage === "topic") go("intro");
  };

  return (
    <div className="space-y-5 animate-in fade-in duration-300">
      {stage !== "intro" && (
        <Progress value={((stageIndex + 1) / STAGES.length) * 100} aria-label={t("guided.stepOf")}>
          <p className="eyebrow w-full">
            {t("guided.stepOf").replace("{n}", String(stageIndex + 1)).replace("{total}", String(STAGES.length))}
          </p>
        </Progress>
      )}

      {stage === "intro" && (
        <>
          <div>
            <h2 className="title text-xl">{t("guided.introTitle")}</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{t("guided.introDesc")}</p>
          </div>
          <Button size="lg" className="w-full" onClick={() => go("topic")}>
            {t("guided.start")}
            <ArrowRightIcon className="size-4" />
          </Button>

          <Separator />

          <div className="space-y-2">
            <p className="eyebrow">{t("guided.watchTitle")}</p>
            {DEMOS.map((d) => (
              <ChoiceButton key={d.id} onClick={() => onStartDemo(d.id)}>
                <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-brand-red text-white">
                  <PlayIcon className="size-3" />
                </span>
                <span>
                  <span className="block text-sm font-bold">{d.title[language]}</span>
                  <span className="mt-0.5 block text-xs text-muted-foreground">{d.blurb[language]}</span>
                </span>
              </ChoiceButton>
            ))}
          </div>
        </>
      )}

      {stage === "topic" && (
        <>
          <h2 className="title text-xl">{t("guided.q1")}</h2>
          <div className="space-y-2">
            {TOPICS.map((tp) => (
              <ChoiceButton key={tp.id} selected={topic === tp.id} className="flex-col gap-0.5" onClick={() => chooseTopic(tp.id)}>
                <span className="text-sm font-bold">{tp.name[language]}</span>
                <span className="text-xs text-muted-foreground">{tp.desc[language]}</span>
              </ChoiceButton>
            ))}
          </div>
        </>
      )}

      {stage === "region" && (
        <>
          <h2 className="title text-xl">{t("guided.q2")}</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (query.trim()) void submitRegion(query.trim());
            }}
            className="flex gap-2"
          >
            <div className="relative flex-1">
              <MagnifyingGlassIcon className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                className="pl-10"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setNotice(null);
                  onPreviewText?.(e.target.value);
                }}
                placeholder={t("header.searchPlaceholder")}
                aria-label={t("guided.q2")}
              />
            </div>
            <Button type="submit" className="h-10" disabled={isSearching || !query.trim()}>
              {isSearching ? "…" : t("regionStep.searchButton")}
            </Button>
          </form>

          {isSearching && (
            <p role="status" className="animate-pulse text-xs text-brand-blue">
              {t("regionStep.locating")}
            </p>
          )}

          <div className="grid grid-cols-2 gap-2">
            {PREDEFINED_REGIONS.slice(0, 6).map((reg) => (
              <ChoiceButton
                key={reg.id}
                selected={regionData?.regionName === reg.name[language]}
                className="!px-3 !py-2"
                onClick={() => {
                  setNotice(null);
                  onSelectPredefined(reg);
                }}
              >
                <span className="line-clamp-2 text-xs font-medium leading-snug">{reg.name[language]}</span>
              </ChoiceButton>
            ))}
          </div>

          {regionData && (
            <div className="rounded-2xl bg-muted p-4">
              <p className="eyebrow">{t("guided.region")}</p>
              <p className="mt-1 text-sm font-bold">{regionData.regionName}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">{regionData.description}</p>
            </div>
          )}
        </>
      )}

      {stage === "period" && (
        <>
          <h2 className="title text-xl">{t("guided.q3")}</h2>
          <div className="space-y-2">
            {PERIODS.map((p) => (
              <ChoiceButton key={p.id} className="flex-col gap-0.5" onClick={() => choosePeriod(p.id)}>
                <span className="text-sm font-bold">{p.label[language]}</span>
                <span className="text-xs text-muted-foreground">{p.desc[language]}</span>
              </ChoiceButton>
            ))}
          </div>
        </>
      )}

      {stage === "suggest" && (
        <>
          <div>
            <h2 className="title text-xl">{t("guided.suggestTitle")}</h2>
            <p className="mt-2 text-sm text-muted-foreground">{t("guided.suggestIntro")}</p>
          </div>

          {loadingGuide && <p className="text-sm text-muted-foreground">{t("guided.thinking")}</p>}

          {guide && !loadingGuide && (
            <>
              <Badge variant={guide.source === "gemini" ? "default" : "secondary"} className="w-fit">
                {guide.source === "gemini" ? t("guided.ai") : t("guided.local")}
              </Badge>
              {guide.summary && <p className="text-sm leading-relaxed">{guide.summary}</p>}
              <div className="space-y-2">
                {guide.ranked
                  .filter((r) => ALL_VARIABLES.includes(r.id))
                  .map((r) => {
                    const info = VARIABLES[r.id];
                    const on = selectedVariables.includes(r.id);
                    return (
                      <ChoiceButton key={r.id} selected={on} aria-pressed={on} onClick={() => toggle(r.id)}>
                        <Checkbox checked={on} tabIndex={-1} className="pointer-events-none mt-0.5" aria-hidden />
                        <span>
                          <span className="block text-sm font-bold">
                            {info.name[language]} <span className="font-normal text-muted-foreground">· {info.product}</span>
                          </span>
                          <span className="mt-0.5 block text-xs leading-snug text-muted-foreground">{r.reason}</span>
                        </span>
                      </ChoiceButton>
                    );
                  })}
              </div>
              <p className="text-xs text-muted-foreground">{t("guided.limits")}</p>
            </>
          )}
        </>
      )}

      {notice && (
        <p role="alert" className="text-xs text-brand-red">
          {notice}
        </p>
      )}

      {stage !== "intro" && (
        <div className="flex gap-2 pt-1">
          <Button variant="outline" onClick={back}>
            <ArrowLeftIcon className="size-4" />
            {t("guided.back")}
          </Button>
          {stage === "region" && (
            <Button className="flex-1" disabled={!regionData} onClick={() => go("period")}>
              {t("guided.continue")}
              <ArrowRightIcon className="size-4" />
            </Button>
          )}
          {stage === "suggest" && (
            <Button className="flex-1" disabled={selectedVariables.length === 0 || loadingGuide} onClick={onFinish}>
              {t("guided.run")}
              <ArrowRightIcon className="size-4" />
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
