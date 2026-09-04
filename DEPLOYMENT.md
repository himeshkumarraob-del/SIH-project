# ThermalWatch — Deployment Guide

Two separately hosted pieces:

| Piece    | Stack             | Host        | Code root   |
|----------|-------------------|-------------|-------------|
| Frontend | React 18 + Vite   | **Vercel**  | `web/`      |
| Backend  | FastAPI (uvicorn) | any host that runs Python + serves a process (Render, Fly.io, Railway, a VM with Nginx/systemd, etc.) | repo root (`backend/main.py`) |

No Docker files are provided — run natively (below).

---

## 1. Frontend → Vercel

### 1a. Vercel project settings (set manually in the dashboard — do NOT commit project settings)

- **Framework Preset:** `Vite`
- **Root Directory:** `web`  *(the Vite app lives in the monorepo subfolder)*
- **Build Command:** `npm run build`  (runs `tsc -b && vite build`)
- **Output Directory:** `dist`
- **Node:** 20.x or newer
- **Install Command:** `npm install` (default)

### 1b. SPA routing (already configured)

`web/vercel.json` rewrites every non-static, non-`/api` path to `/index.html`, so
all React Router routes (`/`, `/map`, `/alerts`, `/events`, `/analytics`,
`/system`) work on direct URL entry / refresh:

```json
{ "rewrites": [ { "source": "/((?!api/|assets/|vite.svg).*)", "destination": "/index.html" } ] }
```

### 1c. Frontend → backend URL (env var)

The app reads **`VITE_API_BASE_URL`** at build time (inlined by Vite):

- **Not set** → calls **same-origin `/api/v1`** (dev: the Vite proxy forwards to
  `localhost:8000`). Usable in production only if you also proxy `/api` on the
  frontend host.
- **Set** → calls that absolute backend URL directly, e.g.
  `VITE_API_BASE_URL=https://thermalwatch-api.example.com/api/v1`.

**Recommended production setup:** frontend and backend on separate hosts ⇒ set
`VITE_API_BASE_URL` to the backend's public URL and configure CORS on the
backend (see §2c).

Type declarations for env vars: `web/src/vite-env.d.ts`.
Copy the reference: `web/.env.example` (documentation only — set real values in
the Vercel dashboard: **Settings → Environment Variables**; a Redeploy is
required after changing a build-time variable).

---

## 2. Backend → separate host

### 2a. Runtime files & startup

- Python 3.11+; install: `pip install -r requirements.txt`
  (only pandas, PyYAML, python-dotenv, FastAPI, uvicorn, pydantic, httpx are
  needed to *serve the API*; the rest are used by the pipeline scripts).
- Run **from the repository root** so relative data paths resolve:
  `uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 2`
  (systemd unit / process manager recommended).
- Health/readiness: `GET /api/v1/health` → `200` only when data is loaded,
  `503` when it is not. Use it for load-balancer/orchestrator checks.

### 2b. Data & model files (REQUIRED — gitignored on purpose)

`data/processed/*.csv` (the 1,792-cluster intelligence CSVs, alert snapshot)
and `models/*` are **not in Git** (`.gitignore`) and must exist on the backend
host. Two options:

1. **Recommended:** run the pipeline once on the host
   (`python scripts/run_full_pipeline.py`; uses `FIRMS_MAP_KEY`), or
2. copy the CSVs from a machine that already ran it into `data/processed/`.

The API never fabricates data: with no dataset it logs an error at startup and
`/api/v1/health` reports `503`. `data/processed/` must also be **writable**
(alert acknowledge/resolve state is persisted to `thermal_alerts.csv`).

Model files are only used by the *classification/satellite* scripts — the API
serves pre-computed results, so an API-only deployment does not need
`models/*.joblib`/`*.pth`. CSVs are required; models are optional for serving.

### 2c. CORS (env var)

Set **`CORS_ORIGINS`** to your Vercel frontend origin:

```
CORS_ORIGINS=https://thermalwatch.vercel.app
```

(comma-separate multiple origins; unset ⇒ localhost-only dev default).
CORS only matters when the browser calls the API **cross-origin**, i.e. when
`VITE_API_BASE_URL` points at a different host than the frontend.

### 2d. Backend env file

Copy `ai-engine/.env.example` → `.env` on the host and set:

| Var | Required? | Purpose |
|---|---|---|
| `FIRMS_MAP_KEY` | only if running the pipeline | NASA FIRMS ingestion |
| `CORS_ORIGINS` | production with cross-origin UI | allowed browser origins |
| `STUDY_AREA_*` | no | optional bbox overrides |

`.env` is gitignored — secrets never enter the repository.

---

## 3. Reference architecture

```
Browser ──► Vercel (web/dist static SPA, vercel.json SPA rewrite)
              │
              │ VITE_API_BASE_URL=https://api.… (cross-origin)
              ▼
           FastAPI (uvicorn)  ── reads data/processed/*.csv
              │                 writes thermal_alerts state
              └── /api/v1/health = readiness probe
```

If you prefer **no CORS** (same-origin), add an explicit Vercel rewrite from
`/api/:path*` to your backend and keep `VITE_API_BASE_URL` unset — but Vercel
rewrite destinations are literal, so that file must be updated when the backend
host changes.

---

## 4. Secrets & Git hygiene

- Real `.env` files are ignored (`.gitignore`: `.env`, `.env.*`, `*.key`).
- Only templates with placeholders are committed: `.env.example` (backend) and
  `web/.env.example` (frontend).
- `data/`, `models/`, `web/dist/`, `web/node_modules/` stay out of Git.
- Nothing above is deployed, committed, or pushed.
