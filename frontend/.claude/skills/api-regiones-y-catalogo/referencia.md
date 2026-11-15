# Referencia — Regiones predefinidas, mallas NASA y outputs de catálogo

## 1. Las 23 regiones predefinidas del backend (`GET /api/v1/regiones`)

Filtros disponibles en `GET /api/v1/regiones`:
- `zona`: `"mexico"` | `"centroamerica"` | `"mexico_centroamerica"` | `"caribe"` | `"sudamerica"` | `"latinoamerica"` | `"referencia_global"`
- `solo_latinoamerica`: `true` | `false`

| `id` | `zona` | `bbox` (`[oeste, sur, este, norte]`) |
|---|---|---|
| `noreste_mexico` | `mexico` | `[-106.0, 22.0, -97.0, 30.0]` |
| `noroeste_mexico_sonora_sinaloa` | `mexico` | `[-115.0, 23.0, -107.0, 32.5]` |
| `peninsula_baja_california` | `mexico` | `[-117.2, 22.8, -109.3, 32.6]` |
| `altiplano_central_bajio` | `mexico` | `[-104.5, 18.5, -97.5, 23.5]` |
| `golfo_centro_veracruz` | `mexico` | `[-99.0, 17.0, -93.5, 22.5]` |
| `pacifico_sur_mexico` | `mexico` | `[-105.5, 15.5, -95.0, 20.5]` |
| `sureste_mexico` | `mexico` | `[-95.0, 14.5, -90.0, 19.5]` |
| `peninsula_yucatan` | `mexico` | `[-91.5, 17.5, -86.5, 21.8]` |
| `corredor_seco_centroamericano` | `centroamerica` | `[-91.0, 12.0, -85.0, 16.0]` |
| `guatemala_belice` | `centroamerica` | `[-92.3, 13.7, -88.1, 18.5]` |
| `el_salvador_honduras` | `centroamerica` | `[-90.2, 12.9, -83.1, 16.5]` |
| `nicaragua` | `centroamerica` | `[-87.7, 10.7, -83.1, 15.1]` |
| `costa_rica_panama` | `centroamerica` | `[-86.0, 7.2, -77.1, 11.3]` |
| `istmo_centroamericano_completo` | `centroamerica` | `[-92.5, 7.0, -77.0, 18.6]` |
| `caribe_antillas_mayores` | `caribe` | `[-85.0, 17.5, -65.0, 23.5]` |
| `andes_norte_colombia_venezuela` | `sudamerica` | `[-78.0, 1.0, -66.0, 11.5]` |
| `andes_centrales_peru_bolivia` | `sudamerica` | `[-78.0, -20.0, -64.0, -5.0]` |
| `amazonia` | `sudamerica` | `[-72.0, -12.0, -50.0, 2.0]` |
| `nordeste_brasil_sertao` | `sudamerica` | `[-46.0, -15.0, -34.5, -2.5]` |
| `cuenca_plata_pampa` | `sudamerica` | `[-65.0, -38.0, -53.0, -24.0]` |
| `chile_central_cuyo` | `sudamerica` | `[-73.5, -39.0, -67.5, -29.0]` |
| `sahel` | `referencia_global` | `[-15.0, 10.0, 20.0, 18.0]` |
| `india_monzon` | `referencia_global` | `[72.0, 15.0, 88.0, 27.0]` |

---

## 2. Output real de `GET /api/v1/regiones/calcular-bbox` (`RegionDTO`)

Petición: `GET /api/v1/regiones/calcular-bbox?oeste=-101&sur=22&este=-97&norte=27&nombre=mi_zona`
```json
{
  "id": "mi_zona",
  "nombre": "mi_zona",
  "descripcion": "Región personalizada [-101, 22, -97, 27]",
  "zona": "personalizada",
  "pais": "Personalizada",
  "es_latinoamerica": true,
  "bbox": [-101.0, 22.0, -97.0, 27.0],
  "predefinida": false,
  "coordenadas": {
    "oeste": -101.0,
    "sur": 22.0,
    "este": -97.0,
    "norte": 27.0,
    "lon_min": -101.0,
    "lat_min": 22.0,
    "lon_max": -97.0,
    "lat_max": 27.0,
    "centro": { "lat": 24.5, "lon": -99.0 },
    "extension_grados": { "ancho_lon": 4.0, "alto_lat": 5.0 },
    "esquinas": {
      "suroeste": { "lat": 22.0, "lon": -101.0 },
      "sureste": { "lat": 22.0, "lon": -97.0 },
      "noreste": { "lat": 27.0, "lon": -97.0 },
      "noroeste": { "lat": 27.0, "lon": -101.0 }
    },
    "poligono_geojson": {
      "type": "Polygon",
      "coordinates": [
        [
          [-101.0, 22.0],
          [-97.0, 22.0],
          [-97.0, 27.0],
          [-101.0, 27.0],
          [-101.0, 22.0]
        ]
      ]
    }
  },
  "mallas_reales": {
    "gpcp": {
      "resolucion": "0.5° × 0.5°",
      "lat_min_real": 22.25,
      "lat_max_real": 26.75,
      "lon_min_real": -100.75,
      "lon_max_real": -97.25,
      "n_lat": 10,
      "n_lon": 8,
      "n_celdas": 80
    },
    "merra2": {
      "resolucion": "0.5° × 0.625°",
      "lat_min_real": 22.0,
      "lat_max_real": 27.0,
      "lon_min_real": -100.625,
      "lon_max_real": -97.5,
      "n_lat": 11,
      "n_lon": 6,
      "n_celdas": 66
    },
    "gldas": {
      "resolucion": "0.25° × 0.25°",
      "lat_min_real": 22.125,
      "lat_max_real": 26.875,
      "lon_min_real": -100.875,
      "lon_max_real": -97.125,
      "n_lat": 20,
      "n_lon": 16,
      "n_celdas": 320
    },
    "imerg": {
      "resolucion": "0.1° × 0.1°",
      "lat_min_real": 22.05,
      "lat_max_real": 26.95,
      "lon_min_real": -100.95,
      "lon_max_real": -97.05,
      "n_lat": 50,
      "n_lon": 40,
      "n_celdas": 2000
    }
  },
  "shortcut": {
    "region": "mi_zona",
    "oeste": -101.0,
    "sur": 22.0,
    "este": -97.0,
    "norte": 27.0,
    "centro_lat": 24.5,
    "centro_lon": -99.0,
    "query_region": "?region=mi_zona",
    "query_bbox": "?oeste=-101&sur=22&este=-97&norte=27"
  }
}
```

---

## 3. Estructura de `GET /api/v1/catalogo` (`200 OK`)

Ideal para cargar una sola vez al iniciar la aplicación Next.js:
```json
{
  "datasets": [
    { "id": "gpcp", "nombre": "GPCP Precipitation Level 3 Monthly 0.5-Degree V3.3" },
    { "id": "merra2", "nombre": "MERRA-2 Monthly Mean (M2TMNXFLX / M2TMNXSLV) V5.12.4" },
    { "id": "gldas", "nombre": "GLDAS Noah Land Surface Model L4 Monthly 0.25 × 0.25 degree V2.1" },
    { "id": "imerg", "nombre": "GPM IMERG Final Precipitation L3 V07 (Mensual y Diario)" }
  ],
  "variables": [ /* 13 variables con unidad_final, pregunta, por_que_elegirla, grilla */ ],
  "regiones": [ /* 23 objetos RegionDTO */ ],
  "periodos": {
    "comun": ["2001-01", "2024-12"],
    "global": ["1983-01", "2024-12"]
  },
  "down_to_earth": { /* el mismo objeto que devuelve GET /catalog */ }
}
```

