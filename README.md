# Hybrid Secret Scanner

Hybrid Secret Scanner is a full-stack project for detecting hardcoded secrets.

- `backend/` runs regex detection and optional model inference.
- `frontend/` provides an interactive editor UI and result panel.

## Repository Layout

- `backend/`: Python scanner engine, API server, tests, ML/training helpers.
- `frontend/`: Next.js app (editor + scan results).
- `backend/examples/`: sample snippets for scanner testing.
- `backend/reports/`: local scan report outputs (git-ignored).
- `backend/artifacts/`: local model/training artifacts (git-ignored).

## Prerequisites

- Python 3.10+
- Node.js 18+
- npm

## Quick Start (End-to-End)

1. Start backend API
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
LLM_DRY_RUN=true python api_server.py --host 127.0.0.1 --port 8000
```

2. Start frontend
```bash
cd frontend
npm install
npm run dev
```

3. Open app
- `http://localhost:3000` (or the URL shown by `npm run dev`)

## Scan Modes

- `fast`: regex + heuristic verdicts (lower latency)
- `full`: regex + LLM inference (falls back when dry-run is enabled)

Frontend calls `POST /api/scan` which proxies to backend `POST /scan`.

## Common Commands

### Backend
```bash
cd backend
source .venv/bin/activate

# API server
python api_server.py --host 127.0.0.1 --port 8000

# CLI pipeline scan current folder
python main.py .

# tests/lint/typecheck via Makefile
make test
make lint
make typecheck
```

### Frontend
```bash
cd frontend
npm install
npm run dev
npm run lint
npm run build
npm run start
```

## Backend API

- `GET /health`
- `POST /scan`

Example:
```bash
curl -X POST http://127.0.0.1:8000/scan \
  -H 'Content-Type: application/json' \
  -d '{
    "code":"const key=\"AKIA1A2B3C4D5E6F7G8H\";",
    "filename":"snippet.ts",
    "scan_mode":"fast"
  }'
```

## Recommended Test Input

Use:
- `backend/examples/comprehensive_secret_test_corpus.txt`

It contains synthetic low/medium/high-risk examples across multiple secret categories.
