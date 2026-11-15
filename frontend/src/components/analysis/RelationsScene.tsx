"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { Billboard, Text } from "@react-three/drei";
import * as THREE from "three";
import { DteCode, DteResult } from "@/lib/api";
import { COLORS, HEX, VAR_COLORS } from "@/components/analysis/palette3d";
import { SceneShell } from "@/components/analysis/SceneShell";

const NODE_POS: Record<DteCode, THREE.Vector3> = {
  P: new THREE.Vector3(0, 2.6, -0.6),
  SM: new THREE.Vector3(-3.4, 0.9, 1.1),
  ET: new THREE.Vector3(3.4, 0.9, 1.1),
  T: new THREE.Vector3(-6.4, 2.4, -0.9),
};

interface Edge {
  pair: string;
  a: DteCode;
  b: DteCode;
  r: number;
}

/** Rim-light aura: additive Fresnel shell (shaders skill), brighter where the surface turns away. */
const auraVertex = /* glsl */ `
  varying vec3 vWorldNormal;
  varying vec3 vWorldPosition;
  void main() {
    vWorldNormal = normalize(mat3(modelMatrix) * normal);
    vWorldPosition = (modelMatrix * vec4(position, 1.0)).xyz;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;
const auraFragment = /* glsl */ `
  uniform vec3 uColor;
  uniform float uPower;
  uniform float uStrength;
  varying vec3 vWorldNormal;
  varying vec3 vWorldPosition;
  void main() {
    vec3 viewDirection = normalize(cameraPosition - vWorldPosition);
    float fresnel = pow(1.0 - max(dot(viewDirection, normalize(vWorldNormal)), 0.0), uPower);
    gl_FragColor = vec4(uColor * fresnel * uStrength, fresnel * uStrength);
  }
`;

function Aura({ color, radius, strength = 1.2 }: { color: THREE.Color; radius: number; strength?: number }) {
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: auraVertex,
        fragmentShader: auraFragment,
        uniforms: { uColor: { value: color.clone() }, uPower: { value: 2.4 }, uStrength: { value: strength } },
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        side: THREE.FrontSide,
      }),
    [color, strength]
  );
  useEffect(() => () => material.dispose(), [material]);
  return (
    <mesh material={material} scale={radius * 1.45}>
      <sphereGeometry args={[1, 48, 32]} />
    </mesh>
  );
}

function EdgeMesh({ edge }: { edge: Edge }) {
  const flow = useRef<THREE.InstancedMesh>(null);
  const a = NODE_POS[edge.a];
  const b = NODE_POS[edge.b];
  const strength = Math.min(1, Math.abs(edge.r));
  const color = edge.r >= 0 ? COLORS.blue : COLORS.red;
  const count = 16;

  // The link arcs upward so it never hides behind the spheres; stronger links arc less.
  const curve = useMemo(() => {
    const mid = new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5);
    mid.y += 1.1 - 0.5 * strength;
    return new THREE.QuadraticBezierCurve3(a.clone(), mid, b.clone());
  }, [a, b, strength]);

  const tube = useMemo(() => new THREE.TubeGeometry(curve, 64, 0.045 + 0.17 * strength, 16, false), [curve, strength]);
  useEffect(() => () => tube.dispose(), [tube]);

  const dummy = useMemo(() => new THREE.Object3D(), []);
  const point = useMemo(() => new THREE.Vector3(), []);
  // Particles travel along the link; faster for stronger correlations.
  useFrame((state) => {
    const m = flow.current;
    if (!m) return;
    const t = state.clock.elapsedTime * (0.12 + strength * 0.45);
    for (let i = 0; i < count; i++) {
      const u = (i / count + t) % 1;
      curve.getPointAt(u, point);
      dummy.position.copy(point);
      dummy.scale.setScalar(0.45 + 0.75 * Math.sin(u * Math.PI));
      dummy.updateMatrix();
      m.setMatrixAt(i, dummy.matrix);
    }
    m.instanceMatrix.needsUpdate = true;
  });

  const labelPos = curve.getPoint(0.5);
  return (
    <group>
      <mesh geometry={tube}>
        <meshPhysicalMaterial color={color} transparent opacity={0.3 + 0.3 * strength} roughness={0.2} clearcoat={1} emissive={color} emissiveIntensity={0.6} />
      </mesh>
      <instancedMesh ref={flow} args={[undefined, undefined, count]}>
        <sphereGeometry args={[0.085, 14, 10]} />
        <meshBasicMaterial color={color.clone().lerp(COLORS.white, 0.45)} toneMapped={false} />
      </instancedMesh>
      <Billboard position={[labelPos.x, labelPos.y + 0.95, labelPos.z]}>
        <Text fontSize={0.33} color={HEX.white} outlineWidth={0.015} outlineColor={HEX.deep} anchorX="center">
          {`${edge.pair.replace("-", " · ")}   r = ${edge.r >= 0 ? "+" : ""}${edge.r.toFixed(2)}`}
        </Text>
      </Billboard>
    </group>
  );
}

function Node({
  code,
  direction,
  significance,
  selected,
  onSelect,
}: {
  code: DteCode;
  direction: "aumento" | "disminucion" | "estable";
  /** 0..1, how strong the (Holm-adjusted) evidence for the trend is; sets the sphere size. */
  significance: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const group = useRef<THREE.Group>(null);
  const moons = useRef<THREE.Group>(null);
  const [hover, setHover] = useState(false);
  const color = VAR_COLORS[code];
  const radius = 0.5 + 0.38 * significance;
  const arrowColor = direction === "aumento" ? COLORS.red : direction === "disminucion" ? COLORS.blue : COLORS.olive;
  const scaleTarget = hover || selected ? 1.14 : 1;

  useFrame((state, delta) => {
    const g = group.current;
    if (g) {
      g.position.y = NODE_POS[code].y + Math.sin(state.clock.elapsedTime * 0.9 + code.charCodeAt(0)) * 0.09;
      const s = THREE.MathUtils.damp(g.scale.x, scaleTarget, 8, delta); // exponential approach
      g.scale.setScalar(s);
    }
    if (moons.current) moons.current.rotation.y += delta * (selected ? 1.4 : 0.7);
  });

  return (
    <group ref={group} position={NODE_POS[code]}>
      <mesh onClick={(e) => { e.stopPropagation(); onSelect(); }} onPointerOver={() => setHover(true)} onPointerOut={() => setHover(false)}>
        <sphereGeometry args={[radius, 64, 40]} />
        <meshPhysicalMaterial color={color} roughness={0.18} metalness={0.05} clearcoat={1} clearcoatRoughness={0.1} emissive={color} emissiveIntensity={selected ? 0.8 : 0.4} />
      </mesh>
      <Aura color={color} radius={radius} strength={selected ? 1.8 : 1.1} />
      <group ref={moons} rotation={[0.5, 0, 0.3]}>
        {[0, 1, 2].map((i) => (
          <mesh key={i} position={[Math.cos((i / 3) * Math.PI * 2) * (radius + 0.5), 0, Math.sin((i / 3) * Math.PI * 2) * (radius + 0.5)]}>
            <sphereGeometry args={[0.06, 12, 8]} />
            <meshBasicMaterial color={selected ? HEX.white : color} toneMapped={false} />
          </mesh>
        ))}
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[radius + 0.5, 0.012, 8, 96]} />
          <meshBasicMaterial color={color} transparent opacity={selected ? 0.7 : 0.25} toneMapped={false} />
        </mesh>
      </group>
      {direction !== "estable" && (
        <mesh position={[0, direction === "aumento" ? radius + 0.85 : -(radius + 0.85), 0]} rotation={[direction === "disminucion" ? Math.PI : 0, 0, 0]}>
          <coneGeometry args={[0.2, 0.5, 24]} />
          <meshStandardMaterial color={arrowColor} emissive={arrowColor} emissiveIntensity={1} roughness={0.3} />
        </mesh>
      )}
      <Billboard position={[0, radius + (direction === "aumento" ? 1.55 : 0.75), 0]}>
        <Text fontSize={0.5} color={HEX.white} outlineWidth={0.02} outlineColor={HEX.deep} anchorX="center" fontWeight="bold">
          {code}
        </Text>
      </Billboard>
    </group>
  );
}

/** The four core variables as a 3D network: link thickness and flow follow |r|, sphere size follows the evidence. */
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
    <SceneShell camera={[4, 6, 19]} target={[-1.2, 1.4, 0]} shadows={false}>
      {(Object.keys(NODE_POS) as DteCode[]).map((code) => {
        const p = dte.variables[code].p_holm;
        const significance = p === null || p <= 0 ? 1 : Math.max(0, Math.min(1, -Math.log10(p) / 20));
        return <Node key={code} code={code} direction={dte.variables[code].direction} significance={significance} selected={selected === code} onSelect={() => onSelect(code)} />;
      })}
      {edges.map((e) => (
        <EdgeMesh key={e.pair} edge={e} />
      ))}
      <gridHelper args={[30, 30, HEX.blue, HEX.blue]} position={[-1.2, -1.6, 0]} material-transparent material-opacity={0.22} />
    </SceneShell>
  );
}
