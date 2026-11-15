"use client";

import { useEffect, useMemo, useRef } from "react";
import { useFrame, ThreeEvent } from "@react-three/fiber";
import { RoundedBox, Text } from "@react-three/drei";
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import type { MapaTendencias } from "@/lib/api";
import { COLORS, HEX } from "@/components/analysis/palette3d";
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

/** Graticule drawn once into a CanvasTexture: one square per NASA grid cell, softly glowing borders. */
function useGraticule(nLat: number, nLon: number) {
  const texture = useMemo(() => {
    const px = 72;
    const c = document.createElement("canvas");
    c.width = Math.min(2048, nLon * px);
    c.height = Math.min(2048, nLat * px);
    const g = c.getContext("2d")!;
    g.fillStyle = HEX.deep;
    g.fillRect(0, 0, c.width, c.height);
    const grad = g.createRadialGradient(c.width / 2, c.height / 2, 0, c.width / 2, c.height / 2, Math.max(c.width, c.height) * 0.7);
    grad.addColorStop(0, "rgba(102,155,188,0.3)");
    grad.addColorStop(1, "rgba(0,48,73,0)");
    g.fillStyle = grad;
    g.fillRect(0, 0, c.width, c.height);
    g.strokeStyle = "rgba(102,155,188,0.55)";
    g.lineWidth = 2;
    for (let i = 0; i <= nLon; i++) {
      const x = (i / nLon) * c.width;
      g.beginPath();
      g.moveTo(x, 0);
      g.lineTo(x, c.height);
      g.stroke();
    }
    for (let j = 0; j <= nLat; j++) {
      const y = (j / nLat) * c.height;
      g.beginPath();
      g.moveTo(0, y);
      g.lineTo(c.width, y);
      g.stroke();
    }
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    t.anisotropy = 8;
    return t;
  }, [nLat, nLon]);
  useEffect(() => () => texture.dispose(), [texture]);
  return texture;
}

/** Per-pixel trend map as a field of rounded 3D bars: height = change per decade, red rises, blue falls. */
function Bars({ mapa, onHover }: { mapa: MapaTendencias; onHover: (h: MapHover | null) => void }) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const material = useRef<THREE.MeshPhysicalMaterial>(null);
  const marker = useRef<THREE.Mesh>(null);
  const frame = useRef<THREE.Mesh>(null);
  const grow = useRef(0);
  const nLat = mapa.lat.length;
  const nLon = mapa.lon.length;
  const cell = Math.min(1.8, SPAN / Math.max(nLat, nLon, 1));
  const graticule = useGraticule(nLat, nLon);

  const geometry = useMemo(() => new RoundedBoxGeometry(1, 1, 1, 4, 0.16), []);
  useEffect(() => () => geometry.dispose(), [geometry]);

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
          z: -(i - (nLat - 1) / 2) * cell, // north at the back
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
      c.multiplyScalar(0.72); // keep the palette hue, lit surfaces wash out light colours
      if (cl.verdict === 0) c.lerp(COLORS.olive, 0.7); // no clear trend: muted
      else if (cl.verdict === 2) c.multiplyScalar(1.1); // significant: a touch brighter
      m.setColorAt(idx, c);
    });
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
    grow.current = 0;
  }, [cells]);

  const dummy = useMemo(() => new THREE.Object3D(), []);
  const maxDist = Math.hypot((nLon * cell) / 2, (nLat * cell) / 2) || 1;

  useFrame((state, delta) => {
    // significant bars breathe: a slow emissive pulse on the shared material
    if (material.current) material.current.emissiveIntensity = 0.04 + 0.04 * Math.sin(state.clock.elapsedTime * 2);

    const m = mesh.current;
    if (!m || grow.current >= 1) return;
    grow.current = Math.min(1, grow.current + delta / 1.6);
    cells.forEach((cl, idx) => {
      // ripple entrance: bars rise outward from the centre of the region
      const local = Math.max(0, Math.min(1, grow.current * 1.8 - (Math.hypot(cl.x, cl.z) / maxDist) * 0.8));
      const e = 1 - Math.pow(1 - local, 3);
      const h = Math.max(0.001, heightOf(cl.slope) * e);
      dummy.position.set(cl.x, h / 2, cl.z);
      dummy.scale.set(cell * 0.8, h, cell * 0.8);
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
    const h = heightOf(cl.slope);
    if (marker.current) {
      marker.current.visible = true;
      marker.current.position.set(cl.x, h + 0.3, cl.z);
    }
    if (frame.current) {
      frame.current.visible = true;
      frame.current.position.set(cl.x, h / 2, cl.z);
      frame.current.scale.set(cell * 0.86, h * 1.02, cell * 0.86);
    }
  };
  const clearHover = () => {
    onHover(null);
    if (marker.current) marker.current.visible = false;
    if (frame.current) frame.current.visible = false;
  };

  const w = nLon * cell;
  const d = nLat * cell;
  const fmt = (v: number) => `${v.toFixed(1)}°`;

  return (
    <group>
      <instancedMesh ref={mesh} args={[geometry, undefined, cells.length]} key={cells.length} onPointerMove={handleMove} onPointerOut={clearHover}>
        <meshPhysicalMaterial ref={material} roughness={0.38} metalness={0.05} clearcoat={0.5} clearcoatRoughness={0.25} emissive={HEX.white} emissiveIntensity={0.05} envMapIntensity={0.35} />
      </instancedMesh>
      <mesh ref={marker} visible={false}>
        <octahedronGeometry args={[0.16]} />
        <meshBasicMaterial color={HEX.white} toneMapped={false} />
      </mesh>
      <mesh ref={frame} visible={false}>
        <boxGeometry args={[1, 1, 1]} />
        <meshBasicMaterial color={HEX.white} wireframe transparent opacity={0.7} toneMapped={false} />
      </mesh>

      {/* region plate: glass slab + graticule */}
      <RoundedBox args={[w + 1.2, 0.3, d + 1.2]} radius={0.14} smoothness={4} position={[0, -0.16, 0]}>
        <meshStandardMaterial color={HEX.deep} roughness={0.85} metalness={0.15} envMapIntensity={0.15} />
      </RoundedBox>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.006, 0]}>
        <planeGeometry args={[w, d]} />
        <meshBasicMaterial map={graticule} toneMapped={false} />
      </mesh>

      {/* coordinate labels at the corners */}
      <Text position={[-w / 2, 0.02, d / 2 + 0.7]} rotation={[-Math.PI / 2, 0, 0]} fontSize={0.3} color={HEX.blue} anchorX="left">
        {`${fmt(mapa.lat[nLat - 1])}  ${fmt(mapa.lon[0])}`}
      </Text>
      <Text position={[w / 2, 0.02, d / 2 + 0.7]} rotation={[-Math.PI / 2, 0, 0]} fontSize={0.3} color={HEX.blue} anchorX="right">
        {fmt(mapa.lon[nLon - 1])}
      </Text>
      <Text position={[-w / 2 - 0.7, 0.02, -d / 2]} rotation={[-Math.PI / 2, 0, Math.PI / 2]} fontSize={0.3} color={HEX.blue} anchorX="left">
        {fmt(mapa.lat[0])}
      </Text>
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
