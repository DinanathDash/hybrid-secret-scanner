PYTHON ?= python3

.PHONY: help install install-dev install-train precommit-install test smoke lint format typecheck run run-test-ai split-valid prep-mlx train-mlx clean

help:
	@echo "Targets:"
	@echo "  install       Install runtime dependencies"
	@echo "  install-dev   Install runtime + dev dependencies"
	@echo "  install-train Install training dependencies"
	@echo "  precommit-install Install pre-commit hooks"
	@echo "  test          Run unit tests"
	@echo "  smoke         Run entrypoint smoke tests"
	@echo "  lint          Run Ruff lint checks"
	@echo "  format        Run Ruff format + Black"
	@echo "  typecheck     Run mypy"
	@echo "  run           Run main scanner demo"
	@echo "  run-test-ai   Run LLM smoke helper"
	@echo "  split-valid   Split MLX train/valid files"
	@echo "  prep-mlx      Convert dataset for MLX"
	@echo "  train-mlx     Run MLX LoRA training wrapper"
	@echo "  clean         Remove common local caches"

install:
	$(PYTHON) -m pip install -r requirements.txt

install-dev:
	$(PYTHON) -m pip install -r requirements-dev.txt

install-train:
	$(PYTHON) -m pip install -r requirements-train.txt

precommit-install:
	$(PYTHON) -m pre_commit install

test:
	$(PYTHON) -m pytest tests

smoke:
	$(PYTHON) -m pytest tests/test_entrypoints_smoke.py

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m black .

typecheck:
	$(PYTHON) -m mypy src

run:
	$(PYTHON) main.py

run-test-ai:
	$(PYTHON) scripts/test_ai.py

split-valid:
	$(PYTHON) scripts/make_valid.py

prep-mlx:
	$(PYTHON) ml_pipeline/prep_mlx_data.py

train-mlx:
	$(PYTHON) ml_pipeline/mac_train_qlora.py

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
