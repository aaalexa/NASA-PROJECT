# Backend: Moody Trends (the two faces of rain)

A **FastAPI** API and statistical engine that query **NASA Earthdata (GES DISC)** datasets through **OPeNDAP straight into RAM**, never storing NetCDF/HDF files on disk.

## What it contains

| Dataset | Variables | Coverage |
|---|---|---|
| **GPCP monthly v3.3** (`GPCPMON`) | `sat_gauge_precip` (`mm/dia`, converted to `mm/mes` using the real days of each month) | 1983 to present, 0.5° |
| **MERRA-2 v5.12.4** (`M2TMNXFLX`, `M2TMNXSLV`) | `PRECTOTCORR` (`kg m-2 s-1` × 86400 → `mm/dia`), `T2M` (`K` − 273.15 → `degC`), `TQV` (`kg m-2` → `mm`) | 1980 to present, 0.5° × 0.625° |
| **GPM IMERG Final v07** (`GPM_3IMERGM`, `GPM_3IMERGDF`) | `precipitation` monthly (`mm/h` × 24 → `mm/dia`) and daily (`mm/dia`) | 1998 to present, 0.1° |

From IMERG daily precipitation, the **5 annual ETCCDI indicators** are computed per pixel:

| Id | Indicator | Unit |
|---|---|---|
| `cdd_imerg` | `CDD`, longest dry spell (days with P < 1 mm) | `dias` |
| `r20mm_imerg` | `R20mm`, days with P ≥ 20 mm | `dias` |
| `dias_humedos_imerg` | `W`, days with P ≥ 1 mm | `dias` |
| `prcptot_imerg` | `PRCPTOT`, total rain on wet days | `mm/anio` |
| `sdii_imerg` | `SDII = PRCPTOT / W` | `mm/dia` |

The catalog (`src/core/recursos/catalogo.yaml`) defines the variables and their unit conversions. There are 23 predefined regions in `src/core/recursos/regiones.yaml` (Mexico, Central America, the Caribbean, South America, the Sahel, India and more), and any custom region can be passed as a bounding box. Identifiers such as variable ids, units and region ids are in Spanish because the data contract is shared with the frontend.

## How it works

1. **CMR search**: `earthaccess.search_data` finds the granules for the requested period.
2. **Server-side slicing on OPeNDAP**: the `[lat_i0:1:lat_i1]` and `[lon_i0:1:lon_i1]` indices of the bounding box are computed from each collection's grid, and only the needed variable and window are requested (DAP4 `.dap.nc4?dap4.ce=...` or DAP2 `.nc4?...`). That is a few KB per month instead of tens of MB per global file.
3. **Open in RAM**: the returned bytes are opened with `netCDF4.Dataset("opendap_response.nc", mode="r", memory=resp.content)` and `xarray`, with **0 bytes on disk**.
4. **In-memory LRU cache** (`CacheMemoriaLRU`): the sliced `xr.DataArray`, already shaped `(time, lat, lon)` and in final units, is kept in memory and also reused for temporal sub-ranges.
5. **Analysis**: `cos(lat)`-weighted regional series, monthly climatology, anomalies and trends from the statistical engine.

### Statistical engine

- Ordinary least squares (OLS) with **HAC / Newey-West** correction and an effective n from autocorrelation.
- t-test, 95 % confidence interval, rate per decade and percent change.
- **Mann-Kendall** (Hamed-Rao) and **Sen's slope** as cross-checks.
- Years needed to detect the trend (Weatherhead) and SNR.
- A verdict per variable, with **Holm** correction for multiple comparisons.

## Data modes

Analysis endpoints accept these query parameters:

| Parameter | Effect |
|---|---|
| `sintetico=true` | Deterministic synthetic data. Use it to develop without credentials or network. |
| `descargar=true` | If the cube is not in RAM, fetch it live from NASA (slow, needs server-side credentials). |
| *(none)* | RAM only. With no data it returns 404 `datos_no_disponibles_en_memoria`. |
| `estricto_memoria=true` | On `/demo/result`, forces that 404 instead of falling back to synthetic data. |

Responses report their origin in `fuente_datos` (or `metadata.source` for `/demo/result`).

## Endpoints

Interactive docs at `/docs` (Swagger) and `/redoc`. All analysis routes live under `/api/v1`.

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/v1/salud` | Server status, RAM usage and whether Earthdata credentials are set |
| `GET` | `/api/v1/catalogo` | Full catalog: `datasets`, `variables`, `regiones`, `periodos` |
| `GET` | `/api/v1/datasets` | `gpcp`, `merra2` and `imerg` with their OPeNDAP endpoints and variables |
| `GET` | `/api/v1/variables` | Variables filtered by `grupo`, `fuente`, `frecuencia`, `solo_analizables` |
| `GET` | `/api/v1/regiones` | Predefined regions |
| `POST` | `/api/v1/regiones/calcular-bbox` | Bounding box from a set of points |
| `GET` | `/api/v1/opendap/consulta` | Indices and DAP4/DAP2 OPeNDAP URLs for a region |
| `POST` | `/api/v1/opendap/precargar` | Preload a regional cube into RAM in the background |
| `GET` | `/api/v1/descargas` | Preload status |
| `GET` | `/api/v1/series/{variable_id}` | Regional series, climatology, anomalies and quality report |
| `GET` | `/api/v1/tendencias/{variable_id}` | `calcular_tendencia` result (20 keys), OLS line and points |
| `GET` | `/api/v1/indicadores` | The 5 annual rainfall-extreme indicators |
| `GET`/`POST` | `/api/v1/escaner` | All variables of a region, ranked by verdict and \|SNR\| |
| `GET`/`POST` | `/api/v1/dos-caras` | Compares two regions or two variables |
| `GET` | `/api/v1/mapas/{variable_id}` | Per-pixel trend map (`pendiente_decada`, `p_t`, `p_mk`, `veredicto`) |
| `GET`/`DELETE` | `/api/v1/cache` | Inspect or clear the LRU cache |
| `GET` | `/demo/result` | Main Down to Earth analysis (P, T, SM, ET) |
| `GET` | `/demo/csv/{mensual\|anual}` | CSV download |

Each analysis takes `region=<id>` or `region=<slug>&oeste=..&sur=..&este=..&norte=..` (all four coordinates together, or none). Dates are `YYYY-MM`.

The full frontend reference is in [`../docs/api/FRONTEND_API.md`](../docs/api/FRONTEND_API.md), with [`openapi.json`](../docs/api/openapi.json) and real responses in [`../docs/api/ejemplos/`](../docs/api/ejemplos).

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `NASA_CORS_ORIGINS` | localhost and project domains | Allowed origins, comma-separated (`*` = all) |
| `EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD` | empty | NASA Earthdata Login credentials. Without them only synthetic data is available. |
| `NASA_CACHE_MEMORIA_MAX` | `128` | Maximum regional cubes in the LRU cache |
| `NASA_OPENDAP_WORKERS` | `6` | Concurrent threads for OPeNDAP slices |
| `NASA_OPENDAP_TIMEOUT` | `60` | HTTP timeout per OPeNDAP request, in seconds |
| `NASA_MAX_DESCARGAS` | `2` | Concurrent background preloads |
| `NASA_MAX_PIXELES` | `20000` | Pixel cap for the trend map in a synchronous request |
| `UVICORN_WORKERS` | `2` | Server processes (Docker) |
| `NASA_CATALOGO`, `NASA_REGIONES` | bundled YAML files | Paths to your own catalog and regions |

Never commit credentials.

## Run locally

### With Docker (recommended)

From the repository root:

```bash
cp .env.example .env     # fill in EARTHDATA_* for real data
docker compose up -d --build api
```

The API is at `http://127.0.0.1:8000`. To test without a public domain, set `API_DOMAIN=:80` in `.env` and start `caddy` too.

### With uv

Needs Python 3.15 (installed by `uv`) and the native HDF5, NetCDF, GEOS and PROJ libraries.

```bash
cd backend
uv sync
uv run python -m core.main servir --host 127.0.0.1 --port 8000 --reload
```

The first import can take about a minute. Check that it responds:

```bash
curl http://127.0.0.1:8000/api/v1/salud
```

On Windows, if `pyyaml` fails to build with Python 3.15, create the environment with Python 3.14.

## Tests

```bash
cd backend
uv run pytest -q
```

The suite covers the catalog and units, series, trends on synthetic series with a known slope, indicators on hand-made daily series, the scanner and the API. It writes nothing to disk.

## Deployment

The repository has everything needed for a Debian 12 server:

1. `sudo ./deploy/setup-debian12-docker.sh` installs Docker Engine and Compose.
2. `cp .env.example .env` and set `API_DOMAIN`, `NASA_CORS_ORIGINS` (with the frontend domain) and, for real data, `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD`.
3. `docker compose up -d --build`. **Caddy** gets a Let's Encrypt HTTPS certificate and proxies to the API (180 s timeouts for live queries).
4. Verify `https://<API_DOMAIN>/api/v1/salud`.

The GitHub Actions workflow (`.github/workflows/ci-cd.yml`) runs the tests, packages the Python project and smoke-tests the Docker image.

## Layout

```
backend/
├─ Dockerfile, entrypoint.sh, pyproject.toml, uv.lock
├─ src/core/
│  ├─ main.py             CLI (servir)
│  ├─ config.py           environment variables
│  ├─ api/                FastAPI app, schemas and routes (analisis, catalogo, datos)
│  ├─ motor/              catalogo, datos (OPeNDAP + cache), series, tendencias,
│  │                      indicadores, escaner, down_to_earth
│  ├─ servicios/          queries, background downloads, regions
│  └─ recursos/           catalogo.yaml and regiones.yaml
└─ tests/
```
