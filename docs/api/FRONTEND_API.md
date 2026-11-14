# Guía de integración Frontend ↔ API Backend

> API: **FastAPI v0.2.0** — "Las Dos Caras de la Lluvia / Down to Earth"
> Todos los ejemplos de esta carpeta son **respuestas reales** generadas con `TestClient` contra `backend/src/core/api/app.py` en modo `sintetico=true` (sin red).
> Regenerar: `cd backend && .venv/bin/python ../docs/api/generar_ejemplos.py`

| Recurso | Ruta |
|---|---|
| Especificación OpenAPI 3 (para generar tipos/cliente) | [`openapi.json`](./openapi.json) |
| Respuestas reales por endpoint | [`ejemplos/`](./ejemplos) (cada archivo = `{request, status, response}`) |
| Swagger UI / ReDoc en vivo | `{BASE_URL}/docs` · `{BASE_URL}/redoc` |

---

## 1. Conexión

| Entorno | `NEXT_PUBLIC_BACKEND_URL` |
|---|---|
| Local (uvicorn / docker compose) | `http://localhost:8000` |
| Producción (Caddy + TLS) | `https://api.moody-trends.earth` |

```bash
# frontend/.env.local
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

Levantar el backend en local:

```bash
cd backend && .venv/bin/python -m core.main servir --host 127.0.0.1 --port 8000 --reload
# o bien, desde la raíz:  cp .env.example .env && docker compose up -d api
```

**CORS**: ya permitidos `http://localhost:3000`, `http://localhost:5173`, `https://moody-trends.earth`, `https://www.moody-trends.earth` (variable `NASA_CORS_ORIGINS`). Si el front corre en otro puerto/dominio, añádelo ahí.

**Sin autenticación**: la API es pública. Las credenciales de NASA Earthdata viven sólo en el servidor.

**Timeouts**: una consulta en vivo (`descargar=true`) puede tardar decenas de segundos (Caddy corta a 180 s). Usa `AbortController` y estado de carga.

---

## 2. Conceptos clave (léelos antes de integrar)

### 2.1 Fuente de datos: `sintetico` vs `opendap_memoria`
La API **no guarda archivos**; los datos de NASA se consultan por OPeNDAP y se cachean en RAM. Cada endpoint de análisis acepta:

| Query param | Efecto |
|---|---|
| `sintetico=true` | Datos sintéticos deterministas. **Úsalo para desarrollar el front.** |
| `descargar=true` | Si no está en RAM, consulta NASA en vivo (lento, requiere credenciales en el server). |
| *(ninguno)* | Sólo RAM. Si no hay datos → **404 `datos_no_disponibles_en_memoria`** (excepto `/demo/result`, ver abajo). |

Las respuestas indican el origen en `fuente_datos` (endpoints `/api/v1/*`) o en `metadata.source` (`/demo/result`). **Muestra un aviso "datos ilustrativos" cuando valga `"sintetico"`.**

> ⚠️ `/demo/result` sin `sintetico` ni `descargar` **cae silenciosamente a sintético** si no hay datos en RAM. Para forzar 404 en ese caso usa `estricto_memoria=true`.

### 2.2 Región: id predefinido **o** bbox
Todos los endpoints de análisis aceptan:
- `region=<id>` (ver `GET /api/v1/regiones`), **o**
- `region=<slug_libre>&oeste=..&sur=..&este=..&norte=..` (las **4** coordenadas son obligatorias juntas; si falta una → 400).

El frontend dibuja un triángulo/polígono → calcula su bbox (min/max de lon/lat) y envíalo así.

### 2.3 Fechas
Formato **`AAAA-MM`** (ej. `2001-01`). `2001-01-01` devuelve **400**. Periodo por defecto `2001-01 → 2024-12` (288 meses / 24 años).

```ts
const toYM = (iso: string) => iso.slice(0, 7); // "2015-03-21" -> "2015-03"
```

### 2.4 Mapeo de variables del frontend → backend

| Frontend `VariableId` | Clave en `/demo/result` (`variables.*`) | `variable_id` en `/api/v1/*` | Unidad mensual | Unidad pendiente |
|---|---|---|---|---|
| `precipitation` | `P` | `lluvia_gpcp` | mm/mes | mm por década |
| `temperature` | `T` | `temp_aire` | °C | °C por década |
| `moisture` | `SM` | `humedad_suelo` | m³/m³ | m³/m³ por década |
| `evapotranspiration` | `ET` | `evapotranspiracion` | mm/mes | mm por década |
| `vegetation` | — | — | — | **No soportada por el backend** (no hay NDVI) |

Variables extra disponibles: `lluvia_merra2`, `vapor_agua`, `lluvia_imerg_mes`, y los indicadores anuales IMERG `cdd_imerg`, `r20mm_imerg`, `dias_humedos_imerg`, `prcptot_imerg`, `sdii_imerg`.

---

## 3. Endpoint principal para la pantalla de resultados

### `GET /demo/result` (alias `GET /api/v1/demo/result`, `GET /api/v1/down-to-earth/analisis`)

Calcula las 4 tendencias (P, T, SM, ET) con OLS + HAC (Newey-West) + corrección de Holm, y la lectura conjunta. **Es lo que hoy está hardcodeado como `ILLUSTRATIVE` en [`ResultsStep.tsx`](../../frontend/src/components/nasa/ResultsStep.tsx).**

| Param | Tipo | Default | Notas |
|---|---|---|---|
| `region` | string | `sahel` | id o slug |
| `oeste,sur,este,norte` | number | — | bbox opcional (las 4) |
| `inicio`, `fin` | `AAAA-MM` | `2001-01`, `2024-12` | |
| `alfa` | number (0, 0.5) | `0.05` | umbral Holm |
| `mascara` | `"tierra"` | — | sólo tierra firme |
| `sintetico`, `descargar`, `estricto_memoria` | bool | `false` | ver §2.1 |

Ejemplo: [`ejemplos/demo_result.json`](./ejemplos/demo_result.json)

```jsonc
{
  "metadata": {
    "project": "Down to Earth — Cuatro variables, dos formas de analizarlas",
    "region": { /* RegionDTO, ver §5 */ },
    "period": ["2001-01", "2024-12"],
    "months_total": 288, "years_expected": 24, "years_complete_count": 24,
    "alpha": 0.05,
    "method": { "ols_formula": "y = a + b * t, ...", "cov_type": "HAC", "multiple_testing": "holm", "family": ["P","T","SM","ET"], "sensitivity_lags": [1,2,3], ... },
    "source": "sintetico",               // o "opendap_memoria"
    "almacenamiento_disco": false
  },
  "variables": {
    "P": {
      "id": "lluvia_gpcp", "code": "P", "name": "Precipitación (P)",
      "question": "¿Está llegando más o menos agua?",
      "units": { "monthly": "mm/mes", "annual": "mm", "slope_decade": "mm por década" },
      "monthly": [ { "date": "2001-01", "value": 59.27, "z": 0.08 }, /* …288 */ ],
      "annual":  [ { "year": 2001, "value": 1039.43, "fitted": 1036.41 }, /* …24 */ ],
      "intercept_a": 1036.41, "slope_annual": 8.19, "se_annual": 0.457, "z_stat": 17.9,
      "slope_decade": 81.93,             // ← valor principal de la tarjeta
      "ci95": [72.96, 90.90],            // ← IC 95 % por década
      "p_raw": 1.18e-71,
      "p_holm": 1.18e-71,                // ← p ajustado
      "significant": true,               // ← badge
      "direction": "aumento",            // "aumento" | "disminucion" | "estable"
      "label": "Aumento con evidencia estadística.",
      "summary_text": "Precipitación (P) cambió aproximadamente +81.9 mm por década; IC95 % […",
      "sensible_al_rezago": false,
      "sensitivity": { "lag_1": {…}, "lag_2": {…}, "lag_3": {…} },
      "quality": { "n_months_valid": 288, "n_years_complete": 24, "complete_period": true, "warnings": [], ... }
    },
    "T": { … }, "SM": { … }, "ET": { … }
  },
  "joint": {
    "preprocessing": { "seasonal_removal": "…", "standardization": "…", "note": "…" },
    "standardized_anomalies": [ { "date": "2001-01", "P": 0.08, "T": -1.71, "SM": -0.58, "ET": -0.59 }, /* …288 */ ],
    "pairs": { "P-SM": {…}, "T-SM": {…}, "P-ET": {…} },
    "pairs_list": [ { "pair": "P-SM", "var_x": "P", "var_y": "SM", "question": "…", "r": 0.856, "n": 288,
                      "direction_description": "variación conjunta en el mismo sentido", "summary_text": "…" } ]
  },
  "conclusion": {
    "joint_reading": "En el período analizado, …",
    "changes_with_statistical_evidence": ["…"],
    "inconclusive_or_insufficient_evidence": [],
    "exploratory_associations": ["…"],
    "methodological_limits": ["…"]
  }
}
```

### Exportar CSV — `GET /demo/csv/{mensual|anual}`
Mismos parámetros. Devuelve `text/csv` con `Content-Disposition: attachment`. Ejemplo: [`ejemplos/demo_csv_anual.csv`](./ejemplos/demo_csv_anual.csv)

```
anio,P_mm_anio,T_degC,SM_m3_m3,ET_mm_anio
2001,1039.43,24.0086,0.219401,549.653
```
Mensual: `fecha,P_mm_mes,T_degC,SM_m3_m3,ET_mm_mes` (288 filas). Basta con un `<a href={url} download>`.

---

## 4. Catálogo de endpoints

### Estado y catálogo (sin parámetros de datos, respuestas rápidas)

| Método | Ruta | Uso en el front | Ejemplo |
|---|---|---|---|
| GET | `/` | info general | [raiz.json](./ejemplos/raiz.json) |
| GET | `/api/v1/salud` | health check / "backend online" | [salud.json](./ejemplos/salud.json) |
| GET | `/api/v1/catalogo` | **inicialización en una sola llamada**: datasets, variables, regiones, periodos, bloque `down_to_earth` | [catalogo.json](./ejemplos/catalogo.json) |
| GET | `/catalog` (alias `/api/v1/catalog`, `/api/v1/down-to-earth/catalogo`) | catálogo Down to Earth (4 variables, colecciones, método, regiones) | [catalog_dte.json](./ejemplos/catalog_dte.json) |
| GET | `/api/v1/datasets` · `/api/v1/datasets/{id}` | `gpcp`, `merra2`, `gldas`, `imerg` | [datasets.json](./ejemplos/datasets.json) |
| GET | `/api/v1/variables?grupo=&fuente=&frecuencia=&solo_analizables=` | listar variables | [variables.json](./ejemplos/variables.json) |
| GET | `/api/v1/variables/{variable_id}` | ficha de una variable | [variable_detalle.json](./ejemplos/variable_detalle.json) |
| GET | `/api/v1/regiones?zona=&solo_latinoamerica=` | selector de regiones (`shortcuts`, `por_zona`, `regiones`) | [regiones.json](./ejemplos/regiones.json) |
| GET | `/api/v1/regiones/{region_id}` | detalle + polígono GeoJSON | [region_detalle.json](./ejemplos/region_detalle.json) |
| GET | `/api/v1/regiones/calcular-bbox?oeste&sur&este&norte&nombre` | resolver un bbox dibujado por el usuario (centro, GeoJSON, celdas por dataset) | [calcular_bbox.json](./ejemplos/calcular_bbox.json) |

`zona` ∈ `mexico | centroamerica | mexico_centroamerica | caribe | sudamerica | latinoamerica | referencia_global`.

Regiones predefinidas (23): `noreste_mexico`, `noroeste_mexico_sonora_sinaloa`, `peninsula_baja_california`, `altiplano_central_bajio`, `golfo_centro_veracruz`, `pacifico_sur_mexico`, `sureste_mexico`, `peninsula_yucatan`, `corredor_seco_centroamericano`, `guatemala_belice`, `el_salvador_honduras`, `nicaragua`, `costa_rica_panama`, `istmo_centroamericano_completo`, `caribe_antillas_mayores`, `andes_norte_colombia_venezuela`, `andes_centrales_peru_bolivia`, `amazonia`, `nordeste_brasil_sertao`, `cuenca_plata_pampa`, `chile_central_cuyo`, `sahel`, `india_monzon`.

### Análisis (aceptan `region`/bbox, `inicio`, `fin`, `sintetico`, `descargar`)

| Método | Ruta | Extra params | Para qué | Ejemplo |
|---|---|---|---|---|
| GET | `/api/v1/series/{variable_id}` | `anual=suma\|media\|media_ponderada_dias`, `unidad`, `mascara` | gráfica de serie, climatología y anomalías | [serie.json](./ejemplos/serie.json), [serie_anual.json](./ejemplos/serie_anual.json) |
| GET | `/api/v1/tendencias/{variable_id}` | `alfa`, `incluir_serie`, `anual`, `mascara` | tendencia OLS(n_ef) + Mann-Kendall + recta OLS | [tendencia.json](./ejemplos/tendencia.json) |
| GET | `/api/v1/indicadores` | `cortar_en_anio`, `alfa`, `mascara` | 5 extremos anuales IMERG + `dos_caras_extremos` | [indicadores.json](./ejemplos/indicadores.json) |
| GET/POST | `/api/v1/escaner` | `grupo`, `fuente`, `alfa` (POST: `variables[]`, `bbox[]`) | ranking de todas las variables por veredicto y \|SNR\| | [escaner.json](./ejemplos/escaner.json) |
| GET/POST | `/api/v1/dos-caras` | `variable`, `region_a`, `region_b`, `variable_b` (POST: `bbox_a`, `bbox_b`) | comparar 2 regiones o 2 variables | [dos_caras.json](./ejemplos/dos_caras.json), [dos_caras_post_variables.json](./ejemplos/dos_caras_post_variables.json) |
| GET | `/api/v1/mapas/{variable_id}` | `alfa`, `mascara` | mapa por píxel (matrices lat × lon) | [mapa.json](./ejemplos/mapa.json) |

### OPeNDAP y caché (administración / precarga)

| Método | Ruta | Uso | Ejemplo |
|---|---|---|---|
| GET | `/api/v1/opendap/consulta?variable&region…` | ver índices y URLs DAP4/DAP2 (debug) | [opendap_consulta.json](./ejemplos/opendap_consulta.json) |
| POST | `/api/v1/opendap/precargar` (alias `/api/v1/descargas`) | precargar en RAM en segundo plano → **202** + tarea | — |
| GET | `/api/v1/descargas` · `/api/v1/descargas/{tarea_id}` | progreso de la tarea (polling) | [descargas.json](./ejemplos/descargas.json) |
| GET / DELETE | `/api/v1/cache?variable=` | inventario / vaciar caché RAM | [cache.json](./ejemplos/cache.json) |

Body de precarga:
```json
{ "variable": "lluvia_gpcp", "region": "noreste_mexico", "bbox": null,
  "inicio": "2001-01", "fin": "2024-12", "forzar": false, "sincrono": false }
```

---

## 5. Formas de respuesta clave

### `RegionDTO` (aparece en `region`, `metadata.region`, `metadatos.region`)
```jsonc
{
  "id": "noreste_mexico", "nombre": "Noreste de México", "descripcion": "…",
  "zona": "mexico", "pais": "México", "es_latinoamerica": true,
  "bbox": [-106.0, 22.0, -97.0, 30.0],              // [oeste, sur, este, norte]
  "predefinida": true,
  "coordenadas": {
    "centro": { "lat": 26.0, "lon": -101.5 },
    "esquinas": { "suroeste": {…}, "sureste": {…}, "noreste": {…}, "noroeste": {…} },
    "poligono_geojson": { "type": "Polygon", "coordinates": [[[-106,22], …]] }, …
  },
  "mallas_reales": { "gpcp": { "resolucion": "0.5° × 0.5°", "n_celdas": 288, … }, "merra2": {…}, "gldas": {…}, "imerg": {…} },
  "shortcut": { "query_region": "?region=noreste_mexico", "query_bbox": "?oeste=-106&sur=22&este=-97&norte=30", … }
}
```
> ⚠️ El GeoJSON del backend usa `[lon, lat]` y `centro.lon`; el front usa `{lat, lng}`.

### `/api/v1/series/{id}` → `SerieRespuestaDTO`
```jsonc
{ "variable": "lluvia_gpcp", "nombre_simple": "Precipitación (P)", "unidad": "mm/mes",
  "frecuencia_serie": "mensual",                      // "anual" si ?anual=…
  "region": RegionDTO, "periodo": ["2001-01","2024-12"],
  "media_climatologia": 76.22,
  "climatologia_mensual": [ { "mes": 1, "valor": 41.66 }, … ],
  "calidad": { "aceptada": true, "n_esperados": 288, "n_faltantes": 0, "fraccion_faltante": 0.0, "motivo": null },
  "puntos": [ { "fecha": "2001-01", "t": 0.0, "valor": 52.37, "anomalia": 10.71 }, … ],
  "fuente_datos": "sintetico" }
```

### `/api/v1/tendencias/{id}` → `TendenciaRespuestaDTO`
```jsonc
{ "tendencia": {
    "variable": "lluvia_gpcp", "region": "noreste_mexico", "periodo": ["2001-01","2024-12"],
    "n": 288, "r1": 0.0795, "n_ef": 245.6,
    "pendiente_ols_decada": -6.92, "ic95_decada": [-7.81, -6.03], "p_t": 1.5e-37,
    "sen_decada": -7.04, "mk_z": -11.09, "mk_tau": -0.507, "p_mk": 0.0,
    "cambio_pct_decada": -9.08, "snr": -1.009, "n_star_anios": 8.61, "anios_faltantes": 0.0,
    "veredicto": "significativo",          // "significativo" | "indicio" | "sin tendencia clara"
    "direccion": "baja",                   // "sube" | "baja" | "estable"
    "metodos": ["ols_neff", "mk_hamed_rao"] },
  "metadatos": { "unidad": "mm/mes", "unidad_pendiente": "mm/mes/decada", "region": RegionDTO,
                 "recta_ols": { "beta0": 8.28, "beta1_por_paso": -0.0577 }, "calidad": {…}, "fuente_datos": "sintetico", … },
  "puntos": [ PuntoSerie… ],              // si incluir_serie=true
  "climatologia_mensual": [ … ] }
```
`escaner.resultados[]` y `dos-caras.region_a/region_b` reutilizan este mismo objeto `tendencia` (+ `nombre_simple`, `unidad`, etc. en el escáner).

### `/api/v1/mapas/{id}`
```jsonc
{ "variable": "lluvia_gpcp", "unidad_pendiente": "mm/mes/decada", "alfa": 0.05, "fuente_datos": "sintetico",
  "codigos_veredicto": { "2": "significativo", "1": "indicio", "0": "sin tendencia clara" },
  "lat": [22.25, …], "lon": [-105.75, …],
  "pendiente_decada": [[…], …],   // matriz [lat][lon]; null = píxel sin datos
  "p_t": [[…]], "p_mk": [[…]], "veredicto": [[2.0, …]],
  "resumen": { "n_pixeles_total": 16, "n_pixeles_validos": 16, "n_significativos_secos": 16, "n_significativos_humedos": 0, "n_indicio": 0 } }
```

### `/api/v1/dos-caras`
```jsonc
{ "region_a": Tendencia, "region_b": Tendencia,
  "signo_opuesto": true, "ambas_significativas": true,
  "dos_caras": true,                       // ← true si ambas significativas y con signo opuesto
  "detalle_a": TendenciaRespuesta, "detalle_b": TendenciaRespuesta }
```

### `/api/v1/indicadores`
```jsonc
{ "region": RegionDTO, "periodo": ["2001","2024"], "fuente_datos": "sintetico",
  "indicadores": {
    "cdd_imerg": { "nombre_simple": "Racha seca más larga", "unidad": "dias",
                   "serie": [ { "anio": 2001, "valor": 102.2 }, … ], "tendencia": Tendencia },
    "r20mm_imerg": {…}, "dias_humedos_imerg": {…}, "prcptot_imerg": {…}, "sdii_imerg": {…} },
  "dos_caras_extremos": { "region_a": Tendencia(cdd), "region_b": Tendencia(r20mm), "dos_caras": … } }
```

---

## 6. Errores

Todos los errores propios devuelven `{ "error": <codigo>, "mensaje": <texto>, … }`, excepto la validación de FastAPI (422 con `detail`).

| HTTP | `error` | Cuándo | Ejemplo |
|---|---|---|---|
| 400 | `parametro_invalido` | fecha mal formada, bbox incompleto, periodo inválido | [error_400_bbox.json](./ejemplos/error_400_bbox.json) |
| 404 | `no_encontrado` | variable/región/dataset/tarea inexistente | [error_404_variable.json](./ejemplos/error_404_variable.json) |
| 404 | `datos_no_disponibles_en_memoria` | no hay datos en RAM y no se pidió `descargar`/`sintetico`; trae `variable`, `region`, `periodo`, `sugerencia` | [error_404_datos.json](./ejemplos/error_404_datos.json) |
| 422 | `serie_rechazada` | demasiados meses faltantes; trae `reporte` | — |
| 422 | *(FastAPI)* `detail[]` | tipo/rango inválido (p. ej. `alfa=0.9`) | [error_422_param.json](./ejemplos/error_422_param.json) |

---

## 7. Cliente TypeScript sugerido (Next.js)

```ts
// frontend/src/lib/api.ts
import type { VariableId } from "@/types/geo";

export const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export const VAR_TO_DTE: Partial<Record<VariableId, "P" | "T" | "SM" | "ET">> = {
  precipitation: "P", temperature: "T", moisture: "SM", evapotranspiration: "ET",
};

export interface DteVariable {
  id: string; code: "P" | "T" | "SM" | "ET"; name: string; question: string;
  units: { monthly: string; annual: string; slope_decade: string };
  monthly: { date: string; value: number | null; z: number | null }[];
  annual: { year: number; value: number | null; fitted: number | null }[];
  slope_decade: number; ci95: [number, number];
  p_raw: number; p_holm: number; significant: boolean;
  direction: "aumento" | "disminucion" | "estable"; label: string; summary_text: string;
  sensible_al_rezago: boolean;
  quality: { warnings: string[]; complete_period: boolean; [k: string]: unknown };
}

export interface DteResult {
  metadata: { period: [string, string]; alpha: number; source: "sintetico" | "opendap_memoria"; region: unknown; [k: string]: unknown };
  variables: Record<"P" | "T" | "SM" | "ET", DteVariable>;
  joint: {
    standardized_anomalies: { date: string; P: number | null; T: number | null; SM: number | null; ET: number | null }[];
    pairs_list: { pair: string; var_x: string; var_y: string; question: string; r: number; n: number; summary_text: string }[];
  };
  conclusion: {
    joint_reading: string;
    changes_with_statistical_evidence: string[];
    inconclusive_or_insufficient_evidence: string[];
    exploratory_associations: string[];
    methodological_limits: string[];
  };
}

export class ApiError extends Error {
  constructor(public status: number, public body: { error?: string; mensaje?: string; [k: string]: unknown }) {
    super(body?.mensaje ?? `HTTP ${status}`);
  }
}

async function get<T>(path: string, params: Record<string, string | number | boolean | undefined> = {}, signal?: AbortSignal): Promise<T> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined) qs.set(k, String(v));
  const res = await fetch(`${BACKEND_URL}${path}${qs.size ? `?${qs}` : ""}`, { signal });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, body);
  return body as T;
}

/** bbox [oeste, sur, este, norte] a partir del polígono GeoJSON ([lon, lat]) que ya genera el front. */
export function bboxFromPolygon(coords: [number, number][][]) {
  const pts = coords[0];
  const lons = pts.map((p) => p[0]), lats = pts.map((p) => p[1]);
  return { oeste: Math.min(...lons), sur: Math.min(...lats), este: Math.max(...lons), norte: Math.max(...lats) };
}

export function fetchDteResult(opts: {
  region?: string; bbox?: { oeste: number; sur: number; este: number; norte: number };
  inicio: string; fin: string; sintetico?: boolean; descargar?: boolean; signal?: AbortSignal;
}) {
  return get<DteResult>("/demo/result", {
    region: opts.region ?? "custom",
    ...opts.bbox,
    inicio: opts.inicio.slice(0, 7),
    fin: opts.fin.slice(0, 7),
    sintetico: opts.sintetico,
    descargar: opts.descargar,
  }, opts.signal);
}

export const fetchSalud = () => get<{ estado: string; credenciales_earthdata: { listo: boolean } }>("/api/v1/salud");
export const fetchCatalogo = () => get<Record<string, unknown>>("/api/v1/catalogo");
export const csvUrl = (freq: "mensual" | "anual", q: Record<string, string>) =>
  `${BACKEND_URL}/demo/csv/${freq}?${new URLSearchParams(q)}`;
```

Uso en `ResultsStep` (reemplaza `ILLUSTRATIVE`):

```ts
const result = await fetchDteResult({
  region: slugify(regionData.regionName),
  bbox: bboxFromPolygon(regionData.geoJsonPolygon.coordinates),
  inicio: range.start, fin: range.end,
  sintetico: process.env.NODE_ENV !== "production",
});
for (const id of selectedVariables) {
  const code = VAR_TO_DTE[id];
  if (!code) continue;                       // "vegetation" no existe en el backend
  const v = result.variables[code];
  // v.slope_decade, v.ci95, v.p_holm, v.significant, v.units.slope_decade, v.summary_text
}
const isDemo = result.metadata.source === "sintetico";
```

---

## 8. Incompatibilidades actuales detectadas en el frontend

1. **`POST ${BACKEND_URL}/analyze` no existe en el backend** ([`ResultsStep.tsx` L55](../../frontend/src/components/nasa/ResultsStep.tsx#L55)) → siempre fallará con 404. Sustituir por `GET /demo/result` (§3).
2. **`vegetation` (NDVI)** no tiene equivalente en el backend; ocultarla o marcarla como "próximamente".
3. **Fechas**: `range.start/end` deben recortarse a `AAAA-MM`.
4. **Geometría**: el backend trabaja con bbox rectangular, no con el triángulo; el análisis cubre la caja envolvente del polígono.
5. Los valores de `ILLUSTRATIVE` (pendiente en mm por década, IC, p-Holm) se corresponden 1:1 con `variables[X].slope_decade`, `ci95`, `p_holm`, `significant`.
