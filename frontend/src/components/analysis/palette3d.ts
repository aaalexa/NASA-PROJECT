import * as THREE from "three";

/** Moody Trends palette as three.js colours. */
export const COLORS = {
  lava: new THREE.Color("#780000"),
  red: new THREE.Color("#c1121f"),
  deep: new THREE.Color("#003049"),
  blue: new THREE.Color("#669bbc"),
  olive: new THREE.Color("#9c914f"),
  white: new THREE.Color("#ffffff"),
};

export const SCENE_BG = { dark: "#00202f", light: "#eaf1f6" } as const;

const tmp = new THREE.Color();

/**
 * Diverging colour for a standardised anomaly: steel blue (below normal) -> palm leaf (normal)
 * -> brick red (above normal) -> molten lava (extreme). Writes into `out` and returns it.
 */
export function divergingColor(z: number, out: THREE.Color = tmp): THREE.Color {
  const c = Math.max(-3, Math.min(3, z));
  if (c < 0) return out.copy(COLORS.olive).lerp(COLORS.blue, Math.min(1, -c / 2));
  if (c <= 2) return out.copy(COLORS.olive).lerp(COLORS.red, c / 2);
  return out.copy(COLORS.red).lerp(COLORS.lava, c - 2);
}

export const VAR_COLORS: Record<string, THREE.Color> = {
  P: COLORS.blue,
  T: COLORS.red,
  SM: COLORS.olive,
  ET: new THREE.Color("#c75a3a"),
};
