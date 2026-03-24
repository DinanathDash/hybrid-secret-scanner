from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run_entrypoint(script: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["LLM_DRY_RUN"] = "true"
    return subprocess.run(
        [sys.executable, script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )


def test_main_entrypoint_smoke() -> None:
    result = _run_entrypoint("main.py")
    assert result.returncode == 0, result.stderr
    assert "Starting Hybrid Secret Scanner Pipeline" in result.stdout


def test_test_ai_entrypoint_smoke() -> None:
    result = _run_entrypoint("scripts/test_ai.py")
    assert result.returncode == 0, result.stderr
    assert "LLM_DRY_RUN is enabled" in result.stdout


def test_root_wrapper_test_ai_entrypoint_smoke() -> None:
    result = _run_entrypoint("test_ai.py")
    assert result.returncode == 0, result.stderr
    assert "LLM_DRY_RUN is enabled" in result.stdout
