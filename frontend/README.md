# Moody Trends — frontend

Next.js 16 (App Router), React 19, Tailwind 4, shadcn/ui, react-three-fiber, Recharts and the
Google GenAI SDK. The data (variables, regions, periods, trends, maps, CSV) comes from the
FastAPI backend in `../backend`; Gemini powers voice, region lookup, the guided flow and Moody.

## Run locally

```bash
cp .env.example .env.local   # then fill GEMINI_API_KEY
pnpm install
pnpm dev                     # http://localhost:3000
```

The backend must be running (default `http://localhost:8000`, see `../docs/api/FRONTEND_API.md`).
Without it the app shows a "no connection" notice with a retry button.

## Deploy on Vercel

1. Import the repository and set **Root Directory** to `frontend`.
2. Framework preset: Next.js. Install: `pnpm install`. Build: `pnpm build` (uses `next build --webpack`).
3. Environment variables (Production and Preview):
   - `GEMINI_API_KEY` — server-side only.
   - `NEXT_PUBLIC_BACKEND_URL` — the **public HTTPS URL** of the backend, e.g. `https://api.moody-trends.earth`.
     `NEXT_PUBLIC_*` values are inlined at build time, so redeploy after changing it.
4. On the backend, make sure `NASA_CORS_ORIGINS` includes the Vercel domain (and your custom domain).

## Scripts

| Script | What it does |
|---|---|
| `pnpm dev` | development server (webpack) |
| `pnpm build` | production build |
| `pnpm start` | serve the production build |
| `pnpm lint` | ESLint |
