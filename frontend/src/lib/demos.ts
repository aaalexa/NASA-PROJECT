import type { WorkflowStep } from "@/types/geo";

type L10n = { es: string; en: string };

export interface DemoStep {
  caption: L10n;
  /** Milliseconds this step stays on screen. */
  duration: number;
  region?: string;
  step?: WorkflowStep;
  preset?: string;
  /** Backend variable ids. */
  variables?: string[];
}

export interface DemoDef {
  id: string;
  title: L10n;
  blurb: L10n;
  steps: DemoStep[];
}

/** Watch-only walkthroughs. They drive the real UI so newcomers see how each step works. */
export const DEMOS: DemoDef[] = [
  {
    id: "two-faces",
    title: { es: "Las dos caras de la lluvia", en: "The two faces of rain" },
    blurb: {
      es: "El Sahel frente al sureste de México: ¿cambia igual la lluvia?",
      en: "The Sahel versus southeast Mexico: does rainfall change the same way?",
    },
    steps: [
      {
        caption: {
          es: "Todo empieza con una pregunta: ¿está cambiando la lluvia donde vivo? Primero elegimos una región: el Sahel, en África.",
          en: "It starts with a question: is rainfall changing where I live? First we pick a region: the Sahel, in Africa.",
        },
        duration: 5200,
        region: "sahel",
        step: "region",
      },
      {
        caption: {
          es: "Elegimos el periodo. Con 24 años completos hay evidencia suficiente para distinguir una tendencia del ruido de cada año.",
          en: "We choose the period. 24 full years give enough evidence to tell a trend from year-to-year noise.",
        },
        duration: 5000,
        step: "period",
        preset: "archive",
      },
      {
        caption: {
          es: "Variables relacionadas: lluvia, temperatura, humedad del suelo y evapotranspiración. Se analizan juntas para ver qué coincide.",
          en: "Related variables: rainfall, temperature, soil moisture and evapotranspiration. They are analysed together to see what coincides.",
        },
        duration: 5600,
        step: "variables",
        variables: ["lluvia_gpcp", "temp_aire", "humedad_suelo", "evapotranspiracion"],
      },
      {
        caption: {
          es: "Resultado: cada variable muestra su cambio por década, un intervalo de confianza y si la evidencia alcanza el criterio estadístico.",
          en: "Result: each variable shows its change per decade, a confidence interval, and whether the evidence meets the statistical criterion.",
        },
        duration: 6400,
        step: "results",
      },
      {
        caption: {
          es: "Ahora el contraste: el sureste de México, otra región con otro clima. Cada lugar cambia a su manera y hay que medirlo.",
          en: "Now the contrast: southeast Mexico, another region with another climate. Each place changes in its own way and must be measured.",
        },
        duration: 6000,
        region: "sureste_mexico",
        step: "results",
      },
    ],
  },
  {
    id: "dry-corridor",
    title: { es: "Corredor Seco Centroamericano", en: "Central American Dry Corridor" },
    blurb: {
      es: "Cuando la lluvia cambia, cambian las cosechas.",
      en: "When rainfall changes, harvests change.",
    },
    steps: [
      {
        caption: {
          es: "El Corredor Seco abarca zonas de agricultura de subsistencia. Una caída de lluvia aquí afecta directamente a las familias.",
          en: "The Dry Corridor holds subsistence farming areas. Less rain here directly affects families.",
        },
        duration: 5600,
        region: "corredor_seco_centroamericano",
        step: "region",
      },
      {
        caption: {
          es: "Usamos la serie larga 2001–2024 para tener suficientes años.",
          en: "We use the long 2001–2024 record to have enough years.",
        },
        duration: 4200,
        step: "period",
        preset: "archive",
      },
      {
        caption: {
          es: "Lluvia, humedad del suelo y evapotranspiración cuentan la historia del agua desde ángulos distintos.",
          en: "Rain, soil moisture and evapotranspiration tell the water story from different angles.",
        },
        duration: 5000,
        step: "variables",
        variables: ["lluvia_gpcp", "humedad_suelo", "evapotranspiracion"],
      },
      {
        caption: {
          es: "Una coincidencia entre variables describe una relación, pero no demuestra una causa.",
          en: "A match between variables describes a relationship but does not prove a cause.",
        },
        duration: 6000,
        step: "results",
      },
    ],
  },
  {
    id: "amazon",
    title: { es: "Selva y lluvia: Amazonia", en: "Forest and rain: Amazonia" },
    blurb: {
      es: "¿Se parece la selva de hoy a la de hace 20 años?",
      en: "Does today's forest look like it did 20 years ago?",
    },
    steps: [
      {
        caption: {
          es: "La Amazonia regula la humedad de medio continente. Empecemos delimitando su cuenca.",
          en: "The Amazon regulates humidity for half a continent. Let's outline its basin.",
        },
        duration: 5000,
        region: "amazonia",
        step: "region",
      },
      {
        caption: {
          es: "Periodo largo para separar el ciclo de las estaciones del cambio real.",
          en: "A long period separates the seasonal cycle from real change.",
        },
        duration: 4200,
        step: "period",
        preset: "archive",
      },
      {
        caption: {
          es: "Lluvia, humedad del suelo y temperatura, para ver cómo responde la selva.",
          en: "Rain, soil moisture and temperature, to see how the forest responds.",
        },
        duration: 5000,
        step: "variables",
        variables: ["lluvia_gpcp", "humedad_suelo", "temp_aire"],
      },
      {
        caption: {
          es: "Los resultados se leen con sus límites: significancia estadística no es lo mismo que importancia.",
          en: "Results are read with their limits: statistical significance is not the same as importance.",
        },
        duration: 6000,
        step: "results",
      },
    ],
  },
];
