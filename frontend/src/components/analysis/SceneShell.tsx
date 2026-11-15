"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, PerformanceMonitor } from "@react-three/drei";
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { useTheme } from "@/context/ThemeContext";
import { SCENE_BG } from "@/components/analysis/palette3d";

/**
 * Selective glow: the composer renders the scene, blooms only what is brighter than `threshold`
 * (emissive bars, nodes, hot peaks) and ends with OutputPass. It takes over rendering, so it runs at
 * a positive priority (see the react-three-fiber and post-processing skills).
 */
function Bloom({ strength = 0.45, radius = 0.55, threshold = 0.9 }: { strength?: number; radius?: number; threshold?: number }) {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const size = useThree((s) => s.size);
  const dpr = useThree((s) => s.viewport.dpr);

  const composer = useMemo(() => {
    const c = new EffectComposer(gl);
    c.addPass(new RenderPass(scene, camera));
    c.addPass(new UnrealBloomPass(new THREE.Vector2(size.width, size.height), strength, radius, threshold));
    c.addPass(new OutputPass());
    return c;
    // size is applied in the effect below; the passes only need to be rebuilt when the context changes
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

/** Shared canvas for every 3D analysis view: palette lights, damped orbit controls, bloom, adaptive resolution. */
export function SceneShell({
  children,
  camera = [9, 8, 12],
  target = [0, 1, 0],
  autoRotate = true,
  bloom = true,
}: {
  children: React.ReactNode;
  camera?: [number, number, number];
  target?: [number, number, number];
  autoRotate?: boolean;
  bloom?: boolean;
}) {
  const { theme } = useTheme();
  const [dpr, setDpr] = useState<[number, number]>([1, 2]);
  const bg = theme === "dark" ? SCENE_BG.dark : SCENE_BG.light;

  return (
    <Canvas
      dpr={dpr}
      flat
      camera={{ position: camera, fov: 42, near: 0.1, far: 200 }}
      gl={{ antialias: true, powerPreference: "high-performance" }}
      className="touch-none"
    >
      <color attach="background" args={[bg]} />
      <fog attach="fog" args={[bg, 28, 60]} />
      <hemisphereLight args={["#bcd9ea", "#0b2a3c", theme === "dark" ? 0.55 : 1.0]} />
      <directionalLight position={[8, 12, 6]} intensity={theme === "dark" ? 1.5 : 2.0} color="#ffffff" />
      <directionalLight position={[-8, 5, -6]} intensity={0.9} color="#669bbc" />
      <Suspense fallback={null}>{children}</Suspense>
      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.08}
        target={target}
        minDistance={4}
        maxDistance={34}
        maxPolarAngle={Math.PI / 2.05}
        autoRotate={autoRotate}
        autoRotateSpeed={0.35}
      />
      <PerformanceMonitor onDecline={() => setDpr([1, 1])} onIncline={() => setDpr([1, 2])} />
      {bloom && <Bloom />}
    </Canvas>
  );
}
