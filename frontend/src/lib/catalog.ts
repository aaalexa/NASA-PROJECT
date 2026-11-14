import type { TopicId, VariableId } from "@/types/geo";

type L10n = { es: string; en: string };

export interface VariableInfo {
  id: VariableId;
  name: L10n;
  question: L10n;
  desc: L10n;
  product: string;
  unit: string;
}

/** Variable catalog (see "Guía práctica": 3 NASA collections -> 4 core variables, + NDVI). */
export const VARIABLES: Record<VariableId, VariableInfo> = {
  precipitation: {
    id: "precipitation",
    name: { es: "Precipitación", en: "Precipitation" },
    question: { es: "¿Está llegando más o menos agua?", en: "Is more or less water arriving?" },
    desc: {
      es: "Lluvia acumulada por mes. Es el fenómeno principal del análisis.",
      en: "Monthly accumulated rainfall. The main phenomenon of the analysis.",
    },
    product: "GPCP v3.2",
    unit: "mm/mes",
  },
  temperature: {
    id: "temperature",
    name: { es: "Temperatura del aire", en: "Air temperature" },
    question: { es: "¿La región se está calentando?", en: "Is the region warming?" },
    desc: {
      es: "Temperatura a 2 m del suelo. Permite ver si los cambios de lluvia coinciden con más calor.",
      en: "Temperature 2 m above ground. Shows whether rainfall changes coincide with more heat.",
    },
    product: "MERRA-2 T2M",
    unit: "°C",
  },
  moisture: {
    id: "moisture",
    name: { es: "Humedad del suelo", en: "Soil moisture" },
    question: { es: "¿El suelo conserva más o menos agua?", en: "Does the soil hold more or less water?" },
    desc: {
      es: "Agua en los primeros 10 cm de suelo. Muestra cómo responde la tierra.",
      en: "Water in the top 10 cm of soil. Shows how the land responds.",
    },
    product: "GLDAS Noah",
    unit: "m³/m³",
  },
  evapotranspiration: {
    id: "evapotranspiration",
    name: { es: "Evapotranspiración", en: "Evapotranspiration" },
    question: { es: "¿Cuánta agua pasa del suelo y las plantas al aire?", en: "How much water moves from soil and plants to the air?" },
    desc: {
      es: "Agua que sube a la atmósfera. Si falta agua en el suelo, puede bajar aunque haga calor.",
      en: "Water returned to the atmosphere. If soil is dry it can drop even when it is hot.",
    },
    product: "GLDAS Noah",
    unit: "mm/mes",
  },
  vegetation: {
    id: "vegetation",
    name: { es: "Vegetación (NDVI)", en: "Vegetation (NDVI)" },
    question: { es: "¿Las plantas están más o menos verdes?", en: "Are plants greener or less green?" },
    desc: {
      es: "Vigor de la vegetación visto desde satélite. Útil para cultivos y bosques.",
      en: "Plant vigor seen from space. Useful for crops and forests.",
    },
    product: "MODIS MOD13C2",
    unit: "NDVI",
  },
};

export const ALL_VARIABLES: VariableId[] = [
  "precipitation",
  "temperature",
  "moisture",
  "evapotranspiration",
  "vegetation",
];

export interface TopicInfo {
  id: TopicId;
  name: L10n;
  desc: L10n;
  variables: VariableId[];
}

/** Topics the guided flow offers; each maps to related data variables, most relevant first. */
export const TOPICS: TopicInfo[] = [
  {
    id: "rain",
    name: { es: "Lluvia y sequía", en: "Rain and drought" },
    desc: { es: "¿Llueve más o menos que antes?", en: "Is it raining more or less than before?" },
    variables: ["precipitation", "moisture", "evapotranspiration", "temperature"],
  },
  {
    id: "heat",
    name: { es: "Calor", en: "Heat" },
    desc: { es: "¿Se está calentando este lugar?", en: "Is this place getting warmer?" },
    variables: ["temperature", "evapotranspiration", "moisture", "precipitation"],
  },
  {
    id: "vegetation",
    name: { es: "Plantas y cultivos", en: "Plants and crops" },
    desc: { es: "¿Hay más o menos vegetación?", en: "Is there more or less vegetation?" },
    variables: ["vegetation", "precipitation", "moisture", "temperature"],
  },
  {
    id: "soil",
    name: { es: "Agua en el suelo", en: "Soil water" },
    desc: { es: "¿El suelo está más seco o más húmedo?", en: "Is the soil getting drier or wetter?" },
    variables: ["moisture", "precipitation", "evapotranspiration", "temperature"],
  },
];

export const PERIODS = [
  {
    id: "5y",
    start: "2019-01-01",
    end: "2024-12-31",
    label: { es: "Últimos 5 años", en: "Last 5 years" },
    desc: { es: "Rápido, pero la lluvia varía mucho de un año a otro.", en: "Quick, but rainfall varies a lot year to year." },
  },
  {
    id: "10y",
    start: "2014-01-01",
    end: "2024-12-31",
    label: { es: "Últimos 10 años", en: "Last 10 years" },
    desc: { es: "Un punto medio entre rapidez y evidencia.", en: "A middle ground between speed and evidence." },
  },
  {
    id: "archive",
    start: "2001-01-01",
    end: "2024-12-31",
    label: { es: "2001 – 2024", en: "2001 – 2024" },
    desc: { es: "24 años completos. Recomendado para detectar tendencias.", en: "24 full years. Recommended for detecting trends." },
  },
] as const;
