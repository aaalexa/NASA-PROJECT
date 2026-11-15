# Moody Trends: frontend

Web interface for Moody Trends. Next.js 16 (App Router), React 19, Tailwind 4, shadcn/ui (base-nova on `@base-ui/react`), react-three-fiber, Recharts and Google GenAI.

Data (variables, regions, periods, trends, maps and CSV) comes from the FastAPI backend in [`../backend`](../backend). Gemini powers voice, region lookup, the guided flow and the Moody chat.

## Requirements

- Node 20 or newer
- pnpm 11
- A Google Gemini API key (`GEMINI_API_KEY`)
- The backend running (default `http://localhost:8000`, see [`../backend/README.md`](../backend/README.md))

## Run locally

```bash
cp .env.example .env.local   # fill in GEMINI_API_KEY
pnpm install
pnpm dev                     # http://localhost:3000
```

If the backend does not respond, the app shows a "no connection" notice with a retry button.

## Environment variables

| Variable | Scope | Description |
|---|---|---|
| `GEMINI_API_KEY` | Server only | Google Gemini key. Used by the `/api/*` routes and never sent to the browser. |
| `NEXT_PUBLIC_BACKEND_URL` | Browser | Backend URL. Defaults to `http://localhost:8000`. Inlined at build time, so redeploy after changing it. |

Only `.env.example` is committed. `.env.local` is git-ignored.

## Scripts

| Script | What it does |
|---|---|
| `pnpm dev` | Development server (webpack) |
| `pnpm build` | Production build (`next build --webpack`) |
| `pnpm start` | Serve the production build |
| `pnpm lint` | ESLint |

## Project layout

```
src/
├─ app/
│  ├─ page.tsx            main flow: welcome, guided and expert modes
│  ├─ layout.tsx          providers (theme, language, backend, tooltips)
│  ├─ globals.css         palette and light/dark theme
│  └─ api/                server routes that call Gemini
│     ├─ parse-voice/     interprets dictated region, period and variables
│     ├─ transcribe/      audio to text
│     ├─ guide/           questions and suggestions for the guided flow
│     └─ chat/            Moody chat
├─ components/
│  ├─ onboarding/         "I'm new / I have experience" modal
│  ├─ guided/             guided flow with examples
│  ├─ nasa/               steps: region, period, variables and results
│  ├─ globe/              react-globe.gl globe (main) and Cobe globe
│  ├─ analysis/           3D drawer: series carpet, relations and map
│  ├─ charts/             Recharts charts
│  ├─ chat/               Moody, the floating chatbot
│  ├─ hud/                voice control
│  └─ ui/                 shadcn components
├─ context/               BackendContext: backend state and catalog
├─ hooks/                 useAnalysisData, useVoiceInput, useSpeak
├─ lib/                   api.ts (backend client), catalog, regionMatch, demos…
└─ messages/              UI text in es.json and en.json
```

### Backend client

All data access goes through [`src/lib/api.ts`](./src/lib/api.ts). It provides typed errors (`ApiError`, `BackendOfflineError`), `YYYY-MM` dates, and the conversion between globe points and the `[west, south, east, north]` bounding box. `BackendContext` loads the catalog, regions and available period on startup and picks the data mode: `descargar` (live NASA data) when the backend has NASA credentials, `sintetico` (synthetic) when it does not. You can force it with `NEXT_PUBLIC_DATA_MODE`.

### Analysis

`useAnalysisData` fetches the main result and the per-variable trends once and shares them between the results panel and the drawer. The 3D drawer opens from the left with the "open analysis in 3D" button and never opens on its own. The WebGL scenes wait for the opening animation to finish so it stays smooth.

### Voice and Gemini

The browser records with `MediaRecorder`, detects silence and sends the audio to `/api/transcribe`. `/api/parse-voice` first looks for a match among the backend's regions; if there is none, it asks Gemini for a triangle, validates it and turns it into a bounding box. Gemini calls try a chain of models with a per-attempt timeout and schema-constrained JSON output.

## Design

- Rounded corners everywhere, no all-caps text, Helvetica typography.
- Only the project palette: `#780000`, `#C1121F`, white, `#003049`, `#669BBC` and `#9c914f`. The 3D scenes always use a `#003049` background so contrast holds in light and dark themes.
- shadcn components only, nothing native to the browser.
- Responsive on phone, tablet and desktop.

## Deploy on Vercel

1. Import the repository and set **Root Directory** to `frontend`.
2. Framework: Next.js. Install: `pnpm install`. Build: `pnpm build`.
3. Environment variables (Production and Preview):
   - `GEMINI_API_KEY`
   - `NEXT_PUBLIC_BACKEND_URL`: the **public https** URL of the backend, e.g. `https://api.moody-trends.earth`.
4. On the backend, `NASA_CORS_ORIGINS` must include the Vercel domain (and your custom domain, if any).
5. Redeploy after changing `NEXT_PUBLIC_BACKEND_URL`.

### Common problems

| Symptom | Likely cause |
|---|---|
| `ERR_CONNECTION_REFUSED` in the console | `NEXT_PUBLIC_BACKEND_URL` points to a stopped backend, or to `localhost` in production |
| CORS error | The frontend domain is missing from the backend's `NASA_CORS_ORIGINS` |
| Mixed content blocked | The site is https but the backend is http: the backend needs HTTPS |
| Voice or chat do not respond | `GEMINI_API_KEY` is missing or the Gemini quota is exhausted |
| "Illustrative data" notice | The backend has no NASA Earthdata credentials and is serving synthetic data |

## Related documentation

- [API integration guide](../docs/api/FRONTEND_API.md) and [`openapi.json`](../docs/api/openapi.json)
- [Backend README](../backend/README.md)
- [Repository README](../README.md)
