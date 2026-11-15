"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { ContactShadows, Environment, Lightformer, OrbitControls, PerformanceMonitor } from "@react-three/drei";
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { SMAAPass } from "three/addons/postprocessing/SMAAPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { HEX } from "@/components/analysis/palette3d";

/**
 * Post-processing chain (see the post-processing skill): RenderPass -> UnrealBloom (only what is
 * brighter than `threshold` glows) -> SMAA (the composer's targets are not multisampled, so edges
 * need it) -> OutputPass (tone mapping and colour space, always last). It takes over rendering, so
 * it runs at a positive priority.
 */
function Effects({ strength = 0.42, radius = 0.55, threshold = 0.9 }: { strength?: number; radius?: number; threshold?: number }) {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const size = useThree((s) => s.size);
  const dpr = useThree((s) => s.viewport.dpr);

  const composer = useMemo(() => {
    const c = new EffectComposer(gl);
    c.addPass(new RenderPass(scene, camera));
    c.addPass(new UnrealBloomPass(new THREE.Vector2(size.width, size.height), strength, radius, threshold));
    c.addPass(new SMAAPass());
    c.addPass(new OutputPass());
    return c;
    // size is applied in the effect below; passes are only rebuilt when the context changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gl, scene, camera, strength, radius, threshold]);

  useEffect(() => {
    composer.setPixelRatio(dpr);
    composer.setSize(size.width, size.height);
  }, [composer, size, dpr]);

  useEffect(() => () => composer.dispose(), [composer]);

  useFrame(() => composer.render(), 1);
  return null;
}

/** Image-based lighting from procedural light cards: PBR materials get soft reflections with no download. */
function Studio() {
  return (
    <Environment resolution={256} environmentIntensity={0.85}>
      <Lightformer form="rect" intensity={2.2} position={[0, 6, 5]} scale={[12, 3, 1]} color={HEX.white} />
      <Lightformer form="ring" intensity={1.6} position={[-7, 3, -4]} scale={5} color={HEX.blue} />
      <Lightformer form="rect" intensity={1.3} position={[7, 1.5, -3]} scale={[7, 2, 1]} color={HEX.red} />
      <Lightformer form="circle" intensity={1.0} position={[0, -2, 6]} scale={6} color={HEX.olive} />
    </Environment>
  );
}

/** Soft radial glow under the content, drawn once into a CanvasTexture. */
function GroundGlow({ y = -0.03, size = 46 }: { y?: number; size?: number }) {
  const texture = useMemo(() => {
    const c = document.createElement("canvas");
    c.width = c.height = 512;
    const g = c.getContext("2d")!;
    const grad = g.createRadialGradient(256, 256, 10, 256, 256, 256);
    grad.addColorStop(0, "rgba(102,155,188,0.38)"); // steel blue
    grad.addColorStop(0.5, "rgba(102,155,188,0.1)");
    grad.addColorStop(1, "rgba(0,48,73,0)"); // deep space blue, transparent
    g.fillStyle = grad;
    g.fillRect(0, 0, 512, 512);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, []);
  useEffect(() => () => texture.dispose(), [texture]);
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, y, 0]} renderOrder={-1}>
      <planeGeometry args={[size, size]} />
      <meshBasicMaterial map={texture} transparent depthWrite={false} toneMapped={false} />
    </mesh>
  );
}

/** A slowly turning cloud of dust motes: depth cue and atmosphere. */
function Dust({ count = 300, radius = 9 }: { count?: number; radius?: number }) {
  const points = useRef<THREE.Points>(null);
  const positions = useMemo(() => {
    // Seeded generator: the dust looks the same on every render and the memo stays pure.
    let seed = 0x9e3779b9;
    const rand = () => {
      seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const r = radius * Math.cbrt(rand());
      const theta = rand() * Math.PI * 2;
      const phi = Math.acos(2 * rand() - 1);
      arr[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      arr[i * 3 + 1] = Math.abs(r * Math.cos(phi)) * 0.6 + 0.2;
      arr[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
    }
    return arr;
  }, [count, radius]);
  useFrame((_, delta) => {
    if (points.current) points.current.rotation.y += delta * 0.015;
  });
  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.03} color={HEX.blue} transparent opacity={0.55} sizeAttenuation depthWrite={false} toneMapped={false} />
    </points>
  );
}

/** Flies the camera in from a wider, higher view with an exponential ease (frame-rate independent). */
function CameraIntro({ to, duration = 1.8 }: { to: [number, number, number]; duration?: number }) {
  const camera = useThree((s) => s.camera);
  const start = useRef<THREE.Vector3 | null>(null);
  const end = useMemo(() => new THREE.Vector3(...to), [to]);
  const t = useRef(0);
  useFrame((_, delta) => {
    if (t.current >= 1) return;
    if (!start.current) {
      start.current = new THREE.Vector3(to[0] * 1.7, to[1] * 1.9 + 4, to[2] * 1.7);
      camera.position.copy(start.current);
    }
    t.current = Math.min(1, t.current + delta / duration);
    const e = 1 - Math.pow(1 - t.current, 4);
    camera.position.lerpVectors(start.current, end, e);
  });
  return null;
}

/** Shared canvas for every 3D analysis view: IBL, palette lights, damped orbit controls, effects, adaptive resolution. */
export function SceneShell({
  children,
  camera = [9, 8, 12],
  target = [0, 1, 0],
  autoRotate = true,
  shadows = true,
}: {
  children: React.ReactNode;
  camera?: [number, number, number];
  target?: [number, number, number];
  autoRotate?: boolean;
  shadows?: boolean;
}) {
  const [dpr, setDpr] = useState<[number, number]>([1, 2]);
  // The 3D stage is always deep space blue: the palette colours keep their contrast in light and dark mode.
  const bg = HEX.deep;

  return (
    <Canvas
      dpr={dpr}
      flat
      camera={{ position: camera, fov: 42, near: 0.1, far: 200 }}
      gl={{ antialias: true, powerPreference: "high-performance" }}
      className="touch-none"
    >
      <color attach="background" args={[bg]} />
      <fog attach="fog" args={[bg, 30, 64]} />
      <hemisphereLight args={[HEX.white, HEX.deep, 0.5]} />
      <directionalLight position={[8, 12, 6]} intensity={1.4} color={HEX.white} />
      <directionalLight position={[-8, 5, -6]} intensity={0.8} color={HEX.blue} />
      <Suspense fallback={null}>
        <Studio />
        <GroundGlow />
        <Dust />
        {children}
        {shadows && <ContactShadows position={[0, -0.02, 0]} opacity={0.55} scale={30} blur={2.6} far={6} resolution={512} color={HEX.deep} />}
      </Suspense>
      <CameraIntro to={camera} />
      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.08}
        target={target}
        minDistance={4}
        maxDistance={36}
        maxPolarAngle={Math.PI / 2.05}
        autoRotate={autoRotate}
        autoRotateSpeed={0.3}
      />
      <PerformanceMonitor onDecline={() => setDpr([1, 1])} onIncline={() => setDpr([1, 2])} />
      <Effects />
    </Canvas>
  );
}
