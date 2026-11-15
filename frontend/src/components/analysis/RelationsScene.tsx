"use client";

import { useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { Billboard, Text } from "@react-three/drei";
import * as THREE from "three";
import { DteCode, DteResult } from "@/lib/api";
import { COLORS, VAR_COLORS } from "@/components/analysis/palette3d";
import { SceneShell } from "@/components/analysis/SceneShell";

const NODE_POS: Record<DteCode, THREE.Vector3> = {
  P: new THREE.Vector3(0, 2.6, -0.6),
  SM: new THREE.Vector3(-3.4, 0.9, 1.1),
  ET: new THREE.Vector3(3.4, 0.9, 1.1),
  T: new THREE.Vector3(-6.4, 2.4, -0.9),
};

const NAMES: Record<DteCode, string> = { P: "P", T: "T", SM: "SM", ET: "ET" };
const UP = new THREE.Vector3(0, 1, 0);

interface Edge {
  pair: string;
  a: DteCode;
  b: DteCode;
  r: number;
}

function EdgeMesh({ edge }: { edge: Edge }) {
  const flow = useRef<THREE.InstancedMesh>(null);
  const a = NODE_POS[edge.a];
  const b = NODE_POS[edge.b];
  const { mid, quat, length } = useMemo(() => {
    const dir = new THREE.Vector3().subVectors(b, a);
    return {
      mid: new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5),
      quat: new THREE.Quaternion().setFromUnitVectors(UP, dir.clone().normalize()),
      length: dir.length(),
    };
  }, [a, b]);

  const strength = Math.min(1, Math.abs(edge.r));
  const color = edge.r >= 0 ? COLORS.blue : COLORS.red;
  const count = 14;
  const dummy = useMemo(() => new THREE.Object3D(), []);

  // Particles travel along the link; faster and denser for stronger correlations.
  useFrame((state) => {
    const m = flow.current;
    if (!m) return;
    const t = state.clock.elapsedTime * (0.15 + strength * 0.5);
    for (let i = 0; i < count; i++) {
      const u = (i / count + t) % 1;
      dummy.position.lerpVectors(a, b, u);
      dummy.scale.setScalar(0.5 + 0.5 * Math.sin(u * Math.PI));
      dummy.updateMatrix();
      m.setMatrixAt(i, dummy.matrix);
    }
    m.instanceMatrix.needsUpdate = true;
  });

  return (
    <group>
      <mesh position={mid} quaternion={quat}>
        <cylinderGeometry args={[0.05 + 0.2 * strength, 0.05 + 0.2 * strength, length, 24, 1, true]} />
        <meshStandardMaterial color={color} transparent opacity={0.28 + 0.35 * strength} emissive={color} emissiveIntensity={0.5} side={THREE.DoubleSide} />
      </mesh>
      <instancedMesh ref={flow} args={[undefined, undefined, count]}>
        <sphereGeometry args={[0.08, 12, 8]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </instancedMesh>
      <Billboard position={[mid.x, mid.y + 0.55, mid.z]}>
        <Text fontSize={0.34} color="#ffffff" outlineWidth={0.015} outlineColor="#00202f" anchorX="center">
          {`${edge.pair.replace("-", " · ")}  r = ${edge.r >= 0 ? "+" : ""}${edge.r.toFixed(2)}`}
        </Text>
      </Billboard>
    </group>
  );
}

function Node({ code, direction, selected, onSelect }: { code: DteCode; direction: "aumento" | "disminucion" | "estable"; selected: boolean; onSelect: () => void }) {
  const group = useRef<THREE.Group>(null);
  const ring = useRef<THREE.Mesh>(null);
  const color = VAR_COLORS[code];
  const arrowColor = direction === "aumento" ? COLORS.red : direction === "disminucion" ? COLORS.blue : COLORS.olive;
  const [hover, setHover] = useState(false);

  useFrame((state, delta) => {
    if (group.current) group.current.position.y = NODE_POS[code].y + Math.sin(state.clock.elapsedTime * 0.9 + code.charCodeAt(0)) * 0.08;
    if (ring.current) ring.current.rotation.z += delta * 0.8;
  });

  return (
    <group ref={group} position={NODE_POS[code]}>
      <mesh onClick={(e) => { e.stopPropagation(); onSelect(); }} onPointerOver={() => setHover(true)} onPointerOut={() => setHover(false)} scale={hover || selected ? 1.15 : 1}>
        <sphereGeometry args={[0.62, 48, 32]} />
        <meshPhysicalMaterial color={color} roughness={0.25} metalness={0.1} clearcoat={0.6} emissive={color} emissiveIntensity={selected ? 0.9 : 0.45} />
      </mesh>
      <mesh ref={ring} rotation={[Math.PI / 2.4, 0, 0]}>
        <torusGeometry args={[0.95, 0.02, 12, 80]} />
        <meshBasicMaterial color={selected ? "#ffffff" : color} transparent opacity={selected ? 0.9 : 0.35} toneMapped={false} />
      </mesh>
      {/* trend arrow: up (increase), down (decrease) or a flat disc (no clear change) */}
      <mesh position={[0, direction === "estable" ? 0 : direction === "aumento" ? 1.25 : -1.25, 0]} rotation={[direction === "disminucion" ? Math.PI : 0, 0, 0]} visible={direction !== "estable"}>
        <coneGeometry args={[0.22, 0.55, 20]} />
        <meshStandardMaterial color={arrowColor} emissive={arrowColor} emissiveIntensity={0.8} />
      </mesh>
      <Billboard position={[0, direction === "aumento" ? 1.95 : 1.15, 0]}>
        <Text fontSize={0.5} color="#ffffff" outlineWidth={0.02} outlineColor="#00202f" anchorX="center" fontWeight="bold">
          {NAMES[code]}
        </Text>
      </Billboard>
    </group>
  );
}

/** The four core variables as a 3D network: link thickness and flow speed follow |r|. */
export default function RelationsScene({
  dte,
  selected,
  onSelect,
}: {
  dte: DteResult;
  selected: DteCode | null;
  onSelect: (code: DteCode) => void;
}) {
  const edges: Edge[] = dte.joint.pairs_list
    .filter((p) => p.r !== null)
    .map((p) => ({ pair: p.pair, a: p.var_x as DteCode, b: p.var_y as DteCode, r: p.r as number }));

  return (
    <SceneShell camera={[4, 6, 19]} target={[-1.2, 1.4, 0]}>
      {(Object.keys(NODE_POS) as DteCode[]).map((code) => (
        <Node key={code} code={code} direction={dte.variables[code].direction} selected={selected === code} onSelect={() => onSelect(code)} />
      ))}
      {edges.map((e) => (
        <EdgeMesh key={e.pair} edge={e} />
      ))}
      <gridHelper args={[26, 26, "#2c6a8a", "#124561"]} position={[-1.2, -1.4, 0]} />
    </SceneShell>
  );
}
