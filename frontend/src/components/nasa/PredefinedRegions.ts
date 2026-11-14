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
    id: "amazon",
    name: {
      es: "Cuenca del Amazonas, Sudamerica",
      en: "Amazon River Basin, South America",
    },
    area: { es: "Sudamerica", en: "South America" },
    center: { lat: -3.4, lng: -62.2 },
    triangle: [
      { lat: -3.12, lng: -60.02 },
      { lat: -8.76, lng: -63.9 },
      { lat: -2.5, lng: -54.7 },
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
      { lat: 38.5, lng: -121.5 },
      { lat: 35.3, lng: -119.0 },
      { lat: 37.0, lng: -122.0 },
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
      { lat: -16.5, lng: 145.8 },
      { lat: -21.0, lng: 149.5 },
      { lat: -14.0, lng: 144.2 },
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
    reg.aliases.some((alias) => clean.includes(alias.toLowerCase()))
  );
}
