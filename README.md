# BikeSim

A cycling simulation platform that models real-time bike physics using a backend physics engine, with a live telemetry dashboard.

## Architecture

```
┌─────────────┐     WebSocket      ┌──────────────┐     SQL/REST     ┌────────────┐
│   Frontend   │ ◄────────────────► │   Backend    │ ◄──────────────► │  Supabase  │
│  React/Vite  │     REST API       │   FastAPI    │                  │  Postgres  │
│  Recharts    │                    │   Physics    │                  │  Storage   │
└─────────────┘                    └──────────────┘                  └────────────┘
```

- **Backend** (`backend/`): FastAPI server with a physics engine that simulates cycling in real time. Runs as a WebSocket streaming service.
- **Frontend** (`frontend/`): React SPA with live telemetry charts, route visualization, and simulation controls.
- **Database**: Supabase (PostgreSQL) for routes, riders, and persisted simulations.
- **Storage**: Supabase Storage for GPX files and simulation telemetry/graphs.

## Prerequisites

- Python 3.12+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- A Supabase project ([supabase.com](https://supabase.com))

## Setup

### 1. Clone and install

```bash
git clone https://github.com/kalebgrove/bikesim
cd bikesim

# Backend
uv sync

# Frontend
cd frontend
npm install
cd ..
```

### 2. Environment variables

Create a `.env` file in the project root:

```env
SUPABASE_URL
SUPABASE_KEY
FRONTEND_ORIGINS
```

> **Never commit `.env` to version control.** The service role key has full database access.

### 3. Database migration

Run this SQL in the Supabase SQL editor:

```sql
create table if not exists public.simulations (
  id          uuid primary key default gen_random_uuid(),
  sim_id      text unique not null,
  route_id    bigint,
  route_name  text,
  rider_ref   text,
  status      text not null,
  stop_reason text,
  config      jsonb not null,
  summary     jsonb,
  file_path   text,
  created_at   timestamptz not null default now(),
  completed_at timestamptz
);

alter table public.simulations enable row level security;
```

The `simulations` storage bucket is created automatically on first use.

### 4. Run

**Backend** (from project root):

```bash
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend** (from `frontend/`):

```bash
npm run dev
```

Frontend runs on `http://localhost:8443` by default.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/routes` | List all routes |
| `POST` | `/routes` | Upload a GPX file (multipart) |
| `GET` | `/routes/{id}` | Get route metadata |
| `GET` | `/routes/{id}/points` | Get route geometry for visualization |
| `DELETE` | `/routes/{id}` | Delete a route and its GPX file |
| `GET` | `/riders` | List all riders |
| `POST` | `/riders` | Create a rider profile |
| `PUT` | `/riders/{name}` | Update a rider profile |
| `DELETE` | `/riders/{name}` | Delete a rider profile |
| `POST` | `/simulations` | Create and start a simulation |
| `GET` | `/simulations/{id}` | Get simulation state (live or persisted) |
| `DELETE` | `/simulations/{id}` | Stop and delete a simulation |
| `WS` | `/simulations/{id}/stream` | WebSocket telemetry stream |

### WebSocket protocol

**Client → Server:**
```json
{ "type": "pause" }
{ "type": "resume" }
{ "type": "stop", "reason": "Optional reason" }
{ "type": "restart" }
```

**Server → Client:**
```json
{ "type": "status", "data": { "simId": "...", "status": "running" } }
{ "type": "tick", "data": { "t": 1.0, "dist": 0.05, "speed": 8.2, ... } }
{ "type": "summary", "data": { "totalTimeS": 3600, "avgSpeedKph": 28.5, ... } }
{ "type": "stopped", "data": { "reason": "Stopped by user" } }
```

## Project Structure

```
bikesim/
├── backend/
│   ├── main.py              # FastAPI app + CORS
│   ├── db.py                # Supabase client
│   ├── schemas.py           # Pydantic models (API contract)
│   ├── sim_manager.py       # In-memory simulation sessions
│   ├── persistence.py       # Save/load simulations from Supabase
│   ├── graphs.py            # Matplotlib chart rendering
│   ├── engine/
│   │   ├── physics.py       # Force model, integration, cornering
│   │   ├── route.py         # GPX parsing, slope, heading, smoothing
│   │   ├── rider.py         # Rider + bike parameters
│   │   └── wind.py          # Wind vector + apparent wind
│   ├── routes/
│   │   ├── routes.py        # Route CRUD + GPX upload
│   │   ├── riders.py        # Rider CRUD
│   │   └── simulations.py   # Simulation lifecycle + WebSocket
│   └── migrations/
│       └── 001_simulations.sql
├── frontend/
│   ├── src/
│   │   ├── App.tsx           # Root + route sync
│   │   ├── lib/
│   │   │   ├── api.ts        # REST/WS client
│   │   │   ├── store.ts      # Client-side state
│   │   │   ├── types.ts      # TypeScript interfaces
│   │   │   └── simEngineContext.ts
│   │   ├── hooks/
│   │   │   ├── useSimEngine.ts   # WebSocket lifecycle
│   │   │   └── useStore.ts       # useSyncExternalStore hooks
│   │   ├── components/
│   │   │   ├── RouteSvg.tsx       # SVG route map
│   │   │   ├── ElevationProfile.tsx
│   │   │   └── TelemetryValue.tsx
│   │   └── pages/
│   │       ├── Dashboard.tsx
│   │       ├── LiveSim.tsx        # Real-time simulation view
│   │       ├── Results.tsx        # Post-run analysis
│   │       ├── GPXUpload.tsx
│   │       ├── RouteDetail.tsx
│   │       └── SimConfig.tsx
│   └── package.json
├── pyproject.toml
└── .env                      # (gitignored)
```

## Physics Model

The simulation uses Euler integration with 0.1s substeps:

- **Gravity**: `m * g * sin(atan(grade/100))`
- **Rolling resistance**: `m * g * Crr * cos(theta)`
- **Aerodynamic drag**: `0.5 * CdA * rho * v_apparent^2`
- **Drive force**: `min(f_max, target_power / velocity)`
- **Cornering limit**: `sqrt(mu * g * cos(theta) * R)` using GPS-derived curvature

Parameters are configurable per simulation (rider mass, FTP, CdA, Crr, wind, power target).

## Deployment

### Vercel (frontend) + Railway (backend)

1. Push to GitHub
2. Import frontend repo into Vercel — auto-detects Vite
3. Import backend repo into Railway — set environment variables
4. Set `VITE_API_BASE` in Vercel to your Railway backend URL
5. Set `FRONTEND_ORIGINS` in Railway to your Vercel frontend URL

### Single container (Docker)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY backend/ ./backend/
COPY frontend/dist/ ./frontend/dist/
RUN pip install uvicorn fastapi supabase python-dotenv python-multipart requests matplotlib
ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build frontend first (`npm run build` in `frontend/`), then serve the static files from FastAPI or add Nginx.
