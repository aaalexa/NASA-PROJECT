Markdown
# Prompt Maestro Definitivo: NASA Earth Trend Detective — Space Apps 2026

Actúa como un Senior Full-Stack, Geospatial & AI Systems Engineer experto en Next.js (App Router), TypeScript, Tailwind CSS, `shadcn/ui` y pnpm. Vamos a construir, configurar, validar y estilizar por completo la aplicación **NASA Earth Trend Detective** para el hackathon **NASA Space Apps Challenge 2026**.

---

## 1. Validación Estricta del Setup Inicial y Dependencias

Antes de escribir código o iniciar el servidor, el agente en Cursor debe validar y asegurar que el entorno local esté configurado correctamente:
- **Gestor de paquetes:** Usar exclusivamente **`pnpm`**.
- **Dependencias esenciales obligatorias en `package.json`:**
  - `cobe` (Globo 3D WebGL ultraligero).
  - `lucide-react` (Iconografía de alta gama).
  - `@google/genai` (SDK oficial de Gemini para procesamiento de lenguaje e interpretación de voz).
- **Configuración de compilación (`package.json` / `pnpm`):** Asegurar que las políticas de dependencias como `protobufjs` estén aprobadas para evitar bloqueos por `[ERR_PNPM_IGNORED_BUILDS]` durante `pnpm dev`.

---

## 2. Contexto Completo: Reto NASA Space Apps 2026 y Recursos Globales

El desarrollo debe alinearse estrictamente con los objetivos del reto y aprovechar los recursos del hackathon:
- **Reto Oficial:** *Event 2026 NASA Space Apps Challenge (Advanced)*. Crear una herramienta para seleccionar variables de misiones o modelos de ciencias de la Tierra de la NASA (como MODIS, GPM, AIRS, MERRA-2), visualizar cambios temporales en regiones delimitadas, y realizar análisis estadísticos de tendencias (*Mann-Kendall / t-test*, tasa de cambio y significancia).
- **Rol del Usuario:** "Detective de datos" (público general y estudiantes), requiriendo definiciones simples de las variables científicas.
- **Global Collaborators (Disponibles para integrar):**
  - **Microsoft Azure / Planetary Computer:** STAC API pública para catálogos satelitales (Landsat, MODIS, GPM) y hosting del backend en Python (FastAPI).
  - **Meteomatics Weather API:** Consultas meteorológicas e históricas de alta resolución.
  - **Google Cloud Platform (GCP) & Gemini API:** Infraestructura y modelos de super inteligencia (`gemini-2.5-flash`) para traducir comandos de voz y texto en estructuras geográficas precisas.

---

## 3. Identidad Visual y Paleta de Colores Estricta

Aplica rigurosamente esta paleta inspirada en interfaces espaciales y diseño orgánico-tecnológico de alta gama:
- **Negro Puro (`#000000` / `bg-black`):** Fondo absoluto del espacio y de toda la aplicación.
- **Blanco (`#FFFFFF` / `text-white` / bordes translúcidos `border-white/15`):** Textos principales, títulos y contenedores de alta legibilidad.
- **Azul NASA / Interactivo (`#2563EB` / `bg-blue-600`):** Color primario para botones de acción, insignias de estado activo (`Badge`), resplandor atmosférico y aristas geodésicas del triángulo.
- **Rojo Alerta / Vértices (`#EF4444` / `bg-red-600`):** Color destructivo, indicador de grabación de voz con animación *pulse*, y los 3 vértices del triángulo sobre el globo.
- **Tipografía:** `Inter` (`--font-inter`) para toda la aplicación.

---

## 4. Directrices de UI/UX (Glassmorphism & Componentes Flotantes)

1. **Efecto Glassmorphism Espacial:** Tarjetas flotantes (`Card`), barras de navegación (`Header`) y píldoras con fondos semitransparentes (`bg-black/80` o `bg-black/90`), desenfoque (`backdrop-blur-md`), bordes finos de alta definición (`border border-white/15`) y esquinas muy redondeadas (`rounded-2xl` o `rounded-3xl`).
2. **Control de Voz Bilingüe y Animado:** Botón de micrófono flotante en la parte inferior central. En reposo usa Azul NASA (`bg-blue-600`), y al escuchar o procesar cambia a Rojo (`bg-red-600`) con un anillo de expansión animado (`animate-pulse`). Sincroniza el idioma del navegador (`recognition.lang`) con el idioma activo (`es-ES` o `en-US`).
3. **Tarjetas de Variables NASA:** Contenedores internos oscuros con bordes sutiles (`bg-zinc-950 border border-white/10 p-3 rounded-xl`), resaltando el nombre de la variable en azul claro y la explicación simple para estudiantes en gris neutro (`text-zinc-400`).

---

## 5. Requisitos de Internacionalización (i18n: `es` y `en`)

- Selector de Idioma intercativo (`ES | EN`) en el Header HUD.
- Proveedor y hook global (`LanguageContext` / `useTranslation()`) para actualizar textos de forma instantánea.
- Envío del parámetro `locale` al endpoint `/api/parse-voice` para que Gemini responda en el idioma seleccionado.

---

## 6. Estructura de Archivos Requerida en Cursor

```text
src/
├── app/
│   ├── api/
│   │   └── parse-voice/
│   │       └── route.ts             # Endpoint Gemini SDK (soporta locale: 'es' | 'en')
│   ├── globals.css                  # Variables CSS con Negro, Blanco, Azul (#2563eb) y Rojo (#ef4444)
│   ├── layout.tsx                   # Fuente Inter + LanguageProvider
│   └── page.tsx                     # Pantalla principal (Globo + HUD + Demos + Voz)
├── components/
│   ├── globe/
│   │   └── CobeGlobePulse.tsx       # Globo WebGL (cobe), vértices rojos pulsantes y aristas azules
│   ├── hud/
│   │   └── VoiceController.tsx      # Botón de micrófono bilingüe
│   └── ui/                          # Componentes shadcn/ui (button, card, badge, input)
├── context/
│   └── LanguageContext.tsx          # Proveedor i18n con hook useTranslation()
├── messages/
│   ├── es.json                      # Textos en Español
│   └── en.json                      # Textos en Inglés
└── types/
    └── geo.ts                       # Interfaces TypeScript (GeoPoint, RegionAnalysisPayload)
7. Archivos de Traducción (es.json y en.json)
src/messages/es.json
JSON
{
  "header": {
    "title": "NASA Earth Trend Detective",
    "subtitle": "Usa tu voz o el buscador para delimitar una región en el globo",
    "searchPlaceholder": "Ej. Cuenca del Amazonas...",
    "demoButton": "Demo: Nicaragua",
    "clearButton": "Limpiar",
    "langToggle": "EN"
  },
  "voice": {
    "speak": "Hablar",
    "listening": "Escuchando región...",
    "processing": "Calculando coordenadas...",
    "unsupported": "Tu navegador no soporta reconocimiento de voz. Usa Google Chrome o Microsoft Edge."
  },
  "panel": {
    "activeTriangle": "TRIÁNGULO ACTIVO",
    "geojsonReady": "GEOJSON LISTO",
    "variablesTitle": "Variables NASA Sugeridas",
    "sendButton": "Enviar Triángulo al Backend",
    "sending": "Enviando telemetría...",
    "backendSuccess": "Triángulo GeoJSON listo para análisis estadístico (revisa la consola F12)."
  },
  "demo": {
    "regionName": "Lago Cocibolca y Corredor Seco, Nicaragua",
    "description": "Monitoreo de balance hídrico y temperatura superficial terrestre.",
    "var1Name": "Precipitación (GPM)",
    "var1Desc": "Mide la lluvia acumulada desde satélites para detectar sequías prolongadas.",
    "var2Name": "Temperatura Superficial (MODIS)",
    "var2Desc": "Mide qué tan caliente está el suelo para evaluar estrés térmico en ecosistemas."
  }
}
src/messages/en.json
JSON
{
  "header": {
    "title": "NASA Earth Trend Detective",
    "subtitle": "Speak or search to outline a region on the globe",
    "searchPlaceholder": "E.g. Amazon Basin...",
    "demoButton": "Demo: Nicaragua",
    "clearButton": "Clear",
    "langToggle": "ES"
  },
  "voice": {
    "speak": "Speak",
    "listening": "Listening for region...",
    "processing": "Computing coordinates...",
    "unsupported": "Your browser does not support speech recognition. Please use Google Chrome or Microsoft Edge."
  },
  "panel": {
    "activeTriangle": "ACTIVE TRIANGLE",
    "geojsonReady": "GEOJSON READY",
    "variablesTitle": "Suggested NASA Variables",
    "sendButton": "Send Triangle to Backend",
    "sending": "Sending telemetry...",
    "backendSuccess": "GeoJSON triangle ready for statistical analysis (check F12 console)."
  },
  "demo": {
    "regionName": "Lake Cocibolca & Dry Corridor, Nicaragua",
    "description": "Monitoring water balance and land surface temperature.",
    "var1Name": "Precipitation (GPM)",
    "var1Desc": "Measures accumulated rainfall from satellites to detect prolonged droughts.",
    "var2Name": "Land Surface Temperature (MODIS)",
    "var2Desc": "Measures how warm the ground is to evaluate thermal stress on ecosystems."
  }
}
8. Instrucciones Finales para el Agente en Cursor
Valida que pnpm install corra sin errores de dependencias.

Implementa todos los archivos respetando estrictamente los colores Negro, Blanco, Azul (#2563eb) y Rojo (#ef4444).

Conecta el SDK de Gemini en /api/parse-voice/route.ts para que interprete la voz del usuario y genere el polígono GeoJSON cerrado ([lng, lat]) junto con las variables científicas de la NASA.