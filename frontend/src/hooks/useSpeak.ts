"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/** Reads guide prompts aloud with the browser's speech synthesis (no network, no key). */
export function useSpeak(locale: "es" | "en") {
  const [enabled, setEnabled] = useState(false);
  const enabledRef = useRef(enabled);
  const localeRef = useRef(locale);
  useEffect(() => {
    enabledRef.current = enabled;
    localeRef.current = locale;
  });

  const cancel = useCallback(() => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
  }, []);

  const speak = useCallback((text: string) => {
    if (!enabledRef.current || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const synth = window.speechSynthesis;
    synth.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    const lang = localeRef.current === "es" ? "es-ES" : "en-US";
    utter.lang = lang;
    const voice = synth.getVoices().find((v) => v.lang.startsWith(lang.slice(0, 2)));
    if (voice) utter.voice = voice;
    utter.rate = 1;
    synth.speak(utter);
  }, []);

  const setSpeakEnabled = useCallback(
    (value: boolean) => {
      setEnabled(value);
      if (!value) cancel();
    },
    [cancel]
  );

  useEffect(() => cancel, [cancel]);

  return { enabled, setEnabled: setSpeakEnabled, speak, cancel };
}
