# Hybrid Secret Scanner - Frontend

Next.js application for editing code snippets and viewing scan results from backend APIs.

## Folder Highlights

- `src/app/page.tsx`: app entry route.
- `src/components/editor-client.tsx`: editor + scan mode UI + results rendering.
- `src/app/api/scan/route.ts`: proxy route forwarding requests to backend.

## Prerequisites

- Node.js 18+
- npm
- Backend API running (`backend/api_server.py`)

## Setup

```bash
cd frontend
npm install
```

## Development Commands

```bash
cd frontend
npm run dev
npm run lint
npm run build
npm run start
```

## Backend Connectivity

Frontend calls `POST /api/scan` (same origin).
That route proxies to backend `POST /scan`.

Default backend URL:
- `http://127.0.0.1:8000`

Override:
```bash
cd frontend
BACKEND_API_URL=http://localhost:8000 npm run dev
```

## Scan Modes in UI

- `Fast Scan`: regex + heuristic checks (quick response)
- `Full Scan`: regex + model inference via backend

If backend is started with `LLM_DRY_RUN=true`, Full Scan falls back and will not return real model reasoning.

## Local Full-Stack Run

Terminal 1 (backend):
```bash
cd backend
source .venv/bin/activate
LLM_DRY_RUN=true python api_server.py --host 127.0.0.1 --port 8000
```

Terminal 2 (frontend):
```bash
cd frontend
npm run dev
```
