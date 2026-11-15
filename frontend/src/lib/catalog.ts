import type { DateRange, TopicId } from "@/types/geo";

type L10n = { es: string; en: string };

/**
 * Everything about data (variables, units, datasets, regions, valid periods) comes from the
 * backend (`GET /api/v1/catalogo`, see context/BackendContext). This file only holds UI concepts
 * the backend does not model: the guided-flow topics and how a period preset is labelled.
 */

export interface TopicInfo {
  id: TopicId;
  name: L10n;
  desc: L10n;
  /** Backend variable ids, most relevant first. Ids missing from the backend catalog are skipped. */
  variables: string[];
}

export const TOPICS: TopicInfo[] = [
  {
    id: "rain",
    name: { es: "Lluvia y sequía", en: "Rain and drought" },
    desc: { es: "¿Llueve más o menos que antes?", en: "Is it raining more or less than before?" },
    variables: ["lluvia_gpcp", "humedad_suelo", "evapotranspiracion", "temp_aire"],
  },
  {
    id: "heat",
    name: { es: "Calor", en: "Heat" },
    desc: { es: "¿Se está calentando este lugar?", en: "Is this place getting warmer?" },
    variables: ["temp_aire", "evapotranspiracion", "humedad_suelo", "lluvia_gpcp"],
  },
  {
    id: "soil",
    name: { es: "Agua en el suelo", en: "Soil water" },
    desc: { es: "¿El suelo está más seco o más húmedo?", en: "Is the soil getting drier or wetter?" },
    variables: ["humedad_suelo", "lluvia_gpcp", "evapotranspiracion", "temp_aire"],
  },
  {
    id: "extremes",
    name: { es: "Sequías y aguaceros", en: "Droughts and downpours" },
    desc: { es: "¿Más días secos seguidos o lluvias más fuertes?", en: "More dry spells or heavier rain?" },
    variables: ["cdd_imerg", "r20mm_imerg", "sdii_imerg", "lluvia_gpcp"],
  },
];

/** Labels for the backend variable groups (`grupo`). */
export const GROUP_LABELS: Record<string, L10n> = {
  lluvia: { es: "Lluvia", en: "Rainfall" },
  causa: { es: "Causas", en: "Drivers" },
  agua: { es: "Agua en la tierra", en: "Water on land" },
  calculada: { es: "Extremos de lluvia", en: "Rainfall extremes" },
};

export const ZONE_LABELS: Record<string, L10n> = {
  mexico: { es: "México", en: "Mexico" },
  centroamerica: { es: "Centroamérica", en: "Central America" },
  caribe: { es: "Caribe", en: "Caribbean" },
  sudamerica: { es: "Sudamérica", en: "South America" },
  referencia_global: { es: "Referencia global", en: "Global reference" },
};

export interface PeriodPreset {
  id: string;
  start: string;
  end: string;
  label: L10n;
  desc: L10n;
}

/** Period presets derived from the backend's common period (`periodos.comun`). */
export function periodPresets(comun: [string, string]): PeriodPreset[] {
  const [from, to] = comun;
  const endYear = Number(to.slice(0, 4));
  const startYear = Number(from.slice(0, 4));
  const mk = (years: number) => {
    const y = Math.max(startYear, endYear - years + 1);
    return { start: `${y}-01-01`, end: `${endYear}-12-31` };
  };
  return [
    {
      id: "5y",
      ...mk(5),
      label: { es: "Últimos 5 años", en: "Last 5 years" },
      desc: { es: "Rápido, pero la lluvia varía mucho de un año a otro.", en: "Quick, but rainfall varies a lot year to year." },
    },
    {
      id: "10y",
      ...mk(10),
      label: { es: "Últimos 10 años", en: "Last 10 years" },
      desc: { es: "Un punto medio entre rapidez y evidencia.", en: "A middle ground between speed and evidence." },
    },
    {
      id: "archive",
      start: `${from}-01`,
      end: `${to}-31`,
      label: { es: `${startYear} – ${endYear}`, en: `${startYear} – ${endYear}` },
      desc: {
        es: `${endYear - startYear + 1} años completos. Recomendado para detectar tendencias.`,
        en: `${endYear - startYear + 1} full years. Recommended for detecting trends.`,
      },
    },
  ];
}

export const rangeFromPreset = (p: PeriodPreset): DateRange => ({ start: p.start, end: p.end, preset: p.id });
