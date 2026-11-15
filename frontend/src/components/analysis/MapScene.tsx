"use client";

import { useEffect, useMemo, useRef } from "react";
import { useFrame, ThreeEvent } from "@react-three/fiber";
import * as THREE from "three";
import type { MapaTendencias } from "@/lib/api";
import { COLORS } from "@/components/analysis/palette3d";
import { SceneShell } from "@/components/analysis/SceneShell";

export interface MapHover {
  lat: number;
  lon: number;
  slope: number;
  pT: number | null;
  pMk: number | null;
  verdict: number | null;
}

const SPAN = 13; // world units for the longest side of the region
const MAX_H = 3.4;

/** Per-pixel trend map as a field of 3D bars: height = |change per decade|, red rises, blue falls. */
function Bars({ mapa, onHover }: { mapa: MapaTendencias; onHover: (h: MapHover | null) => void }) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const marker = useRef<THREE.Mesh>(null);
  const grow = useRef(0);
  const nLat = mapa.lat.length;
  const nLon = mapa.lon.length;
  const cell = Math.min(1.8, SPAN / Math.max(nLat, nLon, 1));

  const cells = useMemo(() => {
    const out: { i: number; j: number; slope: number; verdict: number | null; x: number; z: number }[] = [];
    for (let i = 0; i < nLat; i++) {
      for (let j = 0; j < nLon; j++) {
        const slope = mapa.pendiente_decada[i]?.[j];
        if (slope === null || slope === undefined) continue;
        out.push({
          i,
          j,
          slope,
          verdict: mapa.veredicto[i]?.[j] ?? null,
          x: (j - (nLon - 1) / 2) * cell,
          // north at the back: larger latitude -> negative z
          z: -(i - (nLat - 1) / 2) * cell,
        });
      }
    }
    return out;
  }, [mapa, nLat, nLon, cell]);

  // Heights are relative to the region's own range so small differences stay visible.
  const { minAbs, maxAbs } = useMemo(() => {
    const abs = cells.map((c) => Math.abs(c.slope));
    return { minAbs: Math.min(...abs, Infinity), maxAbs: Math.max(1e-9, ...abs) };
  }, [cells]);
  const heightOf = (slope: number) => 0.35 + ((Math.abs(slope) - minAbs) / Math.max(1e-9, maxAbs - minAbs)) * MAX_H;

  useEffect(() => {
    const m = mesh.current;
    if (!m) return;
    const c = new THREE.Color();
    cells.forEach((cl, idx) => {
      c.copy(cl.slope >= 0 ? COLORS.red : COLORS.blue);
      if (cl.verdict === 0) c.lerp(COLORS.olive, 0.7); // no clear trend: muted
      else if (cl.verdict === 2) c.multiplyScalar(1.35); // significant: glows under bloom
      m.setColorAt(idx, c);
    });
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
    grow.current = 0;
  }, [cells]);

  const dummy = useMemo(() => new THREE.Object3D(), []);
  useFrame((_, delta) => {
    const m = mesh.current;
    if (!m || grow.current >= 1) return;
    grow.current = Math.min(1, grow.current + delta / 1.3);
    const e = 1 - Math.pow(1 - grow.current, 3);
    cells.forEach((cl, idx) => {
      const h = heightOf(cl.slope) * e;
      dummy.position.set(cl.x, h / 2, cl.z);
      dummy.scale.set(cell * 0.82, Math.max(h, 0.001), cell * 0.82);
      dummy.updateMatrix();
      m.setMatrixAt(idx, dummy.matrix);
    });
    m.instanceMatrix.needsUpdate = true;
    m.computeBoundingSphere();
  });

  const handleMove = (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    const cl = e.instanceId !== undefined ? cells[e.instanceId] : undefined;
    if (!cl) return;
    onHover({
      lat: mapa.lat[cl.i],
      lon: mapa.lon[cl.j],
      slope: cl.slope,
      pT: mapa.p_t[cl.i]?.[cl.j] ?? null,
      pMk: mapa.p_mk[cl.i]?.[cl.j] ?? null,
      verdict: cl.verdict,
    });
    if (marker.current) {
      marker.current.visible = true;
      marker.current.position.set(cl.x, heightOf(cl.slope) + 0.25, cl.z);
    }
  };

  return (
    <group>
      <instancedMesh
        ref={mesh}
        args={[undefined, undefined, cells.length]}
        key={cells.length}
        onPointerMove={handleMove}
        onPointerOut={() => {
          onHover(null);
          if (marker.current) marker.current.visible = false;
        }}
      >
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial roughness={0.35} metalness={0.2} emissive="#ffffff" emissiveIntensity={0.08} />
      </instancedMesh>
      <mesh ref={marker} visible={false}>
        <octahedronGeometry args={[0.16]} />
        <meshBasicMaterial color="#ffffff" toneMapped={false} />
      </mesh>
      {/* region floor */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]}>
        <planeGeometry args={[nLon * cell + cell, nLat * cell + cell]} />
        <meshStandardMaterial color="#073a55" roughness={0.9} />
      </mesh>
      <gridHelper args={[Math.max(nLon, nLat) * cell + 2, Math.max(nLon, nLat) + 2, "#2c6a8a", "#124561"]} position={[0, 0, 0]} />
    </group>
  );
}

export default function MapScene({ mapa, onHover }: { mapa: MapaTendencias; onHover: (h: MapHover | null) => void }) {
  return (
    <SceneShell camera={[10, 10, 14]} target={[0, 1, 0]}>
      <Bars mapa={mapa} onHover={onHover} />
    </SceneShell>
  );
}
