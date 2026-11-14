"use client";

import { useEffect, useRef } from "react";
import createGlobe, { Globe, Marker, Arc } from "cobe";
import { GeoPoint } from "@/types/geo";
import { useTheme } from "@/context/ThemeContext";

interface CobeGlobePulseProps {
  trianglePoints: GeoPoint[];
  className?: string;
}

function locationToAngles(lat: number, lng: number): [number, number] {
  return [
    Math.PI - ((lng * Math.PI) / 180 - Math.PI / 2),
    (lat * Math.PI) / 180,
  ];
}

function interpolateEdge(p1: GeoPoint, p2: GeoPoint, steps = 12): Marker[] {
  const edgeMarkers: Marker[] = [];
  for (let i = 1; i < steps; i++) {
    const t = i / steps;
    edgeMarkers.push({
      location: [
        p1.lat + (p2.lat - p1.lat) * t,
        p1.lng + (p2.lng - p1.lng) * t,
      ],
      size: 0.028,
      color: [0.145, 0.388, 0.921], // Azul NASA (#2563eb)
    });
  }
  return edgeMarkers;
}

export default function CobeGlobePulse({ trianglePoints, className }: CobeGlobePulseProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pointerInteracting = useRef<number | null>(null);
  const pointerInteractionMovement = useRef(0);
  const focusRef = useRef<[number, number]>([0, 0]);
  const { theme } = useTheme();
  const isDark = theme === "dark";

  // Sincronizar foco cuando cambian los puntos
  useEffect(() => {
    if (trianglePoints && trianglePoints.length > 0) {
      const avgLat =
        trianglePoints.reduce((sum, p) => sum + p.lat, 0) / trianglePoints.length;
      const avgLng =
        trianglePoints.reduce((sum, p) => sum + p.lng, 0) / trianglePoints.length;
      focusRef.current = locationToAngles(avgLat, avgLng);
    }
  }, [trianglePoints]);

  useEffect(() => {
    let phi = 0;
    let theta = 0.2;
    let width = 0;
    const doublePi = Math.PI * 2;
    let animationFrameId: number;
    let globeInstance: Globe | null = null;

    const onResize = () => {
      if (canvasRef.current) {
        width = canvasRef.current.offsetWidth || 600;
      }
    };
    window.addEventListener("resize", onResize);
    onResize();

    if (!canvasRef.current) return;
    if (width === 0) width = 600;

    // Aristas del triángulo (Azul NASA)
    const edgeMarkers: Marker[] =
      trianglePoints && trianglePoints.length === 3
        ? [
            ...interpolateEdge(trianglePoints[0], trianglePoints[1], 12),
            ...interpolateEdge(trianglePoints[1], trianglePoints[2], 12),
            ...interpolateEdge(trianglePoints[2], trianglePoints[0], 12),
          ]
        : [];

    const arcs: Arc[] =
      trianglePoints && trianglePoints.length === 3
        ? [
            {
              from: [trianglePoints[0].lat, trianglePoints[0].lng],
              to: [trianglePoints[1].lat, trianglePoints[1].lng],
              color: [0.145, 0.388, 0.921],
            },
            {
              from: [trianglePoints[1].lat, trianglePoints[1].lng],
              to: [trianglePoints[2].lat, trianglePoints[2].lng],
              color: [0.145, 0.388, 0.921],
            },
            {
              from: [trianglePoints[2].lat, trianglePoints[2].lng],
              to: [trianglePoints[0].lat, trianglePoints[0].lng],
              color: [0.145, 0.388, 0.921],
            },
          ]
        : [];

    try {
      globeInstance = createGlobe(canvasRef.current, {
        devicePixelRatio: Math.min(typeof window !== "undefined" ? window.devicePixelRatio : 2, 2),
        width: width * 2,
        height: width * 2,
        phi: 0,
        theta: 0.2,
        dark: isDark ? 1 : 0,
        diffuse: isDark ? 1.2 : 1.5,
        mapSamples: 16000,
        mapBrightness: isDark ? 6 : 2.5,
        baseColor: isDark ? [0.12, 0.14, 0.18] : [0.84, 0.88, 0.94],
        markerColor: [0.937, 0.267, 0.267], // Rojo Alerta (#ef4444)
        glowColor: [0.145, 0.388, 0.921], // Halo Azul NASA (#2563eb)
        markers: [],
        arcs,
        arcWidth: 0.8,
        arcHeight: 0.05,
      });

      const render = () => {
        if (!trianglePoints || trianglePoints.length === 0) {
          if (!pointerInteracting.current) {
            phi += 0.003;
          }
        } else {
          const [focusPhi, focusTheta] = focusRef.current;
          const distPositive = (focusPhi - phi + doublePi) % doublePi;
          const distNegative = (phi - focusPhi + doublePi) % doublePi;

          if (distPositive < distNegative) {
            phi += distPositive * 0.08;
          } else {
            phi -= distNegative * 0.08;
          }
          theta = theta * 0.92 + focusTheta * 0.08;
        }

        // Animación Pulse en los 3 vértices rojos
        const pulse = 0.065 + Math.sin(Date.now() / 200) * 0.025;
        const currentMarkers: Marker[] = [
          ...(trianglePoints || []).map((p) => ({
            location: [p.lat, p.lng] as [number, number],
            size: pulse,
            color: [0.937, 0.267, 0.267] as [number, number, number],
          })),
          ...edgeMarkers,
        ];

        globeInstance?.update({
          phi: phi + pointerInteractionMovement.current,
          theta,
          markers: currentMarkers,
          width: width * 2,
          height: width * 2,
        });

        animationFrameId = requestAnimationFrame(render);
      };

      animationFrameId = requestAnimationFrame(render);

      setTimeout(() => {
        if (canvasRef.current) canvasRef.current.style.opacity = "1";
      }, 50);
    } catch (e) {
      console.error("Error initializing Cobe globe:", e);
    }

    return () => {
      cancelAnimationFrame(animationFrameId);
      globeInstance?.destroy();
      window.removeEventListener("resize", onResize);
    };
  }, [trianglePoints, isDark]);

  return (
    <div
      className={`fixed inset-0 z-0 flex items-center justify-center bg-background transition-colors duration-300 overflow-hidden ${
        className || ""
      }`}
    >
      {/* Resplandor atmosférico Azul NASA */}
      <div className="absolute w-[680px] h-[680px] rounded-full bg-blue-500/10 dark:bg-blue-600/15 blur-3xl pointer-events-none select-none transition-all duration-500" />
      <div className="relative w-full max-w-[800px] aspect-square flex items-center justify-center">
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
              const delta = e.clientX - pointerInteracting.current;
              pointerInteractionMovement.current = delta / 200;
            }
          }}
          className="w-full h-full opacity-0 transition-opacity duration-700 cursor-grab select-none touch-none"
        />
      </div>
    </div>
  );
}
