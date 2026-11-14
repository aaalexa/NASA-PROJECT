"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { arrayBufferToBase64, blobToWav16k } from "@/lib/audio";

export type VoiceStatus = "idle" | "listening" | "processing";
export type VoiceErrorCode = "unsupported" | "denied" | "noSpeech" | "failed" | "noKey";

interface Options {
  locale: "es" | "en";
  onTranscript: (text: string) => void;
  onStart?: () => void;
}

const SPEECH_THRESHOLD = 0.018; // RMS above this counts as speech
const SILENCE_MS = 1400; // stop after this much silence once speech was heard
const NO_SPEECH_MS = 7000; // give up if nothing was said
const MAX_MS = 15000;

/**
 * Records the microphone, detects the end of the utterance, and sends the audio to
 * /api/transcribe where the Google GenAI SDK (Gemini) turns it into text.
 */
export function useVoiceInput({ locale, onTranscript, onStart }: Options) {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [level, setLevel] = useState(0);
  const [error, setError] = useState<VoiceErrorCode | null>(null);

  const onTranscriptRef = useRef(onTranscript);
  const onStartRef = useRef(onStart);
  const localeRef = useRef(locale);
  useEffect(() => {
    onTranscriptRef.current = onTranscript;
    onStartRef.current = onStart;
    localeRef.current = locale;
  });

  const recorderRef = useRef<MediaRecorder | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);
  const cancelledRef = useRef(false);

  const teardown = useCallback(() => {
    cleanupRef.current?.();
    cleanupRef.current = null;
    setLevel(0);
  }, []);

  const stop = useCallback(() => {
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") rec.stop();
  }, []);

  const start = useCallback(async () => {
    setError(null);
    if (
      typeof navigator === "undefined" ||
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      setError("unsupported");
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
    } catch {
      setError("denied");
      return;
    }

    onStartRef.current?.();
    cancelledRef.current = false;

    const chunks: BlobPart[] = [];
    const recorder = new MediaRecorder(stream);
    recorderRef.current = recorder;

    const AudioCtx: typeof AudioContext =
      window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const audioCtx = new AudioCtx();
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 1024;
    audioCtx.createMediaStreamSource(stream).connect(analyser);
    const data = new Float32Array(analyser.fftSize);

    let heardSpeech = false;
    let lastVoiceAt = performance.now();
    const startedAt = performance.now();
    let raf = 0;
    let lastPaint = 0;

    const tick = (now: number) => {
      analyser.getFloatTimeDomainData(data);
      let sum = 0;
      for (let i = 0; i < data.length; i++) sum += data[i] * data[i];
      const rms = Math.sqrt(sum / data.length);

      if (rms > SPEECH_THRESHOLD) {
        heardSpeech = true;
        lastVoiceAt = now;
      }
      if (now - lastPaint > 50) {
        lastPaint = now;
        setLevel(Math.min(1, rms * 8));
      }

      const elapsed = now - startedAt;
      if (
        (heardSpeech && now - lastVoiceAt > SILENCE_MS) ||
        (!heardSpeech && elapsed > NO_SPEECH_MS) ||
        elapsed > MAX_MS
      ) {
        stop();
        return;
      }
      raf = requestAnimationFrame(tick);
    };

    cleanupRef.current = () => {
      cancelAnimationFrame(raf);
      stream.getTracks().forEach((t) => t.stop());
      void audioCtx.close();
    };

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };

    recorder.onstop = async () => {
      teardown();
      recorderRef.current = null;
      if (cancelledRef.current) {
        setStatus("idle");
        return;
      }
      if (!heardSpeech) {
        setStatus("idle");
        setError("noSpeech");
        return;
      }
      setStatus("processing");
      try {
        const wav = await blobToWav16k(new Blob(chunks, { type: recorder.mimeType }));
        const res = await fetch("/api/transcribe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            audio: arrayBufferToBase64(wav),
            mimeType: "audio/wav",
            locale: localeRef.current,
          }),
        });
        const json = await res.json().catch(() => ({}));
        if (res.status === 503) {
          setError("noKey");
        } else if (!res.ok) {
          setError("failed");
        } else if (!json.transcript || !String(json.transcript).trim()) {
          setError("noSpeech");
        } else if (!cancelledRef.current) {
          onTranscriptRef.current(String(json.transcript).trim());
        }
      } catch (e) {
        console.error("[voice] transcription failed", e);
        setError("failed");
      } finally {
        setStatus("idle");
      }
    };

    recorder.start();
    setStatus("listening");
    raf = requestAnimationFrame(tick);
  }, [stop, teardown]);

  const toggle = useCallback(() => {
    if (status === "listening") stop();
    else if (status === "idle") void start();
  }, [status, start, stop]);

  const clearError = useCallback(() => setError(null), []);

  useEffect(() => {
    return () => {
      cancelledRef.current = true;
      const rec = recorderRef.current;
      if (rec && rec.state !== "inactive") rec.stop();
      cleanupRef.current?.();
    };
  }, []);

  return { status, level, error, toggle, start, stop, clearError };
}
