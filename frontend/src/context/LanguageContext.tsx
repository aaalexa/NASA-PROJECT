"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import esMessages from "@/messages/es.json";
import enMessages from "@/messages/en.json";

export type Language = "es" | "en";

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  toggleLanguage: () => void;
  t: (keyPath: string) => string;
  messages: typeof esMessages;
}

const translations: Record<Language, typeof esMessages> = {
  es: esMessages,
  en: enMessages,
};

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguage] = useState<Language>("es");

  useEffect(() => {
    const saved = localStorage.getItem("nasa_earth_lang") as Language | null;
    if (saved && (saved === "es" || saved === "en")) {
      setLanguage(saved);
    }
  }, []);

  const handleSetLanguage = (lang: Language) => {
    setLanguage(lang);
    if (typeof window !== "undefined") {
      localStorage.setItem("nasa_earth_lang", lang);
    }
  };

  const toggleLanguage = () => {
    handleSetLanguage(language === "es" ? "en" : "es");
  };

  const t = (keyPath: string): string => {
    const keys = keyPath.split(".");
    let current: any = translations[language];
    for (const key of keys) {
      if (current && typeof current === "object" && key in current) {
        current = current[key];
      } else {
        // Fallback to Spanish or keyPath
        let fallback: any = translations.es;
        for (const fbKey of keys) {
          if (fallback && typeof fallback === "object" && fbKey in fallback) {
            fallback = fallback[fbKey];
          } else {
            return keyPath;
          }
        }
        return typeof fallback === "string" ? fallback : keyPath;
      }
    }
    return typeof current === "string" ? current : keyPath;
  };

  return (
    <LanguageContext.Provider
      value={{
        language,
        setLanguage: handleSetLanguage,
        toggleLanguage,
        t,
        messages: translations[language],
      }}
    >
      {children}
    </LanguageContext.Provider>
  );
}

export function useTranslation() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useTranslation must be used within a LanguageProvider");
  }
  return context;
}
