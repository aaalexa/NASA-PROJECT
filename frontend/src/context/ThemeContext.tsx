"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

export type Theme = "light" | "dark";

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const saved = localStorage.getItem("nasa_earth_theme") as Theme | null;
    if (saved && (saved === "light" || saved === "dark")) {
      setTheme(saved);
      document.documentElement.classList.toggle("dark", saved === "dark");
    } else {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      const initial: Theme = prefersDark ? "dark" : "dark";
      setTheme(initial);
      document.documentElement.classList.toggle("dark", initial === "dark");
    }
  }, []);

  const handleSetTheme = (newTheme: Theme) => {
    setTheme(newTheme);
    if (typeof window !== "undefined") {
      localStorage.setItem("nasa_earth_theme", newTheme);
      document.documentElement.classList.toggle("dark", newTheme === "dark");
    }
  };

  const toggleTheme = () => {
    handleSetTheme(theme === "dark" ? "light" : "dark");
  };

  return (
    <ThemeContext.Provider
      value={{
        theme,
        setTheme: handleSetTheme,
        toggleTheme,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
