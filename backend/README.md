# Backend y API REST — Las Dos Caras de la Lluvia (FastAPI + OPeNDAP en Memoria)

API en **FastAPI** y motor estadístico/científico para consultar los datasets de **NASA Earthdata (GES DISC)** mediante **OPeNDAP en memoria RAM (sin almacenar archivos NetCDF/HDF en disco)**:

- **GPCP mensual v3.3** (`GPCPMON`, 0.5°, 1983–presente): `sat_gauge_precip` (`mm/dia` → `mm/mes` × días reales del mes).
- **MERRA-2 v5.12.4** (`M2TMNXFLX` y `M2TMNXSLV`, 0.5° × 0.625°, 1980–presente):
  - `PRECTOTCORR` (`kg m-2 s-1` × 86400 → `mm/dia`)
  - `T2M` (`K` − 273.15 → `degC`)
  - `TQV` (`kg m-2` → `mm`)
- **GPM IMERG Final v07** (`GPM_3IMERGM` mensual y `GPM_3IMERGDF` diario, 0.1°, 1998–presente):
  - `precipitation` mensual (grupo HDF5 `Grid`, `mm/h` × 24 → `mm/dia`)
  - `precipitation` diaria (`mm/dia`) → cálculo por píxel de los **5 indicadores anuales ETCCDI**:
    - `cdd_imerg` (`CDD`, racha seca más larga con $P_d < 1\text{ mm}$, en `dias`)
    - `r20mm_imerg` (`R20mm`, días con $P_d \ge 20\text{ mm}$, en `dias`)
    - `dias_humedos_imerg` (`W`, días con $P_d \ge 1\text{ mm}$, en `dias`)
    - `prcptot_imerg` (`PRCPTOT`, lluvia acumulada en días húmedos, en `mm/anio`)
    - `sdii_imerg` (`SDII = PRCPTOT / W`, en `mm/dia`)

---

## Cómo funciona la arquitectura FastAPI + OPeNDAP sin disco

1. **Búsqueda de gránulos en CMR**: `earthaccess.search_data` obtiene los metadatos UMM-G del periodo solicitado.
2. **Recorte en el servidor OPeNDAP (Constraint Expressions)**:
   - Se calculan los índices espaciales exactos `[lat_i0:1:lat_i1]` y `[lon_i0:1:lon_i1]` del bounding box a partir de la malla de cada colección (`indices_bbox_grilla`).
   - Se construye la URL OPeNDAP **DAP4** (`.dap.nc4?dap4.ce=...`) o **DAP2** (`.nc4?...`) pidiendo únicamente la variable requerida y la ventana geográfica (unos pocos KB por mes en lugar de decenas de MB por archivo global).
3. **Apertura directa en RAM (`0 bytes` en disco)**:
   - Los bytes binarios devueltos por OPeNDAP se abren directamente en memoria con `netCDF4.Dataset("opendap_response.nc", mode="r", memory=resp.content)` y `xarray.backends.NetCDF4DataStore`.
4. **Caché LRU en memoria RAM (`CACHE_MEMORIA`)**:
   - El `xr.DataArray` ya recortado, normalizado a `(time, lat, lon)` y convertido a las unidades finales del catálogo se guarda en una caché LRU en memoria RAM (`CacheMemoriaLRU`), capaz además de reutilizar subrangos temporales en RAM sin volver a consultar OPeNDAP.

---

## Endpoints principales (`/api/v1`)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/v1/salud` | Estado del servidor, uso de memoria RAM y credenciales de NASA Earthdata |
| `GET` | `/api/v1/catalogo` | Catálogo completo (`datasets`, `variables`, `regiones`, `periodos`) |
| `GET` | `/api/v1/datasets` | Lista `gpcp`, `merra2` e `imerg` con sus endpoints OPeNDAP y variables |
| `GET` | `/api/v1/variables` | Filtra variables por `grupo`, `fuente`, `frecuencia`, `solo_analizables` |
| `GET` | `/api/v1/regiones` | Lista regiones predefinidas (`sahel`, `noreste_mexico`, `sureste_mexico`, `amazonia`, `india_monzon`) |
| `GET` | `/api/v1/opendap/consulta` | Muestra los índices `[lat0:1:lat1]`, `[lon0:1:lon1]` y las URLs OPeNDAP DAP4/DAP2 |
| `GET` | `/api/v1/series/{variable_id}` | Serie regional, climatología mensual, anomalías y reporte de calidad |
| `GET` | `/api/v1/tendencias/{variable_id}` | Resultado oficial de `calcular_tendencia` (20 claves) + recta OLS y puntos |
| `GET` | `/api/v1/indicadores` | Los 5 indicadores anuales de extremos de lluvia (IMERG diario) + `dos_caras_extremos` |
| `GET`/`POST` | `/api/v1/escaner` | Escáner de todas las variables de una región ordenadas por veredicto y `\|SNR\|` |
| `GET`/`POST` | `/api/v1/dos-caras` | Compara dos regiones o dos variables/indicadores (`comparar_dos_caras`) |
| `GET` | `/api/v1/mapas/{variable_id}` | Mapa de tendencias por píxel (`pendiente_decada`, `p_t`, `p_mk`, `veredicto`) |
| `GET`/`DELETE` | `/api/v1/cache` | Inspecciona o vacía la caché LRU en memoria RAM |
| `POST` | `/api/v1/opendap/precargar` | Consulta OPeNDAP en segundo plano y precarga el cubo regional en memoria RAM |

---

## Levantar la API y ejecutar pruebas

```bash
cd backend
# Servidor FastAPI en http://127.0.0.1:8000 (Swagger UI en /docs):
.venv/bin/python -m core.main servir --host 127.0.0.1 --port 8000 --reload

# Suite completa de pruebas (64 tests, 0 archivos en disco):
.venv/bin/python -m pytest -q
```
