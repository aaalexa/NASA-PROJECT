---
name: api-cliente-backend
description: Úsala siempre que haya que conectar el frontend Next.js con la API FastAPI del backend, configurar NEXT_PUBLIC_BACKEND_URL o CORS, crear o modificar src/lib/api.ts, manejar modos de datos (sintetico, descargar, estricto_memoria), gestionar errores HTTP (400, 404 datos_no_disponibles_en_memoria, 422 serie_rechazada) o precargar cubos OPeNDAP en RAM (/api/v1/opendap/precargar y /api/v1/descargas).
---

# Cliente HTTP, modos de datos y errores del backend

## Objetivo

Centralizar todas las llamadas del frontend Next.js hacia la API FastAPI (`v0.2.0`) en un único módulo tipado (`src/lib/api.ts`), garantizando formato correcto de fechas (`AAAA-MM`), coordenadas (`oeste, sur, este, norte`), control de concurrencia/cancelación (`AbortController`) y manejo uniforme de los errores de dominio del backend.

Esquemas completos de error, variables de entorno y ciclo de precarga en RAM: [referencia.md](referencia.md).
Plantilla lista para copiar a `frontend/src/lib/api.ts`: [scripts/api_client_plantilla.ts](scripts/api_client_plantilla.ts).

## 1. URL base y variables de entorno

| Entorno | `NEXT_PUBLIC_BACKEND_URL` | Notas |
|---|---|---|
| Desarrollo local | `http://localhost:8000` | Uvicorn directo o `docker compose up -d api` |
| Producción | `https://api.moody-trends.earth` | Proxy inverso Caddy con TLS y timeout de 180 s |

- En `frontend/.env.local` define `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`.
- **CORS**: el backend ya autoriza `http://localhost:3000`, `http://localhost:5173`, `https://moody-trends.earth` y `https://www.moody-trends.earth` mediante `NASA_CORS_ORIGINS`.
- **Sin tokens en el cliente**: las credenciales de NASA Earthdata viven exclusivamente en el servidor. Nunca pidas ni envíes credenciales de Earthdata desde el navegador.

## 2. Los 3 modos de acceso a datos en la API

El backend opera con **OPeNDAP en memoria RAM (0 archivos en disco)**. Todos los endpoints de análisis aceptan estos parámetros booleanos:

1. **`sintetico=true` (modo desarrollo / demo determinista)**:
   - Genera cubos sintéticos deterministas al instante sin conexión a NASA.
   - Ideal para desarrollo de UI, pruebas E2E o demostraciones sin latencia.
   - La respuesta marca `"fuente_datos": "sintetico"` (en `/api/v1/*`) o `"metadata": { "source": "sintetico" }` (en `/demo/result`).
2. **`descargar=true` (consulta OPeNDAP en vivo)**:
   - Si el cubo regional no está en la caché LRU de RAM, consulta NASA GES DISC en vivo vía OPeNDAP y lo guarda en RAM.
   - Puede tardar entre 5 s y 90 s según la región y el rango de años. Usa siempre `AbortController` y estados de carga claros.
3. **Sin `sintetico` ni `descargar` (solo caché RAM)**:
   - En `/api/v1/*`: si el cubo no está en RAM, devuelve **HTTP 404** con `"error": "datos_no_disponibles_en_memoria"`.
   - **Excepción en `/demo/result`**: por defecto hace fallback automático a datos sintéticos si no están en RAM. Si quieres desactivar ese fallback y recibir el 404, envía **`estricto_memoria=true`**.

## 3. Reglas obligatorias de formato en peticiones

- **Fechas siempre en `AAAA-MM`**: recorta cualquier ISO string con `fecha.slice(0, 7)`. Enviar `2001-01-01` produce **HTTP 400 `parametro_invalido`**.
- **Bounding box completo o ausente**: si envías coordenadas (`oeste`, `sur`, `este`, `norte`), debes enviar **las cuatro** y cumplir `oeste < este` (`[-180, 180]`) y `sur < norte` (`[-90, 90]`). Enviar solo 1, 2 o 3 coordenadas produce **HTTP 400**.
- **Nivel de significancia `alfa`**: debe cumplir `0 < alfa < 0.5` (por defecto `0.05`). Un valor fuera de rango produce **HTTP 422**.

## 4. Manejo de errores en el frontend

Usa una clase `ApiError` que conserve `status` y el payload JSON del backend:

| Código HTTP | `body.error` | Causa y acción recomendada en la UI |
|---|---|---|
| `400` | `"parametro_invalido"` | Fecha que no es `AAAA-MM`, `inicio > fin` o bbox incompleto. Corrige el formateo antes de enviar. |
| `404` | `"no_encontrado"` | `variable_id`, `region_id`, `dataset_id` o `tarea_id` inexistente. |
| `404` | `"datos_no_disponibles_en_memoria"` | El cubo no está en RAM. Ofrece al usuario consultar en vivo (`descargar=true`), lanza precarga (`POST /api/v1/opendap/precargar`) o muestra modo demo (`sintetico=true`). |
| `422` | `"serie_rechazada"` | La serie supera el 10 % de datos faltantes. Lee `body.reporte` (`fraccion_faltante`, `n_faltantes`) y muestra aviso de cobertura insuficiente. |
| `422` | *(sin `error`, trae `detail: [...]`)* | Error de validación Pydantic/FastAPI en query/body (ej. `alfa=0.9`). |

## 5. Flujo de precarga asíncrona en RAM (opcional para UX fluida)

Cuando el usuario selecciona una región y periodo en los pasos previos del wizard (`RegionStep` / `PeriodStep`), puedes precargar en segundo plano antes de llegar a `ResultsStep`:

1. `POST /api/v1/opendap/precargar` con `{ variable, region, bbox, inicio, fin }` → devuelve **HTTP 202** y `{ id, estado, progreso, ... }`.
2. Consulta el progreso con `GET /api/v1/descargas/{tarea_id}` hasta que `estado === "completada"` (o `"error"`).
3. Al abrir resultados, los cubos ya estarán en la caché LRU en RAM (`fuente_datos: "opendap_memoria"`).

## Errores comunes

- **Llamar a `POST /analyze`**: ese endpoint no existe en el backend (era un placeholder en `ResultsStep.tsx`). Usa `GET /demo/result` o los endpoints de `/api/v1/*`.
- **Pasar `range.start` completo (`"2015-01-01"`)**: el backend exige `"AAAA-MM"`. Aplica `.slice(0, 7)` siempre en el cliente HTTP.
- **No distinguir datos sintéticos de datos reales de NASA**: revisa siempre `metadata.source === "sintetico"` o `fuente_datos === "sintetico"` y muestra una etiqueta visible en la interfaz.

