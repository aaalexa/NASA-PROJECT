import { NextResponse } from "next/server";
import { GoogleGenAI, Type } from "@google/genai";

const apiKey = process.env.GEMINI_API_KEY || "";
const ai = apiKey ? new GoogleGenAI({ apiKey }) : null;

// Base de conocimiento geográfico de contingencia para el Hackathon
const FALLBACK_REGIONS: Record<
  string,
  {
    regionName: { es: string; en: string };
    description: { es: string; en: string };
    vertices: [ { lat: number; lng: number }, { lat: number; lng: number }, { lat: number; lng: number } ];
    variables: {
      es: Array<{ id: string; name: string; simpleExplanation: string }>;
      en: Array<{ id: string; name: string; simpleExplanation: string }>;
    };
  }
> = {
  nicaragua: {
    regionName: {
      es: "Lago Cocibolca y Corredor Seco, Nicaragua",
      en: "Lake Cocibolca & Dry Corridor, Nicaragua",
    },
    description: {
      es: "Monitoreo de balance hídrico, nivel de aguas y sequías en Centroamérica.",
      en: "Monitoring water balance, lake level, and drought patterns in Central America.",
    },
    vertices: [
      { lat: 12.13, lng: -86.25 },
      { lat: 11.10, lng: -85.60 },
      { lat: 11.90, lng: -84.80 },
    ],
    variables: {
      es: [
        {
          id: "GPM_PRECIP",
          name: "Precipitación (GPM)",
          simpleExplanation: "Mide la lluvia acumulada desde satélites para detectar sequías prolongadas.",
        },
        {
          id: "MODIS_LST",
          name: "Temperatura Superficial (MODIS)",
          simpleExplanation: "Mide qué tan caliente está la superficie terrestre para evaluar estrés térmico.",
        },
      ],
      en: [
        {
          id: "GPM_PRECIP",
          name: "Precipitation (GPM)",
          simpleExplanation: "Measures satellite-accumulated rainfall to detect prolonged drought periods.",
        },
        {
          id: "MODIS_LST",
          name: "Land Surface Temperature (MODIS)",
          simpleExplanation: "Measures how hot the ground surface is to evaluate thermal ecosystem stress.",
        },
      ],
    },
  },
  amazonas: {
    regionName: {
      es: "Cuenca del Amazonas, Sudamérica",
      en: "Amazon River Basin, South America",
    },
    description: {
      es: "Vigilancia de deforestación, evapotranspiración y estrés hídrico de la selva tropical.",
      en: "Surveillance of deforestation, evapotranspiration, and rainforest water stress.",
    },
    vertices: [
      { lat: -3.12, lng: -60.02 },
      { lat: -8.76, lng: -63.90 },
      { lat: -2.50, lng: -54.70 },
    ],
    variables: {
      es: [
        {
          id: "MODIS_NDVI",
          name: "Índice de Vegetación (MODIS NDVI)",
          simpleExplanation: "Refleja el verdor y la densidad de la biomasa vegetal amazónica.",
        },
        {
          id: "GLDAS_SOILM",
          name: "Humedad del Suelo (GLDAS)",
          simpleExplanation: "Calcula el agua retenida en el suelo para predecir vulnerabilidad a incendios.",
        },
      ],
      en: [
        {
          id: "MODIS_NDVI",
          name: "Vegetation Index (MODIS NDVI)",
          simpleExplanation: "Tracks the greenness and density of living canopy biomass in the Amazon.",
        },
        {
          id: "GLDAS_SOILM",
          name: "Soil Moisture (GLDAS)",
          simpleExplanation: "Estimates soil water content to gauge wildfire and drought vulnerability.",
        },
      ],
    },
  },
  sahara: {
    regionName: {
      es: "Desierto del Sahara, Norte de África",
      en: "Sahara Desert, North Africa",
    },
    description: {
      es: "Detección de tormentas de polvo atmosférico y temperaturas extremas.",
      en: "Detection of mineral dust transport and extreme surface temperature anomalies.",
    },
    vertices: [
      { lat: 23.41, lng: 25.66 },
      { lat: 28.03, lng: 1.65 },
      { lat: 18.07, lng: 15.97 },
    ],
    variables: {
      es: [
        {
          id: "AIRS_TEMP",
          name: "Temperatura Atmosférica (AIRS)",
          simpleExplanation: "Monitorea perfiles térmicos y aerosoles minerales en capas atmosféricas.",
        },
        {
          id: "MODIS_AOD",
          name: "Profundidad Óptica de Aerosoles (MODIS AOD)",
          simpleExplanation: "Mide partículas de polvo suspendidas en la atmósfera.",
        },
      ],
      en: [
        {
          id: "AIRS_TEMP",
          name: "Atmospheric Temperature (AIRS)",
          simpleExplanation: "Monitors thermal sounding profiles and airborne aerosols across air layers.",
        },
        {
          id: "MODIS_AOD",
          name: "Aerosol Optical Depth (MODIS AOD)",
          simpleExplanation: "Quantifies dust and particle concentrations suspended in the atmosphere.",
        },
      ],
    },
  },
  artico: {
    regionName: {
      es: "Océano Ártico y Groenlandia",
      en: "Arctic Ocean & Greenland",
    },
    description: {
      es: "Seguimiento del retroceso del hielo marino y albedo polar.",
      en: "Tracking sea ice extent retreat and polar albedo feedback dynamics.",
    },
    vertices: [
      { lat: 78.0, lng: -40.0 },
      { lat: 72.0, lng: 15.0 },
      { lat: 82.0, lng: -10.0 },
    ],
    variables: {
      es: [
        {
          id: "MODIS_ALBEDO",
          name: "Albedo Superficial (MODIS)",
          simpleExplanation: "Mide cuánta radiación solar refleja la capa de nieve y hielo.",
        },
        {
          id: "MERRA2_T2M",
          name: "Anomalía Térmica 2m (MERRA-2)",
          simpleExplanation: "Modela la temperatura a 2 metros del suelo para estudiar el calentamiento ártico.",
        },
      ],
      en: [
        {
          id: "MODIS_ALBEDO",
          name: "Surface Albedo (MODIS)",
          simpleExplanation: "Measures solar radiation reflection from ice and snowpack surfaces.",
        },
        {
          id: "MERRA2_T2M",
          name: "2m Air Temperature (MERRA-2)",
          simpleExplanation: "Models 2-meter air temperature to track polar amplification rates.",
        },
      ],
    },
  },
};

export async function POST(req: Request) {
  try {
    const { prompt, locale = "es" } = await req.json();

    if (!prompt || typeof prompt !== "string") {
      return NextResponse.json({ error: "No prompt provided" }, { status: 400 });
    }

    const lang = locale === "en" ? "en" : "es";

    // Intentar resolución con Gemini si la API key y cliente están disponibles
    if (ai) {
      try {
        const systemInstruction =
          lang === "en"
            ? `You are an expert NASA Earth Science AI Assistant for the 2026 NASA Space Apps Challenge.
The user wants to investigate environmental changes in an area on the Earth.
User input: "${prompt}".
Your task:
1. Identify the geographical region mentioned.
2. Generate exactly 3 geographic coordinates [lat, lng] that form a balanced, realistic triangle covering that region. Lat: [-90 to 90], Lng: [-180 to 180].
3. Suggest 2 real NASA satellite or model data variables (e.g. MODIS LST, GPM Precipitation, MODIS NDVI, AIRS Atmospheric Temp, MERRA-2 Soil Moisture, Landsat Albedo) with clear, simple explanations in English suitable for students and detectives.
Provide your response strictly in the requested JSON schema.`
            : `Eres un asistente científico de la NASA para el reto NASA Space Apps Challenge 2026.
El usuario quiere investigar cambios ambientales en una región de la Tierra.
Petición del usuario: "${prompt}".
Tu tarea:
1. Identifica la región geográfica mencionada.
2. Genera exactamente 3 coordenadas geográficas [lat, lng] que formen un triángulo equilibrado y realista que cubra esa región. Lat: [-90 a 90], Lng: [-180 a 180].
3. Sugiere 2 variables reales de satélites o modelos de la NASA (ej. GPM Precipitación, MODIS Temperatura Superficial LST, MODIS NDVI Vegetación, AIRS Temperatura Atmosférica, MERRA-2 Humedad, Landsat Albedo) con explicaciones simples y claras en español para estudiantes.
Responde estrictamente con el esquema JSON solicitado.`;

        const response = await ai.models.generateContent({
          model: "gemini-2.5-flash",
          contents: systemInstruction,
          config: {
            responseMimeType: "application/json",
            responseSchema: {
              type: Type.OBJECT,
              properties: {
                regionName: { type: Type.STRING },
                description: { type: Type.STRING },
                triangleVertices: {
                  type: Type.ARRAY,
                  items: {
                    type: Type.OBJECT,
                    properties: {
                      lat: { type: Type.NUMBER },
                      lng: { type: Type.NUMBER },
                    },
                    required: ["lat", "lng"],
                  },
                },
                suggestedVariables: {
                  type: Type.ARRAY,
                  items: {
                    type: Type.OBJECT,
                    properties: {
                      id: { type: Type.STRING },
                      name: { type: Type.STRING },
                      simpleExplanation: { type: Type.STRING },
                    },
                    required: ["id", "name", "simpleExplanation"],
                  },
                },
              },
              required: ["regionName", "description", "triangleVertices", "suggestedVariables"],
            },
          },
        });

        const parsed = JSON.parse(response.text || "{}");
        const v = parsed.triangleVertices ? parsed.triangleVertices.slice(0, 3) : [];

        if (v.length === 3) {
          // Formato GeoJSON cerrado [lng, lat] para enviar al backend Python
          const geoJsonPolygon = {
            type: "Polygon",
            coordinates: [
              [
                [v[0].lng, v[0].lat],
                [v[1].lng, v[1].lat],
                [v[2].lng, v[2].lat],
                [v[0].lng, v[0].lat],
              ],
            ],
          };

          return NextResponse.json({
            regionName: parsed.regionName,
            description: parsed.description,
            triangleVertices: v,
            geoJsonPolygon,
            suggestedVariables: parsed.suggestedVariables || [],
          });
        }
      } catch (geminiError) {
        console.warn("[NASA Earth Detective] Gemini API fallback triggered:", geminiError);
      }
    }

    // Estrategia de Fallback inteligente ante contingencia de red / cuota
    const lower = prompt.toLowerCase();
    let matchedKey = "nicaragua";
    if (lower.includes("amazon") || lower.includes("brasil") || lower.includes("selva")) {
      matchedKey = "amazonas";
    } else if (lower.includes("sahara") || lower.includes("africa") || lower.includes("desierto")) {
      matchedKey = "sahara";
    } else if (lower.includes("artico") || lower.includes("polar") || lower.includes("arctic") || lower.includes("ice") || lower.includes("groenlandia")) {
      matchedKey = "artico";
    }

    const preset = FALLBACK_REGIONS[matchedKey];
    const v = preset.vertices;
    const geoJsonPolygon = {
      type: "Polygon",
      coordinates: [
        [
          [v[0].lng, v[0].lat],
          [v[1].lng, v[1].lat],
          [v[2].lng, v[2].lat],
          [v[0].lng, v[0].lat],
        ],
      ],
    };

    return NextResponse.json({
      regionName: preset.regionName[lang],
      description: preset.description[lang],
      triangleVertices: v,
      geoJsonPolygon,
      suggestedVariables: preset.variables[lang],
    });
  } catch (error) {
    console.error("Error crítico en /api/parse-voice:", error);
    return NextResponse.json(
      { error: "No se pudo interpretar la región solicitada" },
      { status: 500 }
    );
  }
}
