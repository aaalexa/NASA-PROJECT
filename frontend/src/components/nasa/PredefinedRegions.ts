import { PredefinedRegion } from "@/types/geo";

export const PREDEFINED_REGIONS: PredefinedRegion[] = [
  {
    id: "nicaragua",
    name: {
      es: "Lago Cocibolca y Corredor Seco, Nicaragua",
      en: "Lake Cocibolca & Dry Corridor, Nicaragua",
    },
    area: { es: "Centroamerica", en: "Central America" },
    center: { lat: 11.6, lng: -85.4 },
    triangle: [
      { lat: 12.13, lng: -86.25 },
      { lat: 11.1, lng: -85.6 },
      { lat: 11.9, lng: -84.8 },
    ],
    aliases: ["nicaragua", "cocibolca", "lago nicaragua", "corredor seco", "managua"],
  },
  {
    id: "mediterranean",
    name: { es: "Mediterráneo, Europa", en: "Mediterranean, Europe" },
    area: { es: "Sur de Europa", en: "Southern Europe" },
    center: { lat: 39.0, lng: 10.0 },
    triangle: [
      { lat: 37.5, lng: -4.0 },
      { lat: 35.5, lng: 24.0 },
      { lat: 44.0, lng: 10.0 },
    ],
    aliases: ["mediterraneo", "mediterranean", "espana", "italia", "grecia", "spain", "italy", "greece"],
  },
  {
    id: "northeurope",
    name: { es: "Norte de Europa", en: "Northern Europe" },
    area: { es: "Escandinavia y Báltico", en: "Scandinavia and Baltic" },
    center: { lat: 59.0, lng: 15.0 },
    triangle: [
      { lat: 59.0, lng: 5.0 },
      { lat: 61.0, lng: 26.0 },
      { lat: 55.5, lng: 14.0 },
    ],
    aliases: ["norte de europa", "northern europe", "escandinavia", "scandinavia", "suecia", "sweden", "noruega", "norway", "finlandia", "finland"],
  },
  {
    id: "amazon",
    name: {
      es: "Cuenca del Amazonas, Sudamerica",
      en: "Amazon River Basin, South America",
    },
    area: { es: "Sudamerica", en: "South America" },
    center: { lat: -3.4, lng: -62.2 },
    triangle: [
      { lat: 3.5, lng: -67.0 },
      { lat: -14.5, lng: -73.0 },
      { lat: -8.0, lng: -51.0 },
    ],
    aliases: ["amazonas", "amazon", "cuenca amazonica", "brasil", "selva amazonica"],
  },
  {
    id: "sahara",
    name: {
      es: "Desierto del Sahara, Norte de Africa",
      en: "Sahara Desert, North Africa",
    },
    area: { es: "Norte de Africa", en: "North Africa" },
    center: { lat: 23.8, lng: 10.1 },
    triangle: [
      { lat: 23.41, lng: 25.66 },
      { lat: 28.03, lng: 1.65 },
      { lat: 18.07, lng: 15.97 },
    ],
    aliases: ["sahara", "desierto del sahara", "africa", "sahel"],
  },
  {
    id: "california",
    name: {
      es: "Valle Central de California, EE.UU.",
      en: "California Central Valley, USA",
    },
    area: { es: "Norteamerica", en: "North America" },
    center: { lat: 37.2, lng: -120.2 },
    triangle: [
      { lat: 40.2, lng: -122.4 },
      { lat: 35.0, lng: -118.7 },
      { lat: 36.4, lng: -122.2 },
    ],
    aliases: ["california", "valle central", "san joaquin", "sierra nevada"],
  },
  {
    id: "arctic",
    name: {
      es: "Oceano Artico y Groenlandia",
      en: "Arctic Ocean & Greenland",
    },
    area: { es: "Zona Polar Norte", en: "North Polar Zone" },
    center: { lat: 78.0, lng: -40.0 },
    triangle: [
      { lat: 78.0, lng: -40.0 },
      { lat: 72.0, lng: 15.0 },
      { lat: 82.0, lng: -10.0 },
    ],
    aliases: ["artico", "arctic", "groenlandia", "polo norte", "hielo marino"],
  },
  {
    id: "coral",
    name: {
      es: "Gran Barrera de Coral, Australia",
      en: "Great Barrier Reef, Australia",
    },
    area: { es: "Oceania", en: "Oceania" },
    center: { lat: -18.1, lng: 147.7 },
    triangle: [
      { lat: -10.5, lng: 142.5 },
      { lat: -24.5, lng: 153.3 },
      { lat: -20.5, lng: 145.5 },
    ],
    aliases: ["gran barrera", "coral", "barrera de coral", "australia", "queensland"],
  },
];

export function findMatchingPredefinedRegion(query: string): PredefinedRegion | undefined {
  const clean = query
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();

  return PREDEFINED_REGIONS.find((reg) =>
    reg.aliases.some((alias) => {
      const a = alias.toLowerCase();
      return clean.includes(a) || (clean.length >= 3 && a.startsWith(clean));
    })
  );
}
