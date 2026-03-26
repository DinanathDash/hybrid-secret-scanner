# Gemini Context: Hybrid Secret Scanner (March 23, 2026)

Use this as context when asking Gemini/Web assistants about this repo.

## What changed recently
- Introduced graceful CLI runtime handling (`Ctrl+C`) via `cli_runtime.py` and wired entrypoint scripts through `run_cli(...)`.
- Added line-buffered stdout/stderr normalization to reduce broken/mixed terminal rendering.
- Added optional dry-run mode for LLM-dependent scripts using env var `LLM_DRY_RUN=true`.
- Centralized runtime config in `src/config.py` (model/adapters/token limits/Ollama settings).
- Reorganized repo structure for clarity:
  - `scripts/` for utility scripts
  - `examples/` for demo scan targets
  - compatibility wrappers kept at repo root (`test_ai.py`, `make_valid.py`).
- Refined `.gitignore` to avoid committing virtual envs, local artifacts, generated datasets/checkpoints, logs, and secrets.
- Added tooling and quality baseline:
  - `pyproject.toml` for `pytest`, `ruff`, `black`, `mypy` config
  - `Makefile` task runner
  - `.pre-commit-config.yaml`
  - split dependency files: `requirements.txt`, `requirements-dev.txt`, `requirements-train.txt`
- Added smoke tests for entrypoints (`tests/test_entrypoints_smoke.py`).
- Added local convention directories:
  - `reports/` (scan outputs)
  - `artifacts/` (local ML/checkpoint artifacts)

## Current run patterns
- Main demo scan: `python main.py`
- LLM helper smoke (supports dry-run): `python scripts/test_ai.py`
- Dry-run mode (no model load): `LLM_DRY_RUN=true python main.py`

## Important constraints and context
- Python environment currently used is 3.14 in local venv (`mlx_env`).
- Some pinned runtime libs may lag Python 3.14 wheels (e.g., older `pydantic` pins can require source build).
- Lint passes with Ruff; smoke tests pass.

## If asking Gemini for help
Ask for suggestions that are compatible with:
1. Local-first ML workflow (MLX/Ollama)
2. Python 3.14 compatibility
3. Existing structure (`src/`, `scripts/`, `ml_pipeline/`, `examples/`, `reports/`, `artifacts/`)
4. Non-breaking changes to current entrypoints and Make targets
