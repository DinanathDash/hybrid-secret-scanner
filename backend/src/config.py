from __future__ import annotations

import os


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


LLM_MODEL_ID = os.getenv("LLM_MODEL_ID", "mlx-community/Meta-Llama-3-8B-Instruct-4bit")
LLM_ADAPTER_PATH = os.getenv("LLM_ADAPTER_PATH", "./adapters")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "500"))
LLM_EFFECTIVE_MAX_TOKENS = int(os.getenv("LLM_EFFECTIVE_MAX_TOKENS", "120"))
LLM_DRY_RUN = _as_bool(os.getenv("LLM_DRY_RUN"), default=False)
LLM_WARMUP_ON_START = _as_bool(os.getenv("LLM_WARMUP_ON_START"), default=True)
LLM_CACHE_ENABLED = _as_bool(os.getenv("LLM_CACHE_ENABLED"), default=True)
LLM_CACHE_MAX_ENTRIES = int(os.getenv("LLM_CACHE_MAX_ENTRIES", "512"))

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.1"))
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "15"))
