# Moody Trends

> The two faces of rain: see, with NASA data, how rainfall, temperature, soil moisture and evapotranspiration change in a region, and whether those changes are statistically real.

Built for the **NASA Space Apps Challenge 2026**, *Down to Earth* challenge.

Moody Trends lets you pick a region on a 3D globe, choose a period and a few variables, and get trends with their statistical significance. You can use it by hand or by voice. It has a guided mode for first-time users and an assistant (Moody) that explains any step.

---

## What it does

- **3D globe** to pick a predefined region or draw your own. The globe turns to the region as you type or speak.
- **Voice**: dictate the region, period and variables. Transcription and interpretation use Google Gemini.
- **Two ways in**: guided (short questions, examples, AI-suggested variables) or expert (the tool directly).
- **Moody**: a floating Gemini chatbot that knows the flow, the results and the catalog, with default questions and voice input.
- **Analysis** of rainfall, air temperature, soil moisture and evapotranspiration, with trend per decade, confidence interval, verdict and a joint reading of anomalies (rainfall with soil moisture, temperature with soil moisture, rainfall with evapotranspiration).
- **Full-screen 3D view** of the analysis (series carpet, relations and per-pixel trend map), plus Recharts charts in the side panel.
- **CSV download**, monthly and annual.
- English and Spanish interface, responsive, light and dark themes.

## How it works

```
 Browser ──► frontend (Next.js, Vercel) ──► backend (FastAPI, Docker + Caddy)
                │                                   │
                │ /api/* routes                     │ OPeNDAP in RAM
                ▼                                   ▼
          Google Gemini                 NASA Earthdata (GPCP, MERRA-2, GPM IMERG)
```

- **The frontend does no science.** Variables, regions, periods, trends, maps and CSV all come from the backend.
- **Gemini** runs only on the frontend's server side (Next.js `/api/*` routes) for voice, region lookup, the guided flow and chat.
- **NASA data is never written to disk.** The backend queries OPeNDAP, slices the requested region and keeps the cube in an in-memory LRU cache.
- **Statistical method**: OLS with HAC (Newey-West) correction, Holm correction for multiple comparisons, Mann-Kendall and Sen's slope as cross-checks.

## Repository layout

| Folder | Contents |
|---|---|
| [`frontend/`](./frontend) | Next.js 16 app with React 19, Tailwind 4, shadcn/ui, react-three-fiber, Recharts and Google GenAI. See its [README](./frontend/README.md). |
| [`backend/`](./backend) | FastAPI API and statistical engine. See its [README](./backend/README.md). |
| [`docs/api/`](./docs/api) | Integration guide [`FRONTEND_API.md`](./docs/api/FRONTEND_API.md), `openapi.json` and real example responses. |
| [`deploy/`](./deploy) | `Caddyfile` (automatic HTTPS) and a Docker install script for Debian 12. |
| [`.github/workflows/`](./.github/workflows) | CI/CD: tests, packaging and Docker smoke tests. |
| `docker-compose.yml` | Runs the API and Caddy. |
| `.env.example` | Backend variables for Docker (copy to `.env`). |

## NASA data

| Source | Variables | Coverage |
|---|---|---|
| GPCP monthly v3.3 | Precipitation | 1983 to present, 0.5° |
| MERRA-2 v5.12.4 | Precipitation, 2 m air temperature, water vapor | 1980 to present, 0.5° × 0.625° |
| GPM IMERG Final v07 | Monthly and daily precipitation, extreme indicators (CDD, R20mm, wet days, PRCPTOT, SDII) | 1998 to present, 0.1° |

With **NASA Earthdata** credentials the backend queries real data. Without them it serves **synthetic** data and the frontend shows a notice.

## Quick start (local)

You need Node 20 or newer with pnpm, and either Docker or Python with `uv` for the backend.

**1. Backend** (port 8000):

```bash
cp .env.example .env
docker compose up -d --build api
```

Without Docker, from `backend/`: `uv sync`, then `uv run python -m core.main servir --host 127.0.0.1 --port 8000 --reload`. More detail in the [backend README](./backend/README.md).

**2. Frontend** (port 3000):

```bash
cd frontend
cp .env.example .env.local   # fill in GEMINI_API_KEY
pnpm install
pnpm dev
```

Open <http://localhost:3000>. Check the backend at <http://localhost:8000/api/v1/salud> and its docs at <http://localhost:8000/docs>.

## Deployment

| Part | Where | What to configure |
|---|---|---|
| Frontend | Vercel, with **Root Directory** set to `frontend` | `GEMINI_API_KEY` and `NEXT_PUBLIC_BACKEND_URL` (public https URL of the backend). Redeploy after changing the URL, since it is inlined at build time. |
| Backend | A server with Docker (`docker compose up -d --build`); Caddy provides TLS | `NASA_CORS_ORIGINS` with the frontend domain. Optional: `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD`. |

Full steps are in each part's README.

## Environment variables

| Variable | Where | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | frontend (server) | Voice, chat, guided flow and region lookup |
| `NEXT_PUBLIC_BACKEND_URL` | frontend | Backend URL |
| `NASA_CORS_ORIGINS` | backend | Allowed frontend origins |
| `EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD` | backend | Real NASA data |
| `NASA_CACHE_MEMORIA_MAX`, `NASA_OPENDAP_WORKERS`, `NASA_OPENDAP_TIMEOUT`, `NASA_MAX_DESCARGAS`, `NASA_MAX_PIXELES`, `UVICORN_WORKERS` | backend | Performance and limits |

Never commit `.env` or `.env.local`; only the `.env.example` files belong in the repository.

## Tests

```bash
cd backend && uv run pytest -q     # engine and API
cd frontend && pnpm lint           # ESLint
cd frontend && pnpm build          # production build
```

## Credits

Data: NASA Earthdata (GES DISC), GPCP, MERRA-2 and GPM IMERG products. Built for the NASA Space Apps Challenge 2026.
