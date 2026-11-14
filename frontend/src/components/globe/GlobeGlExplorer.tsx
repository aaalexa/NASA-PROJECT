"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import type { GlobeMethods } from "react-globe.gl";
import { GeoPoint } from "@/types/geo";
import { useTheme } from "@/context/ThemeContext";

// three.js needs the browser, so the globe is loaded client-side only.
const Globe = dynamic(() => import("react-globe.gl"), { ssr: false });

interface GlobeGlExplorerProps {
  trianglePoints: GeoPoint[];
  className?: string;
}

// Moody Trends palette
const BRICK_RED = "#c1121f";
const STEEL_BLUE = "#669bbc";
const PALM_LEAF = "#9c914f";

const TEXTURE = "https://unpkg.com/three-globe/example/img";

function spanDegrees(points: GeoPoint[]): number {
  if (points.length < 3) return 0;
  const lats = points.map((p) => p.lat);
  const lngs = points.map((p) => p.lng);
  return Math.max(Math.max(...lats) - Math.min(...lats), Math.max(...lngs) - Math.min(...lngs));
}

/** react-globe.gl version of the globe: textured Earth, region polygon, pulsing vertices. */
export default function GlobeGlExplorer({ trianglePoints, className }: GlobeGlExplorerProps) {
  const globeRef = useRef<GlobeMethods | undefined>(undefined);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 800, h: 800 });
  const [ready, setReady] = useState(false);
  const { theme } = useTheme();
  const isDark = theme === "dark";

  // Track the container so the canvas always fills the screen.
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const update = () => setSize({ w: el.clientWidth, h: el.clientHeight });
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const hasRegion = trianglePoints.length === 3;

  const polygons = useMemo(() => {
    if (!hasRegion) return [];
    // The globe uses d3-geo spherical winding: exterior rings must be clockwise, or the polygon
    // is treated as everything except the triangle.
    const [a, b, c] = trianglePoints;
    const signedArea = (b.lng - a.lng) * (c.lat - a.lat) - (c.lng - a.lng) * (b.lat - a.lat);
    const ring = signedArea <= 0 ? [a, b, c] : [a, c, b];
    return [
      {
        type: "Feature",
        geometry: { type: "Polygon", coordinates: [[...ring.map((p) => [p.lng, p.lat]), [ring[0].lng, ring[0].lat]]] },
      },
    ];
  }, [hasRegion, trianglePoints]);

  const vertices = useMemo(() => trianglePoints.map((p, i) => ({ ...p, id: i })), [trianglePoints]);

  // Auto-rotate while idle; fly to the region as soon as one is set.
  useEffect(() => {
    const g = globeRef.current;
    if (!g || !ready) return;
    const controls = g.controls();
    controls.autoRotate = !hasRegion;
    controls.autoRotateSpeed = 0.5;
    controls.enableZoom = true;

    if (hasRegion) {
      const lat = trianglePoints.reduce((s, p) => s + p.lat, 0) / 3;
      const lng = trianglePoints.reduce((s, p) => s + p.lng, 0) / 3;
      const span = spanDegrees(trianglePoints);
      const altitude = span < 10 ? 1.2 : span < 25 ? 1.8 : span < 50 ? 2.3 : 2.6;
      g.pointOfView({ lat, lng, altitude }, 1200);
    }
  }, [trianglePoints, hasRegion, ready]);

  return (
    <div
      ref={wrapRef}
      className={`fixed inset-0 z-0 overflow-hidden bg-background transition-colors duration-300 ${className || ""}`}
    >
      <div className="absolute inset-0 max-sm:-translate-y-[18%]">
        <Globe
          ref={globeRef}
          width={size.w}
          height={size.h}
          backgroundColor="rgba(0,0,0,0)"
          onGlobeReady={() => setReady(true)}
          globeImageUrl={isDark ? `${TEXTURE}/earth-night.jpg` : `${TEXTURE}/earth-day.jpg`}
          bumpImageUrl={`${TEXTURE}/earth-topology.png`}
          atmosphereColor={STEEL_BLUE}
          atmosphereAltitude={0.18}
          // Region: translucent cap, thin steel-blue outline
          polygonsData={polygons}
          polygonCapColor={() => "rgba(193,18,31,0.22)"}
          polygonSideColor={() => "rgba(102,155,188,0.35)"}
          polygonStrokeColor={() => STEEL_BLUE}
          polygonAltitude={0.012}
          // Vertices: brick-red cores with expanding rings
          pointsData={vertices}
          pointLat="lat"
          pointLng="lng"
          pointColor={() => BRICK_RED}
          pointAltitude={0.02}
          pointRadius={0.35}
          ringsData={vertices}
          ringLat="lat"
          ringLng="lng"
          ringColor={() => (t: number) => `rgba(193,18,31,${1 - t})`}
          ringMaxRadius={4}
          ringPropagationSpeed={2}
          ringRepeatPeriod={1400}
        />
      </div>
    </div>
  );
}
