"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";
import createGlobe, { type Globe, type Marker } from "cobe";

type RGB = [number, number, number];

// Moody Trends palette
const BRICK_RED: RGB = [0.757, 0.071, 0.122];
const STEEL_BLUE: RGB = [0.4, 0.608, 0.737];
const PALM_LEAF: RGB = [0.612, 0.569, 0.31];

/** A few points of interest from the demo regions, in palette colours. */
const MARKERS: Marker[] = [
  { location: [13.5, -87.5], size: 0.07, color: BRICK_RED }, // Central American Dry Corridor
  { location: [-3.5, -62], size: 0.05, color: PALM_LEAF }, // Amazonia
  { location: [14, 2], size: 0.05, color: STEEL_BLUE }, // Sahel
  { location: [17.5, -92.5], size: 0.04, color: BRICK_RED }, // Southeast Mexico
];

/** Follows the `dark` class on <html>, so it also works outside the theme provider (global-error). */
function subscribeTheme(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}
const readDark = () => document.documentElement.classList.contains("dark");

/**
 * Small Cobe globe used by the error screens. `muted` dims the map and drops the markers
 * (offline state): the planet is there, but the signal is not.
 */
export function ErrorGlobe({ muted = false, className = "" }: { muted?: boolean; className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const isDark = useSyncExternalStore(subscribeTheme, readDark, () => true);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let phi = 0;
    let raf = 0;
    let globe: Globe | null = null;
    const size = () => (canvas.offsetWidth || 160) * 2;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    try {
      globe = createGlobe(canvas, {
        devicePixelRatio: 2,
        width: size(),
        height: size(),
        phi: 0,
        theta: 0.25,
        dark: isDark ? 1 : 0,
        diffuse: isDark ? 1.2 : 1.5,
        mapSamples: 16000,
        mapBrightness: muted ? (isDark ? 1.2 : 0.8) : isDark ? 3.2 : 1.6,
        mapBaseBrightness: 0,
        // Lighter than the page background so the small globe stands out from it.
        baseColor: isDark ? STEEL_BLUE : [0.9, 0.94, 0.97],
        markerColor: BRICK_RED,
        glowColor: isDark ? [0.0, 0.19, 0.29] : STEEL_BLUE,
        markers: muted ? [] : MARKERS,
      });

      const render = () => {
        if (!reduceMotion) phi += muted ? 0.0012 : 0.004;
        globe?.update({ phi, width: size(), height: size() });
        raf = requestAnimationFrame(render);
      };
      raf = requestAnimationFrame(render);
      requestAnimationFrame(() => {
        canvas.style.opacity = muted ? "0.55" : "1";
      });
    } catch (e) {
      // WebGL unavailable: the screen still works without the globe.
      console.error("Error globe could not start:", e);
    }

    return () => {
      cancelAnimationFrame(raf);
      globe?.destroy();
    };
  }, [isDark, muted]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className={`size-full opacity-0 transition-opacity duration-1000 ${className}`}
    />
  );
}
