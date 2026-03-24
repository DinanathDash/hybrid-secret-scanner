# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## [0.1.0] - 2026-03-23
### Added
- `cli_runtime.py` for graceful CLI shutdown and cleaner terminal stream behavior.
- `src/config.py` for centralized environment-driven configuration.
- `pyproject.toml` with `pytest`, `ruff`, `black`, and `mypy` settings.
- `.pre-commit-config.yaml` for local quality hooks.
- `Makefile` for common dev/training tasks.
- `requirements-dev.txt` and `requirements-train.txt` dependency split.
- `.env.example` with documented runtime knobs.
- `tests/test_entrypoints_smoke.py` for entrypoint-level smoke checks.
- `reports/` and `artifacts/` conventions with readmes.
- `docs/GEMINI_CONTEXT.md` to share project context with external assistants.

### Changed
- Reorganized helper/demo files into `scripts/` and `examples/`.
- Updated `main.py` to scan `examples/dummy_app.py`.
- Updated multiple CLI scripts to use common graceful runtime wrapper.
- Refined `.gitignore` to better exclude generated or local-only files.
- Updated `README.md` with new structure, tasks, and environment setup.

### Fixed
- Removed duplicate import in `src/scanner.py`.
- Resolved project lint issues (imports, formatting, typing modernizations where applied).
