"use client";

import { useEffect, useMemo, useRef } from "react";
import { useFrame, ThreeEvent } from "@react-three/fiber";
import { RoundedBox, Text } from "@react-three/drei";
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import type { SeriesData } from "@/lib/seriesData";
import { COLORS, HEX, divergingColor } from "@/components/analysis/palette3d";
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
const SUB = 3; // each data cell becomes SUB x SUB smooth quads
const FLOOR_Z = -2.2; // anomalies below this sit on the plinth

/** Height above the plinth for an anomaly: the landscape never sinks below the base. */
const levelOf = (z: number) => (Math.max(z, FLOOR_Z) - FLOOR_Z) * HEIGHT;

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

/** Catmull-Rom spline through p1..p2 (p0 and p3 shape the tangents). */
const catmull = (p0: number, p1: number, p2: number, p3: number, t: number) =>
  0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t);

/** Bicubic sample of a [year][month] grid, so the raw data becomes a smooth landscape. */
function sampleGrid(g: number[][], y: number, x: number) {
  const nY = g.length;
  const yi = Math.floor(y);
  const xi = Math.floor(x);
  const ty = y - yi;
  const tx = x - xi;
  const at = (r: number, c: number) => g[clamp(r, 0, nY - 1)][clamp(c, 0, 11)];
  const rows = [-1, 0, 1, 2].map((dy) => catmull(at(yi + dy, xi - 1), at(yi + dy, xi), at(yi + dy, xi + 1), at(yi + dy, xi + 2), tx));
  return catmull(rows[0], rows[1], rows[2], rows[3], ty);
}

/**
 * Contour lines and a cool rim glow added to a physical material (shaders skill, "extending built-in
 * materials"): the vertex stage forwards the height, the fragment stage draws iso-lines on it.
 */
function makeTerrainMaterial() {
  const m = new THREE.MeshPhysicalMaterial({
    vertexColors: true,
    side: THREE.DoubleSide,
    roughness: 0.4,
    metalness: 0.08,
    clearcoat: 0.4,
    clearcoatRoughness: 0.35,
  });
  m.onBeforeCompile = (shader) => {
    shader.vertexShader = "varying float vHeight;\n" + shader.vertexShader;
    shader.vertexShader = shader.vertexShader.replace("#include <begin_vertex>", "#include <begin_vertex>\n  vHeight = transformed.y;");
    shader.fragmentShader = "varying float vHeight;\n" + shader.fragmentShader;
    shader.fragmentShader = shader.fragmentShader.replace(
      "#include <color_fragment>",
      `#include <color_fragment>
      float hLine = vHeight * 2.4;
      float gLine = abs(fract(hLine - 0.5) - 0.5) / max(fwidth(hLine), 1e-4);
      float lineMask = 1.0 - clamp(gLine, 0.0, 1.0);
      diffuseColor.rgb = mix(diffuseColor.rgb, vec3(1.0), lineMask * 0.32);`
    );
    shader.fragmentShader = shader.fragmentShader.replace(
      "#include <emissivemap_fragment>",
      `#include <emissivemap_fragment>
      float rim = pow(1.0 - clamp(dot(normalize(vViewPosition), normal), 0.0, 1.0), 3.0);
      totalEmissiveRadiance += vec3(0.40, 0.61, 0.74) * rim * 0.55;`
    );
  };
  m.customProgramCacheKey = () => "moody-terrain-v1";
  return m;
}

/** Years x months landscape of standardised anomalies (blue below normal, red above), with contour lines. */
function Carpet({ data, onHover }: { data: SeriesData; onHover: (h: CarpetHover | null) => void }) {
  const nYears = data.years.length;
  const grow = useRef(0);
  const surface = useRef<THREE.Mesh>(null);
  const marker = useRef<THREE.Mesh>(null);
  const cross = useRef<THREE.Mesh>(null);

  const { geometry, heights, rawZ, rawV, rows, cols } = useMemo(() => {
    const rawZ: (number | null)[][] = Array.from({ length: nYears }, () => Array(12).fill(null));
    const rawV: (number | null)[][] = Array.from({ length: nYears }, () => Array(12).fill(null));
    for (const c of data.monthly) {
      if (c.yi >= 0) {
        rawZ[c.yi][c.m] = c.z;
        rawV[c.yi][c.m] = c.value;
      }
    }
    const g = rawZ.map((r) => r.map((v) => v ?? 0));
    const rows = (nYears - 1) * SUB + 1;
    const cols = 11 * SUB + 1;
    const heights = new Float32Array(rows * cols);
    const positions = new Float32Array(rows * cols * 3);
    const colors = new Float32Array(rows * cols * 3);
    const color = new THREE.Color();
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const i = r * cols + c;
        const z = sampleGrid(g, r / SUB, c / SUB);
        heights[i] = z;
        positions[i * 3] = (c / SUB - 5.5) * DX;
        positions[i * 3 + 2] = (r / SUB - (nYears - 1) / 2) * DZ;
        divergingColor(z, color);
        colors.set([color.r, color.g, color.b], i * 3);
      }
    }
    const index: number[] = [];
    for (let r = 0; r < rows - 1; r++) {
      for (let c = 0; c < cols - 1; c++) {
        const a = r * cols + c;
        const b = a + 1;
        const d = a + cols;
        const e = d + 1;
        index.push(a, d, b, b, d, e);
      }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    geo.setIndex(index);
    return { geometry: geo, heights, rawZ, rawV, rows, cols };
  }, [data, nYears]);

  const material = useMemo(() => makeTerrainMaterial(), []);
  useEffect(() => () => geometry.dispose(), [geometry]);
  useEffect(() => () => material.dispose(), [material]);

  // Rise-from-flat animation with a cubic ease-out.
  useFrame((_, delta) => {
    const geo = surface.current?.geometry;
    if (!geo || grow.current >= 1) return;
    grow.current = Math.min(1, grow.current + delta / 1.5);
    const e = 1 - Math.pow(1 - grow.current, 3);
    const pos = geo.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < rows * cols; i++) pos.setY(i, levelOf(heights[i]) * e);
    pos.needsUpdate = true;
    geo.computeVertexNormals();
    geo.computeBoundingSphere();
  });

  const handleMove = (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    const m = clamp(Math.round(e.point.x / DX + 5.5), 0, 11);
    const yi = clamp(Math.round(e.point.z / DZ + (nYears - 1) / 2), 0, nYears - 1);
    const z = rawZ[yi][m];
    onHover({ year: data.years[yi], month: m, z, value: rawV[yi][m] });
    const h = levelOf(z ?? 0);
    const x = (m - 5.5) * DX;
    const zz = (yi - (nYears - 1) / 2) * DZ;
    if (marker.current) {
      marker.current.visible = true;
      marker.current.position.set(x, h + 0.2, zz);
    }
    if (cross.current) {
      cross.current.visible = true;
      cross.current.position.set(x, (h + 0.2) / 2 - 0.1, zz);
      cross.current.scale.set(1, Math.max(0.01, h + 0.4), 1);
    }
  };
  const clearHover = () => {
    onHover(null);
    if (marker.current) marker.current.visible = false;
    if (cross.current) cross.current.visible = false;
  };

  return (
    <group>
      <mesh ref={surface} geometry={geometry} material={material} onPointerMove={handleMove} onPointerOut={clearHover} />
      <mesh geometry={geometry}>
        <meshBasicMaterial wireframe color={HEX.white} transparent opacity={0.035} />
      </mesh>

      {/* glass plinth under the landscape */}
      <RoundedBox args={[12 * DX + 1.4, 0.3, nYears * DZ + 1.2]} radius={0.14} smoothness={4} position={[0, -0.2, 0]}>
        <meshStandardMaterial color={HEX.deep} roughness={0.85} metalness={0.15} emissive={HEX.blue} emissiveIntensity={0.12} envMapIntensity={0.15} />
      </RoundedBox>

      <mesh ref={marker} visible={false}>
        <sphereGeometry args={[0.12, 20, 12]} />
        <meshBasicMaterial color={HEX.white} toneMapped={false} />
      </mesh>
      <mesh ref={cross} visible={false}>
        <cylinderGeometry args={[0.015, 0.015, 1, 8]} />
        <meshBasicMaterial color={HEX.white} transparent opacity={0.6} toneMapped={false} />
      </mesh>

      {MONTHS.map((l, m) => (
        <Text key={m} position={[(m - 5.5) * DX, 0.01, (nYears / 2) * DZ + 0.75]} rotation={[-Math.PI / 2, 0, 0]} fontSize={0.34} color={HEX.blue} anchorX="center">
          {l}
        </Text>
      ))}
      {data.years.map((y, yi) =>
        yi % 4 === 0 || yi === nYears - 1 ? (
          <Text key={y} position={[-6.9 * DX, 0.01, (yi - (nYears - 1) / 2) * DZ]} rotation={[-Math.PI / 2, 0, 0]} fontSize={0.3} color={HEX.blue} anchorX="right">
            {String(y)}
          </Text>
        ) : null
      )}
    </group>
  );
}

/** One rounded column per year (value) with the backend's trend line through them as a glowing tube. */
function AnnualColumns({ data }: { data: SeriesData }) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const pulse = useRef<THREE.Mesh>(null);
  const grow = useRef(0);
  const n = data.annual.length;
  const hasCarpet = data.monthly.length > 0;
  const x0 = hasCarpet ? 7.2 : 0;
  const spacing = DZ * (hasCarpet ? 1 : 1.35);

  const { norm, range } = useMemo(() => {
    const vals = data.annual.map((a) => a.value).filter((v): v is number => v !== null);
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    const r = hi - lo || 1;
    return { norm: (v: number) => 0.5 + ((v - lo) / r) * 3.2, range: r };
  }, [data]);

  const geometry = useMemo(() => new RoundedBoxGeometry(1, 1, 1, 4, 0.18), []);
  useEffect(() => () => geometry.dispose(), [geometry]);

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
    grow.current = Math.min(1, grow.current + delta / 1.6);
    for (let i = 0; i < n; i++) {
      // staggered entrance: each column starts a little after the previous one
      const local = clamp(grow.current * 1.6 - (i / n) * 0.6, 0, 1);
      const e = 1 - Math.pow(1 - local, 3);
      const v = data.annual[i].value;
      const h = (v === null ? 0.05 : norm(v)) * e + 0.02;
      dummy.position.set(x0, h / 2, (i - (n - 1) / 2) * spacing);
      dummy.scale.set(0.55, h, spacing * 0.7);
      dummy.updateMatrix();
      m.setMatrixAt(i, dummy.matrix);
    }
    m.instanceMatrix.needsUpdate = true;
  });

  const curve = useMemo(() => {
    const pts = data.annual
      .map((a, i) => (a.fitted === null ? null : new THREE.Vector3(x0, norm(a.fitted) + 0.14, (i - (n - 1) / 2) * spacing)))
      .filter((p): p is THREE.Vector3 => p !== null);
    return pts.length > 1 ? new THREE.CatmullRomCurve3(pts) : null;
  }, [data, n, norm, spacing, x0]);

  const tube = useMemo(() => (curve ? new THREE.TubeGeometry(curve, 96, 0.055, 10, false) : null), [curve]);
  const halo = useMemo(() => (curve ? new THREE.TubeGeometry(curve, 96, 0.16, 10, false) : null), [curve]);
  useEffect(() => () => { tube?.dispose(); halo?.dispose(); }, [tube, halo]);

  const lineColor = data.significant ? HEX.red : HEX.olive;
  const arrow = useMemo(() => {
    if (!curve) return null;
    const end = curve.getPoint(1);
    const dir = curve.getTangent(1);
    return { end, quat: new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir) };
  }, [curve]);

  // A bead of light travels along the trend line, in the direction of time.
  useFrame((state) => {
    if (!pulse.current || !curve) return;
    const u = (state.clock.elapsedTime * 0.18) % 1;
    pulse.current.position.copy(curve.getPointAt(u));
  });

  return (
    <group>
      <instancedMesh ref={mesh} args={[geometry, undefined, n]}>
        <meshPhysicalMaterial roughness={0.28} metalness={0.1} clearcoat={0.7} clearcoatRoughness={0.2} emissive={HEX.white} emissiveIntensity={0.1} />
      </instancedMesh>
      {tube && halo && arrow && (
        <>
          <mesh geometry={tube}>
            <meshBasicMaterial color={lineColor} toneMapped={false} />
          </mesh>
          <mesh geometry={halo}>
            <meshBasicMaterial color={lineColor} transparent opacity={0.22} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
          </mesh>
          <mesh position={arrow.end} quaternion={arrow.quat}>
            <coneGeometry args={[0.2, 0.5, 20]} />
            <meshBasicMaterial color={lineColor} toneMapped={false} />
          </mesh>
          <mesh ref={pulse}>
            <sphereGeometry args={[0.13, 16, 12]} />
            <meshBasicMaterial color={HEX.white} toneMapped={false} />
          </mesh>
        </>
      )}
      {data.annual.map((a, i) =>
        i % 4 === 0 || i === n - 1 ? (
          <Text key={a.year} position={[x0 + 0.9, 0.01, (i - (n - 1) / 2) * spacing]} rotation={[-Math.PI / 2, 0, 0]} fontSize={0.28} color={HEX.blue} anchorX="left">
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
      <gridHelper args={[30, 30, HEX.blue, HEX.blue]} position={[hasCarpet ? 2.6 : 0, -0.04, 0]} material-transparent material-opacity={0.22} />
    </SceneShell>
  );
}
