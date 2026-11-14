"use client";

import { useEffect, useRef } from "react";
import createGlobe, { Globe, Marker, Arc } from "cobe";
import { GeoPoint } from "@/types/geo";
import { useTheme } from "@/context/ThemeContext";

interface CobeGlobePulseProps {
  trianglePoints: GeoPoint[];
  className?: string;
}

type RGB = [number, number, number];

// Moody Trends palette
const BRICK_RED: RGB = [0.757, 0.071, 0.122];
const STEEL_BLUE: RGB = [0.4, 0.608, 0.737];
const PALM_LEAF: RGB = [0.612, 0.569, 0.31];
const MOLTEN_LAVA: RGB = [0.47, 0, 0];

function locationToAngles(lat: number, lng: number): [number, number] {
  return [Math.PI - ((lng * Math.PI) / 180 - Math.PI / 2), (lat * Math.PI) / 180];
}

const mix = (a: GeoPoint, b: GeoPoint, t: number): [number, number] => [
  a.lat + (b.lat - a.lat) * t,
  a.lng + (b.lng - a.lng) * t,
];

interface RegionShape {
  edges: Marker[];
  fill: Marker[];
  arcs: Arc[];
  vertices: GeoPoint[];
  /** Approximate angular size in degrees, used to scale the pulse rings. */
  span: number;
}

/** Delicate outline (fine blue dots), a soft dotted fill (palm leaf) and three thin arcs. */
function buildShape(points: GeoPoint[]): RegionShape | null {
  if (points.length !== 3) return null;
  const [a, b, c] = points;
  const sides: [GeoPoint, GeoPoint][] = [[a, b], [b, c], [c, a]];

  const span = Math.max(
    ...sides.map(([p, q]) => Math.hypot(p.lat - q.lat, (p.lng - q.lng) * Math.cos(((p.lat + q.lat) / 2) * (Math.PI / 180))))
  );

  const edgeSteps = Math.max(18, Math.min(60, Math.round(span * 3)));
  const edges: Marker[] = [];
  for (const [p, q] of sides) {
    for (let i = 1; i < edgeSteps; i++) {
      edges.push({ location: mix(p, q, i / edgeSteps), size: 0.009, color: STEEL_BLUE });
    }
  }

  // Interior dots on a barycentric grid (interior points only).
  const n = Math.max(5, Math.min(13, Math.round(span / 3)));
  const fill: Marker[] = [];
  for (let i = 1; i < n; i++) {
    for (let j = 1; i + j < n; j++) {
      const k = n - i - j;
      fill.push({
        location: [(a.lat * i + b.lat * j + c.lat * k) / n, (a.lng * i + b.lng * j + c.lng * k) / n],
        size: 0.007,
        color: PALM_LEAF,
      });
    }
  }

  const arcs: Arc[] = sides.map(([p, q]) => ({
    from: [p.lat, p.lng],
    to: [q.lat, q.lng],
    color: STEEL_BLUE,
  }));

  return { edges, fill, arcs, vertices: points, span };
}

export default function CobeGlobePulse({ trianglePoints, className }: CobeGlobePulseProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pointerInteracting = useRef<number | null>(null);
  const pointerInteractionMovement = useRef(0);
  const focusRef = useRef<[number, number] | null>(null);
  const shapeRef = useRef<RegionShape | null>(null);
  const { theme } = useTheme();
  const isDark = theme === "dark";

  // New region: rebuild the shape and aim the globe at it right away (no globe re-creation).
  useEffect(() => {
    shapeRef.current = buildShape(trianglePoints);
    if (trianglePoints.length > 0) {
      const lat = trianglePoints.reduce((s, p) => s + p.lat, 0) / trianglePoints.length;
      const lng = trianglePoints.reduce((s, p) => s + p.lng, 0) / trianglePoints.length;
      focusRef.current = locationToAngles(lat, lng);
      pointerInteractionMovement.current = 0;
    } else {
      focusRef.current = null;
    }
  }, [trianglePoints]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let phi = 0;
    let theta = 0.2;
    let zoom = 1;
    let width = canvas.offsetWidth || 600;
    const doublePi = Math.PI * 2;
    let raf = 0;
    let globe: Globe | null = null;

    const onResize = () => {
      width = canvas.offsetWidth || 600;
    };
    window.addEventListener("resize", onResize);

    try {
      globe = createGlobe(canvas, {
        devicePixelRatio: Math.min(window.devicePixelRatio || 2, 2),
        width: width * 2,
        height: width * 2,
        phi: 0,
        theta: 0.2,
        dark: isDark ? 1 : 0,
        diffuse: isDark ? 1.2 : 1.5,
        mapSamples: 42000,
        mapBrightness: isDark ? 3.2 : 1.6,
        mapBaseBrightness: 0,
        baseColor: isDark ? [0.0, 0.1, 0.16] : [0.9, 0.94, 0.97],
        markerColor: BRICK_RED,
        glowColor: isDark ? [0.0, 0.19, 0.29] : STEEL_BLUE,
        markers: [],
        arcs: [],
        arcWidth: 0.16,
        arcHeight: 0.02,
      });

      const render = () => {
        const focus = focusRef.current;
        if (!focus) {
          if (pointerInteracting.current === null) phi += 0.003;
        } else {
          const [focusPhi, focusTheta] = focus;
          const diff = ((focusPhi - phi + Math.PI) % doublePi + doublePi) % doublePi - Math.PI;
          phi += diff * 0.1;
          theta += (focusTheta - theta) * 0.1;
        }
        // Zoom in on small regions, stay wide for continents.
        const span = shapeRef.current?.span ?? 0;
        const zoomTarget = !focus ? 1 : span < 10 ? 1.7 : span < 25 ? 1.45 : span < 50 ? 1.2 : 1.05;
        zoom += (zoomTarget - zoom) * 0.06;

        const shape = shapeRef.current;
        const t = Date.now();
        const markers: Marker[] = [];
        if (shape) {
          markers.push(...shape.edges, ...shape.fill);
          // Vertices: a small solid core plus a soft ring that breathes outward.
          const breathe = 0.5 + 0.5 * Math.sin(t / 700);
          const ringRadius = Math.max(0.6, shape.span * 0.035) * (0.7 + breathe * 0.6);
          for (const v of shape.vertices) {
            markers.push({ location: [v.lat, v.lng], size: 0.024, color: BRICK_RED });
            const cos = Math.max(0.2, Math.cos((v.lat * Math.PI) / 180));
            for (let i = 0; i < 12; i++) {
              const ang = (i / 12) * doublePi;
              markers.push({
                location: [v.lat + ringRadius * Math.sin(ang), v.lng + (ringRadius * Math.cos(ang)) / cos],
                size: 0.0045,
                color: i % 2 ? MOLTEN_LAVA : BRICK_RED,
              });
            }
          }
        }

        globe?.update({
          phi: phi + pointerInteractionMovement.current,
          theta,
          scale: zoom,
          markers,
          arcs: shape ? shape.arcs : [],
          width: width * 2,
          height: width * 2,
        });
        raf = requestAnimationFrame(render);
      };
      raf = requestAnimationFrame(render);
      setTimeout(() => {
        if (canvas) canvas.style.opacity = "1";
      }, 50);
    } catch (e) {
      console.error("Error initializing Cobe globe:", e);
    }

    return () => {
      cancelAnimationFrame(raf);
      globe?.destroy();
      window.removeEventListener("resize", onResize);
    };
  }, [isDark]);

  return (
    <div
      className={`fixed inset-0 z-0 flex items-center justify-center overflow-hidden bg-background transition-colors duration-300 ${
        className || ""
      }`}
    >
      <div className="relative flex aspect-square w-full max-w-[800px] items-center justify-center max-sm:-translate-y-[24%] max-sm:scale-125">
        <canvas
          ref={canvasRef}
          onPointerDown={(e) => {
            pointerInteracting.current = e.clientX - pointerInteractionMovement.current;
            if (canvasRef.current) canvasRef.current.style.cursor = "grabbing";
          }}
          onPointerUp={() => {
            pointerInteracting.current = null;
            if (canvasRef.current) canvasRef.current.style.cursor = "grab";
          }}
          onPointerOut={() => {
            pointerInteracting.current = null;
            if (canvasRef.current) canvasRef.current.style.cursor = "grab";
          }}
          onMouseMove={(e) => {
            if (pointerInteracting.current !== null) {
              pointerInteractionMovement.current = (e.clientX - pointerInteracting.current) / 200;
            }
          }}
          className="h-full w-full cursor-grab touch-none select-none opacity-0 transition-opacity duration-700"
        />
      </div>
    </div>
  );
}
