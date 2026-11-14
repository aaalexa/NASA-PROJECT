"use client";

import { useState, useRef, useEffect } from "react";
import {
  MicrophoneIcon,
  ArrowPathIcon,
  SpeakerWaveIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/24/outline";
import { MicrophoneIcon as MicrophoneIconSolid } from "@heroicons/react/24/solid";
import { Button } from "@/components/ui/button";
import { RegionAnalysisPayload } from "@/types/geo";
import { useTranslation } from "@/context/LanguageContext";

interface VoiceControllerProps {
  onRegionParsed: (data: RegionAnalysisPayload) => void;
  className?: string;
}

export function VoiceController({ onRegionParsed, className }: VoiceControllerProps) {
  const { language, t } = useTranslation();
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // Cleanup
        }
      }
    };
  }, []);

  const startListening = () => {
    setErrorMessage(null);

    // Si ya está escuchando, detener inmediatamente
    if (isListening && recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // No-op
      }
      setIsListening(false);
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setErrorMessage(t("voice.unsupported"));
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = language === "es" ? "es-ES" : "en-US";
      recognition.continuous = false;
      recognition.interimResults = true;

      recognition.onstart = () => {
        setIsListening(true);
        setTranscript("");
      };

      recognition.onresult = (event: any) => {
        let currentTranscript = "";
        for (let i = 0; i < event.results.length; i++) {
          currentTranscript += event.results[i][0].transcript;
        }
        setTranscript(currentTranscript);
      };

      recognition.onerror = (event: any) => {
        console.error("[NASA Earth Detective] Speech recognition error:", event.error);
        setIsListening(false);
        if (event.error === "no-speech") {
          setErrorMessage(
            language === "es"
              ? "No se detectó audio. Por favor intenta de nuevo."
              : "No speech detected. Please try again."
          );
        } else if (event.error === "not-allowed") {
          setErrorMessage(
            language === "es"
              ? "Permiso de micrófono denegado en tu navegador."
              : "Microphone permission denied."
          );
        } else {
          setErrorMessage(`Error: ${event.error}`);
        }
      };

      recognition.onend = () => {
        setIsListening(false);
        if (transcript && transcript.trim()) {
          processVoiceCommand(transcript);
        }
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (e: any) {
      console.error("[NASA Earth Detective] Failed to start recognition:", e);
      setIsListening(false);
      setErrorMessage(e.message || "Failed to initialize microphone");
    }
  };

  const processVoiceCommand = async (text: string) => {
    if (!text.trim()) return;
    setIsProcessing(true);
    setErrorMessage(null);

    console.group("[NASA Earth Detective] Processing Voice Command");
    console.log("Audio Query:", text);
    console.log("Target Locale:", language);
    console.groupEnd();

    try {
      const res = await fetch("/api/parse-voice", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: text, locale: language }),
      });
      const data = await res.json();
      if (!data.error) {
        onRegionParsed(data);
      } else {
        setErrorMessage(data.error);
      }
    } catch (error) {
      console.error("[NASA Earth Detective] Voice processing error:", error);
      setErrorMessage(language === "es" ? "Error al procesar el audio" : "Error processing voice audio");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div
      className={`fixed bottom-8 left-1/2 -translate-x-1/2 z-30 flex flex-col items-center gap-2.5 select-none ${
        className || ""
      }`}
    >
      {/* Transcripción en tiempo real */}
      {transcript && (
        <div className="bg-card/95 dark:bg-black/95 backdrop-blur-md border border-border px-4 py-2 rounded-full text-xs sm:text-sm text-foreground font-mono shadow-2xl flex items-center gap-2 max-w-sm sm:max-w-md text-center truncate animate-in fade-in zoom-in-95">
          <SpeakerWaveIcon className="w-3.5 h-3.5 text-blue-500 shrink-0 animate-pulse" />
          <span className="truncate">&ldquo;{transcript}&rdquo;</span>
        </div>
      )}

      {/* Error discreto */}
      {errorMessage && (
        <div className="bg-red-500/10 border border-red-500/40 px-3 py-1.5 rounded-xl text-[11px] text-red-600 dark:text-red-300 font-mono flex items-center gap-1.5 shadow-xl">
          <ExclamationCircleIcon className="w-4 h-4 text-red-500 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Botón Central de Micrófono */}
      <div className="relative flex items-center justify-center">
        {/* Anillo de pulso expansivo durante escucha activa */}
        {isListening && (
          <>
            <span className="absolute inline-flex h-20 w-20 rounded-full bg-red-600/30 animate-ping" />
            <span className="absolute inline-flex h-24 w-24 rounded-full border border-red-500/40 animate-pulse" />
          </>
        )}

        <Button
          size="lg"
          onClick={startListening}
          disabled={isProcessing}
          aria-label={isListening ? t("voice.stop") : t("voice.speak")}
          className={`relative rounded-full h-16 w-16 text-white border-2 border-white/20 shadow-2xl transition-all cursor-pointer ${
            isListening
              ? "bg-red-600 hover:bg-red-700 ring-4 ring-red-500/50 scale-105"
              : isProcessing
              ? "bg-blue-800 cursor-wait"
              : "bg-blue-600 hover:bg-blue-700 hover:scale-105 active:scale-95 shadow-blue-600/30"
          }`}
        >
          {isProcessing ? (
            <ArrowPathIcon className="h-6 w-6 animate-spin text-white" />
          ) : isListening ? (
            <MicrophoneIconSolid className="h-6 w-6 text-white animate-pulse" />
          ) : (
            <MicrophoneIcon className="h-6 w-6 text-white" />
          )}
        </Button>
      </div>

      {/* Visualizador de ondas de sonido cuando está escuchando */}
      {isListening ? (
        <div className="flex items-center gap-1 h-3 mt-0.5">
          <span className="w-1 bg-red-500 rounded-full animate-[pulse_0.4s_ease-in-out_infinite] h-2" />
          <span className="w-1 bg-red-500 rounded-full animate-[pulse_0.6s_ease-in-out_infinite] h-3.5" />
          <span className="w-1 bg-red-500 rounded-full animate-[pulse_0.3s_ease-in-out_infinite] h-2.5" />
          <span className="w-1 bg-red-500 rounded-full animate-[pulse_0.5s_ease-in-out_infinite] h-4" />
          <span className="w-1 bg-red-500 rounded-full animate-[pulse_0.4s_ease-in-out_infinite] h-2" />
        </div>
      ) : null}

      {/* Estado del sistema */}
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono font-medium">
        {isListening
          ? t("voice.listening")
          : isProcessing
          ? t("voice.processing")
          : t("voice.speak")}
      </span>
    </div>
  );
}
