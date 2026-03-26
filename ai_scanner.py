"""Compatibility shim for older imports.

Prefer importing `HybridAIScanner` from `src.llm_engine` directly.
"""

from src.llm_engine import HybridAIScanner

__all__ = ["HybridAIScanner"]
