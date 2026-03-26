# Hybrid Secret Scanner - Backend

Python backend for secret detection.

It provides:
- CLI pipeline scanning (`main.py`)
- HTTP API for frontend integration (`api_server.py`)
- Regex candidate extraction + optional LLM validation

## Folder Highlights

- `src/scanner.py`: regex scanning and snippet scan modes.
- `src/fast_scanner.py`: signature-based fast scan engine (traditional heuristic mode).
- `src/llm_engine.py`: model inference + dry-run behavior.
- `api_server.py`: HTTP server (`/health`, `/scan`).
- `examples/`: scanner input examples.
- `tests/`: backend tests.
- `reports/`: local output reports.
- `artifacts/`: local model/training artifacts.

## Requirements

- Python 3.10+
- macOS/Apple Silicon recommended for MLX model path

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If your environment blocks global/user installs (PEP 668), always use `.venv`.

## Run Commands

### Start API Server

```bash
cd backend
source .venv/bin/activate
LLM_DRY_RUN=true python api_server.py --host 127.0.0.1 --port 8000
```

### Run CLI Scanner

```bash
cd backend
source .venv/bin/activate
python main.py .
```

### Scan a Specific Path

```bash
cd backend
source .venv/bin/activate
python main.py /absolute/or/relative/path
```

## API Endpoints

- `GET /health`
- `POST /scan`

### `POST /scan` Request Body

```json
{
  "code": "const token = \"ghp_abc...\";",
  "filename": "example.ts",
  "scan_mode": "fast"
}
```

`scan_mode` values:
- `fast`: regex + heuristic verdicts (lower latency)
- `full`: regex + LLM model inference

If `LLM_DRY_RUN=true`, `full` mode falls back to heuristic behavior.
If model runtime is unavailable (for example missing `mlx_lm`), `full` mode also falls back and the API response includes fallback metadata.

### cURL Example

```bash
curl -X POST http://127.0.0.1:8000/scan \
  -H 'Content-Type: application/json' \
  -d '{
    "code":"const x = \"sk_live_abc123...\";",
    "filename":"snippet.ts",
    "scan_mode":"full"
  }'
```

## Development Commands

```bash
cd backend
source .venv/bin/activate

# Install variants
make install
make install-dev
make install-train

# Quality checks
make lint
make format
make typecheck

# Tests
make test
make smoke

# Pipeline helpers
make run
make run-test-ai
make split-valid
make prep-mlx
make train-mlx
```

## Test Corpus

Use this file to test many secret patterns quickly:
- `examples/comprehensive_secret_test_corpus.txt`

## Notes

- `requirements.txt` includes ML/runtime dependencies.
- If model dependency resolution fails on your machine, run API with `LLM_DRY_RUN=true` for UI and integration testing.
