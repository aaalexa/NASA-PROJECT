---
name: api-down-to-earth
description: Úsala al conectar o modificar ResultsStep.tsx, GuidedFlow.tsx o cualquier vista que muestre el análisis principal "Down to Earth" de las 4 variables (P, T, SM, ET), las tendencias con OLS + HAC (Newey-West) + corrección de Holm, la lectura conjunta de anomalías estandarizadas (P-SM, T-SM, P-ET), el catálogo GET /catalog o la descarga de CSV (GET /demo/csv/mensual y GET /demo/csv/anual).
---

# Integración Down to Earth (4 Variables: P, T, SM, ET)

## Objetivo

Conectar la vista principal de resultados del frontend (`src/components/nasa/ResultsStep.tsx` y flujo guiado) con los endpoints oficiales de la guía **Down to Earth**:
- `GET /catalog` (o `/api/v1/down-to-earth/catalogo`)
- `GET /demo/result` (o `/api/v1/down-to-earth/analisis`)
- `GET /demo/csv/{mensual|anual}` (o `/api/v1/down-to-earth/csv/{mensual|anual}`)
- **Cálculo exacto desde datos del cliente**: `POST /api/v1/down-to-earth/calcular` (JSON) y
  `POST /api/v1/down-to-earth/calcular/csv` (subida de CSV).
- **Datos reales de NASA para una región** (descarga OPeNDAP en segundo plano, tarda minutos):
  `POST /api/v1/down-to-earth/trabajos` → sondear `GET /api/v1/down-to-earth/trabajos/{id}` →
  `GET /api/v1/down-to-earth/trabajos/{id}/resultado` y `.../tablas/{mensual|anual|limpieza|diccionario|serie_regional}`.

Todos devuelven el mismo esquema `ResultadoDTE` (ver `/docs` del backend y [referencia.md](referencia.md) §5).

Sustituye tanto el objeto estático `ILLUSTRATIVE` como el `fetch("${BACKEND_URL}/analyze")` (que no existe en el backend) por los datos reales calculados por `core/motor/down_to_earth.py`.

Estructura completa del JSON de `/demo/result`, `/catalog` y formato CSV: [referencia.md](referencia.md).

## 1. Mapeo exacto entre `VariableId` (Frontend) y `DteCode` (Backend)

| `VariableId` en `types/geo.ts` | Clave en `variables` (`/demo/result`) | `id` en catálogo backend | Colección NASA | Unidad mensual | Unidad anual | Unidad de `slope_decade` |
|---|---|---|---|---|---|---|
| `"precipitation"` | `"P"` | `lluvia_gpcp` | GPCP v3.3 (`GPCPMON`) | `mm/mes` | `mm/anio` | `mm por década (total anual)` |
| `"temperature"` | `"T"` | `temp_aire` | MERRA-2 (`M2TMNXSLV`) | `°C` | `°C` | `°C por década` |
| `"moisture"` | `"SM"` | `humedad_suelo` | GLDAS Noah v2.1 (`GLDAS_NOAH025_M`) | `m³/m³` | `m³/m³` | `m³/m³ por década` |
| `"evapotranspiration"` | `"ET"` | `evapotranspiracion` | GLDAS Noah v2.1 (`GLDAS_NOAH025_M`) | `mm/mes` | `mm/anio` | `mm por década (total anual)` |
| `"vegetation"` | *No existe* | *No existe* | — | — | — | **No soportada en backend v0.2.0** |

> **Regla sobre `"vegetation"`**: el backend v0.2.0 analiza la familia cerrada de 4 variables `[P, T, SM, ET]` para el ajuste de Holm. Si `selectedVariables` en el frontend incluye `"vegetation"`, omítela al indexar `result.variables` o desactívala en `VariablesStep.tsx` / `catalog.ts`.

## 2. Cómo reemplazar `ILLUSTRATIVE` en `ResultsStep.tsx`

En `ResultsStep.tsx`, cada tarjeta de variable utilizaba:
- `s.slope` → ahora es **`v.slope_decade`** (`number`)
- `s.ci` → ahora es **`v.ci95`** (`[number, number]`, intervalo de confianza del 95 % por década con errores estándar HAC Newey-West `maxlags=1`)
- `s.pHolm` → ahora es **`v.p_holm`** (`number`, p-valor ajustado por Holm sobre las 4 variables)
- `significant` → ahora es **`v.significant`** (`boolean`, equivale a `v.p_holm <= metadata.alpha`)
- `s.unit` → ahora es **`v.units.annual`** (o **`v.units.slope_decade`** si muestras la frase completa)
- Texto explicativo de la tarjeta → **`v.summary_text`** y **`v.label`** (`"aumento con evidencia estadística según este método"`, `"disminución con evidencia estadística según este método"`, `"evidencia insuficiente"` o `"evidencia insuficiente tras el ajuste"`; ver la tabla completa en [referencia.md](referencia.md)). Nunca muestres "sin cambio" ni "estable".

Además, el bloque `result.conclusion` entrega textos listos en español para renderizar debajo de las tarjetas:
- `conclusion.joint_reading`: párrafo síntesis de las 4 variables.
- `conclusion.changes_with_statistical_evidence`: lista de frases con los cambios significativos tras Holm.
- `conclusion.inconclusive_or_insufficient_evidence`: lista de variables sin evidencia suficiente.
- `conclusion.exploratory_associations`: asociaciones mensuales desestacionalizadas y sin tendencia lineal (`P-SM`, `T-SM`, `P-ET`).
- `conclusion.methodological_limits`: advertencias metodológicas obligatorias (correlación ≠ causalidad, sensibilidad al periodo y resolución de grilla).

## 3. Cuidado con el fallback silencioso de `/demo/result`

A diferencia de `/api/v1/series/*` o `/api/v1/tendencias/*`, el endpoint `GET /demo/result` tiene `estricto_memoria=false` por defecto:
- Si no pasas `descargar=true` y el cubo no está en RAM, **devuelve `200 OK` con datos sintéticos** en lugar de `404`.
- **Obligatorio en el frontend**:
  1. Inspecciona siempre `result.metadata.source` (`"sintetico"` vs `"opendap_memoria"`).
  2. Si `result.metadata.source === "sintetico"`, muestra el aviso de datos ilustrativos/sintéticos en la UI.
  3. Si quieres forzar que falle con `404 datos_no_disponibles_en_memoria` cuando no haya datos reales en RAM, añade `estricto_memoria=true` al query string.

## 4. Exportación de CSV en un clic (`GET /demo/csv/{frecuencia}`)

No generes el CSV en el navegador si el usuario pide descargar los datos del análisis Down to Earth; enlaza directamente a:
- **Anual (24 filas, 2001–2024)**: `${BACKEND_URL}/demo/csv/anual?region=...&oeste=...&sur=...&este=...&norte=...&inicio=2001-01&fin=2024-12`
  - Columnas: `anio,P_mm_anio,T_degC,SM_m3_m3,ET_mm_anio`
- **Mensual (288 filas, 2001-01 a 2024-12)**: `${BACKEND_URL}/demo/csv/mensual?region=...`
  - Columnas: `fecha,P_mm_mes,T_degC,SM_m3_m3,ET_mm_mes`

El servidor responde con `Content-Type: text/csv; charset=utf-8` y `Content-Disposition: attachment; filename="down_to_earth_..."`.

## Errores comunes

- **Enviar `inicio=2001-01-01` desde `DateRange`**: `/demo/result` devuelve `400 parametro_invalido`. Usa siempre `range.start.slice(0, 7)`.
- **Tratar `joint.pairs_list[i].r` como causalidad o ponerle p-valor**: el diseño metodológico de *Down to Earth* define las correlaciones `r` de Pearson sobre anomalías estandarizadas `z` (sin ciclo anual y sin tendencia lineal) como **estrictamente exploratorias**. Muestra siempre `question`, `r`, `direction_description` e `interpretation_note`.
- **Ignorar `v.sensible_al_rezago`**: si `v.sensible_al_rezago === true`, la significancia estadística cambia al variar el rezago HAC entre `lag_1`, `lag_2` y `lag_3`; muéstralo como nota de precaución en el desplegable de detalles.

