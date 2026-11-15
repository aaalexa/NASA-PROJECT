"use client";

import { useEffect, useMemo, useRef } from "react";
import { useFrame, ThreeEvent } from "@react-three/fiber";
import { Line, Text } from "@react-three/drei";
import * as THREE from "three";
import type { SeriesData } from "@/lib/seriesData";
import { COLORS, divergingColor } from "@/components/analysis/palette3d";
import { SceneShell } from "@/components/analysis/SceneShell";

export interface CarpetHover {
  year: number;
  month: number;
  z: number | null;
  value: number | null;
}

const MONTHS = ["E", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
const DX = 0.9; // spacing between months
const DZ = 0.55; // spacing between years
const HEIGHT = 0.95; // height of one standard deviation

/** Years x months heightfield of standardised anomalies (blue below normal, red above). */
function Carpet({ data, onHover }: { data: SeriesData; onHover: (h: CarpetHover | null) => void }) {
  const nYears = data.years.length;
  const grow = useRef(0);
  const marker = useRef<THREE.Mesh>(null);
  const surface = useRef<THREE.Mesh>(null);

  const { geometry, grid } = useMemo(() => {
    const grid: (number | null)[][] = Array.from({ length: nYears }, () => Array(12).fill(null));
    const values: (number | null)[][] = Array.from({ length: nYears }, () => Array(12).fill(null));
    for (const c of data.monthly) {
      if (c.yi >= 0) {
        grid[c.yi][c.m] = c.z;
        values[c.yi][c.m] = c.value;
      }
    }
    const geo = new THREE.BufferGeometry();
    const count = nYears * 12;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const color = new THREE.Color();
    for (let yi = 0; yi < nYears; yi++) {
      for (let m = 0; m < 12; m++) {
        const i = yi * 12 + m;
        positions[i * 3] = (m - 5.5) * DX;
        positions[i * 3 + 2] = (yi - (nYears - 1) / 2) * DZ;
        const z = grid[yi][m] ?? 0;
        divergingColor(z, color);
        colors.set([color.r, color.g, color.b], i * 3);
      }
    }
    const index: number[] = [];
    for (let yi = 0; yi < nYears - 1; yi++) {
      for (let m = 0; m < 11; m++) {
        const a = yi * 12 + m;
        const b = a + 1;
        const c = a + 12;
        const d = c + 1;
        index.push(a, c, b, b, c, d);
      }
    }
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    geo.setIndex(index);
    return { geometry: geo, grid: { z: grid, v: values } };
  }, [data, nYears]);

  useEffect(() => () => geometry.dispose(), [geometry]);

  // Rise-from-flat animation: ease the heights in over ~1.2 s.
  useFrame((_, delta) => {
    const geo = surface.current?.geometry;
    if (!geo || grow.current >= 1) return;
    grow.current = Math.min(1, grow.current + delta / 1.2);
    const e = 1 - Math.pow(1 - grow.current, 3);
    const pos = geo.attributes.position as THREE.BufferAttribute;
    for (let yi = 0; yi < nYears; yi++) {
      for (let m = 0; m < 12; m++) {
        pos.setY(yi * 12 + m, (grid.z[yi][m] ?? 0) * HEIGHT * e);
      }
    }
    pos.needsUpdate = true;
    geo.computeVertexNormals();
    geo.computeBoundingSphere();
  });

  const handleMove = (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    const m = Math.max(0, Math.min(11, Math.round(e.point.x / DX + 5.5)));
    const yi = Math.max(0, Math.min(nYears - 1, Math.round(e.point.z / DZ + (nYears - 1) / 2)));
    const z = grid.z[yi][m];
    onHover({ year: data.years[yi], month: m, z, value: grid.v[yi][m] });
    if (marker.current) {
      marker.current.visible = true;
      marker.current.position.set((m - 5.5) * DX, (z ?? 0) * HEIGHT + 0.15, (yi - (nYears - 1) / 2) * DZ);
    }
  };

  return (
    <group>
      <mesh ref={surface} geometry={geometry} onPointerMove={handleMove} onPointerOut={() => { onHover(null); if (marker.current) marker.current.visible = false; }}>
        <meshStandardMaterial vertexColors side={THREE.DoubleSide} roughness={0.5} metalness={0.15} emissive="#ffffff" emissiveIntensity={0.04} />
      </mesh>
      <mesh geometry={geometry}>
        <meshBasicMaterial wireframe color="#ffffff" transparent opacity={0.07} />
      </mesh>
      <mesh ref={marker} visible={false}>
        <sphereGeometry args={[0.13, 20, 12]} />
        <meshBasicMaterial color="#ffffff" toneMapped={false} />
      </mesh>
      {MONTHS.map((l, m) => (
        <Text key={m} position={[(m - 5.5) * DX, 0.01, (nYears / 2) * DZ + 0.55]} rotation={[-Math.PI / 2, 0, 0]} fontSize={0.34} color="#9cb8c9" anchorX="center">
          {l}
        </Text>
      ))}
      {data.years.map((y, yi) =>
        yi % 4 === 0 || yi === nYears - 1 ? (
          <Text key={y} position={[-6.6 * DX, 0.01, (yi - (nYears - 1) / 2) * DZ]} rotation={[-Math.PI / 2, 0, 0]} fontSize={0.3} color="#9cb8c9" anchorX="right">
            {String(y)}
          </Text>
        ) : null
      )}
    </group>
  );
}

/** One column per year (value) with the backend's trend line through them. */
function AnnualColumns({ data }: { data: SeriesData }) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const grow = useRef(0);
  const n = data.annual.length;
  const x0 = data.monthly.length ? 6.9 : 0;

  const { norm, min, range } = useMemo(() => {
    const vals = data.annual.map((a) => a.value).filter((v): v is number => v !== null);
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    const r = hi - lo || 1;
    return { norm: (v: number) => 0.5 + ((v - lo) / r) * 3.2, min: lo, range: r };
  }, [data]);

  const colors = useMemo(() => {
    const c = new THREE.Color();
    return data.annual.map((a) => {
      if (a.value === null) return COLORS.deep.clone();
      const z = a.fitted === null ? 0 : (a.value - a.fitted) / (range * 0.12);
      return divergingColor(z, c).clone();
    });
  }, [data, range]);

  useEffect(() => {
    const m = mesh.current;
    if (!m) return;
    colors.forEach((c, i) => m.setColorAt(i, c));
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
    grow.current = 0;
  }, [colors]);

  const dummy = useMemo(() => new THREE.Object3D(), []);
  useFrame((_, delta) => {
    const m = mesh.current;
    if (!m || grow.current >= 1) return;
    grow.current = Math.min(1, grow.current + delta / 1.4);
    const e = 1 - Math.pow(1 - grow.current, 3);
    for (let i = 0; i < n; i++) {
      const v = data.annual[i].value;
      const h = (v === null ? 0.05 : norm(v)) * e + 0.02;
      dummy.position.set(x0, h / 2, (i - (n - 1) / 2) * DZ * (data.monthly.length ? 1 : 1.35));
      dummy.scale.set(0.5, h, DZ * 0.62 * (data.monthly.length ? 1 : 1.35));
      dummy.updateMatrix();
      m.setMatrixAt(i, dummy.matrix);
    }
    m.instanceMatrix.needsUpdate = true;
  });

  const spacing = DZ * (data.monthly.length ? 1 : 1.35);
  const line = useMemo(
    () =>
      data.annual
        .map((a, i) => (a.fitted === null ? null : new THREE.Vector3(x0, norm(a.fitted) + 0.12, (i - (n - 1) / 2) * spacing)))
        .filter((p): p is THREE.Vector3 => p !== null),
    [data, n, norm, spacing, x0]
  );
  void min;

  return (
    <group>
      <instancedMesh ref={mesh} args={[undefined, undefined, n]}>
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial roughness={0.4} metalness={0.2} emissive="#ffffff" emissiveIntensity={0.12} />
      </instancedMesh>
      {line.length > 1 && <Line points={line} color={data.significant ? "#ff4d5a" : "#c9bd6a"} lineWidth={3} />}
      {data.annual.map((a, i) =>
        i % 4 === 0 || i === n - 1 ? (
          <Text key={a.year} position={[x0 + 0.8, 0.01, (i - (n - 1) / 2) * spacing]} rotation={[-Math.PI / 2, 0, 0]} fontSize={0.28} color="#9cb8c9" anchorX="left">
            {String(a.year)}
          </Text>
        ) : null
      )}
    </group>
  );
}

export default function CarpetScene({ data, onHover }: { data: SeriesData; onHover: (h: CarpetHover | null) => void }) {
  const hasCarpet = data.monthly.length > 0;
  return (
    <SceneShell camera={hasCarpet ? [15, 11, 19] : [9, 7, 12]} target={[hasCarpet ? 2.6 : 0, 0.6, 0]}>
      {hasCarpet && <Carpet data={data} onHover={onHover} />}
      <AnnualColumns data={data} />
      <gridHelper args={[26, 26, "#2c6a8a", "#124561"]} position={[hasCarpet ? 3 : 0, -0.02, 0]} />
    </SceneShell>
  );
}
