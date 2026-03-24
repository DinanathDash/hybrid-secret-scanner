"""Shared helpers for clean CLI behavior across project scripts."""

from __future__ import annotations

import sys
from collections.abc import Callable


def normalize_terminal_streams() -> None:
    """Prefer line-buffered output so logs don't appear jammed together."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(line_buffering=True)


def run_cli(main_func: Callable[[], None]) -> int:
    """Run a CLI entrypoint with graceful Ctrl+C handling."""
    normalize_terminal_streams()
    try:
        main_func()
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting gracefully.", flush=True)
        return 130
