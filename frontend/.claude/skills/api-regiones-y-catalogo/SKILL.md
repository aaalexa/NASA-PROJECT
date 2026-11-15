---
name: api-regiones-y-catalogo
description: Úsala al poblar o sincronizar regiones predefinidas, variables y datasets entre el frontend (PredefinedRegions.ts, catalog.ts, RegionStep.tsx, GlobeGlExplorer.tsx) y el backend (/api/v1/catalogo, /api/v1/regiones, /api/v1/regiones/calcular-bbox, /api/v1/variables, /api/v1/datasets), o al convertir entre los triángulos/GeoJSON del globo ({lat, lng}) y los bounding boxes [oeste, sur, este, norte] y mallas reales de NASA.
---

# Catálogo, regiones y conversión geométrica (Globo ↔ Backend)

## Objetivo

Sincronizar el selector de regiones, el globo 3D (`RegionStep.tsx`, `PredefinedRegions.ts`, `GlobeGlExplorer.tsx`) y el catálogo de variables (`src/lib/catalog.ts`) con los endpoints de metadatos del backend:
- `GET /api/v1/catalogo` (inicialización completa en 1 llamada)
- `GET /api/v1/regiones`, `GET /api/v1/regiones/{region_id}` y `GET /api/v1/regiones/calcular-bbox`
- `GET /api/v1/variables`, `GET /api/v1/variables/{variable_id}` y `GET /api/v1/datasets`

Tabla de las 23 regiones del backend, mapeo con `PREDEFINED_REGIONS` y outputs reales: [referencia.md](referencia.md).

## 1. Diferencias geométricas entre el Frontend y el Backend

1. **Triángulo vs Bounding Box rectangular**:
   - El frontend permite elegir 3 puntos en el globo (`triangleVertices: [GeoPoint, GeoPoint, GeoPoint]`) y construye `geoJsonPolygon`.
   - El backend recorta los cubos OPeNDAP de NASA mediante cajas rectangulares `bbox = [oeste, sur, este, norte]` (`[lon_min, lat_min, lon_max, lat_max]`).
   - **Cómo conectar ambos**:
     - Si la región elegida coincide con una de las 23 regiones predefinidas del backend (ej. `"nicaragua"`, `"amazonia"`, `"sahel"`), envía únicamente `?region=<id_backend>` sin coordenadas para aprovechar la definición oficial y su caché en RAM.
     - Si es un triángulo libre o una región de `PredefinedRegions.ts` que no está en el backend (ej. `"mediterranean"`, `"california"`, `"arctic"`, `"coral"`), calcula `oeste`, `sur`, `este`, `norte` a partir de `triangleVertices` y envíalos junto con `?region=<slug>`.

2. **Nombres de propiedades (`lng` vs `lon`)**:
   - Frontend (`GeoPoint`): `{ lat: number, lng: number }`.
   - Backend (`RegionDTO.coordenadas.centro` y `esquinas`): `{ lat: number, lon: number }`.
   - GeoJSON (`poligono_geojson.coordinates[0]`): pares `[lon, lat]` (estándar RFC 7946).

## 2. Mapeo de `PREDEFINED_REGIONS` (`PredefinedRegions.ts`) al Backend

| `id` en `PredefinedRegions.ts` | ¿Existe en `regiones.yaml` del backend? | `region_id` equivalente en el backend | Cómo enviarlo a la API |
|---|---|---|---|
| `"nicaragua"` | Sí | `"nicaragua"` (o `"corredor_seco_centroamericano"`) | `?region=nicaragua` |
| `"amazon"` | Sí (con otro id) | `"amazonia"` | `?region=amazonia` |
| `"sahara"` | Sí (Sahel africano) | `"sahel"` | `?region=sahel` |
| `"mediterranean"` | No | — | `?region=mediterranean&oeste=-4&sur=35.5&este=24&norte=44` |
| `"northeurope"` | No | — | `?region=northeurope&oeste=5&sur=55.5&este=26&norte=61` |
| `"california"` | No | — | `?region=california&oeste=-122.4&sur=35&este=-118.7&norte=40.2` |
| `"arctic"` | No | — | `?region=arctic&oeste=-40&sur=72&este=15&norte=82` |
| `"coral"` | No | — | `?region=coral&oeste=142.5&sur=-24.5&este=153.3&norte=-10.5` |

> **Recomendación**: puedes cargar dinámicamente las 23 regiones oficiales del backend con `GET /api/v1/regiones` (que incluye 8 regiones de México, 6 de Centroamérica, 1 del Caribe, 6 de Sudamérica y 2 de referencia global) usando el arreglo `response.shortcuts`.

## 3. Vista previa de grilla NASA para cualquier selección (`GET /api/v1/regiones/calcular-bbox`)

Cuando el usuario termina de colocar los 3 vértices en el globo en `RegionStep.tsx`, puedes llamar a:
`GET /api/v1/regiones/calcular-bbox?oeste=...&sur=...&este=...&norte=...&nombre=...`

Devuelve al instante (sin consultar a NASA):
- `coordenadas.centro` (`{ lat, lon }`), `extension_grados` (`{ ancho_lon, alto_lat }`) y `poligono_geojson`.
- `mallas_reales`: cuántas celdas reales (`n_lat`, `n_lon`, `n_celdas`) caen dentro de la caja para cada satélite:
  - `gpcp` (`0.5° × 0.5°`)
  - `merra2` (`0.5° × 0.625°`)
  - `gldas` (`0.25° × 0.25°`)
  - `imerg` (`0.1° × 0.1°`)
- `shortcut.query_bbox`: el query string exacto listo para concatenar a cualquier petición de análisis.

## Errores comunes

- **Enviar un triángulo degenerado con `oeste === este` o `sur === norte`**: si los 3 puntos tienen la misma latitud o longitud, el backend devuelve `400 parametro_invalido` (`"oeste debe ser menor que este"`). Añade un margen mínimo (ej. `±0.25°`) si el área colapsa en una línea.
- **Cruzar el antimeridiano (`oeste > este`)**: el backend exige `-180 <= oeste < este <= 180`.

