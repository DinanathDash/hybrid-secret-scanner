from __future__ import annotations

import json
import logging
import os
import warnings
from typing import Any

from .config import LLM_ADAPTER_PATH, LLM_DRY_RUN, LLM_MAX_TOKENS, LLM_MODEL_ID
from .models import CandidateSecret, LLMResponse

CONFIRMED_SECRET_PRIORITIES = {"CRITICAL", "HIGH", "MEDIUM"}
_SCANNER: HybridAIScanner | None = None


class HybridAIScanner:
    """Local MLX-backed validator for regex candidate secrets."""

    def __init__(self) -> None:
        # Keep model-download output quiet in normal terminals.
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        warnings.filterwarnings(
            "ignore",
            message=r"mx\.metal\.device_info is deprecated.*",
            category=DeprecationWarning,
        )
        self.dry_run = LLM_DRY_RUN
        self.model = None
        self.tokenizer = None

        if self.dry_run:
            return

        from mlx_lm import load

        self.model, self.tokenizer = load(
            LLM_MODEL_ID,
            adapter_path=LLM_ADAPTER_PATH,
        )

    def analyze_candidate(self, candidate: CandidateSecret) -> LLMResponse:
        """Run deterministic MLX inference and parse structured verdict safely."""
        if self.dry_run:
            return LLMResponse(
                is_genuine_secret=False,
                confidence_score=0.0,
                remediation_priority="SAFE",
                reasoning="Dry-run mode enabled. LLM inference skipped.",
            )

        from mlx_lm import generate

        prompt = _build_prompt(candidate)

        raw_response = generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=LLM_MAX_TOKENS,
        )
        clean_json = raw_response.split("<|eot_id|>")[0].strip()
        parsed = _parse_json_object(clean_json)

        priority = str(parsed.get("remediation_priority", "SAFE")).upper()
        if priority not in {
            "CRITICAL",
            "HIGH",
            "MEDIUM",
            "LOW",
            "MANUAL_REVIEW_REQUIRED",
            "SAFE",
        }:
            priority = "SAFE"

        is_secret = priority in CONFIRMED_SECRET_PRIORITIES
        confidence = _as_confidence(parsed.get("confidence_score"), is_secret)
        reasoning = str(parsed.get("reasoning", "No reasoning provided by model."))

        return LLMResponse(
            is_genuine_secret=is_secret,
            confidence_score=confidence,
            remediation_priority=priority,
            reasoning=reasoning,
        )


def get_scanner() -> HybridAIScanner:
    """Return the singleton scanner so model load happens only once."""
    global _SCANNER
    if _SCANNER is None:
        _SCANNER = HybridAIScanner()
    return _SCANNER


def _build_prompt(candidate: CandidateSecret) -> str:
    filename = candidate.file_path.name
    unredacted_code_snippet = candidate.sanitized_context or ""
    prompt = f"""You are an elite Application Security Engineer. Your task is to analyze a code snippet and determine if it contains a LIVE, HIGH-RISK hardcoded secret.

### Evaluation Rubric:
1. SAFE (False Positives): UUIDs, CSS Hex colors, cryptographic public keys, empty strings, obvious placeholder/dummy values (e.g., 'test_key', 'admin123' in test context), and files ending in `.example` or `.md`.
2. CRITICAL (True Positives): High-entropy, production-looking API keys, cloud provider tokens (AWS, GCP, Azure), database URIs with complex passwords, and private cryptographic keys assigned to active variables.

Analyze the context (variable names, comments, filename) deeply.

### Instruction:
Analyze the code snippet from '{filename}'. Output ONLY a valid JSON object. The "reasoning" key MUST come first so you can think step-by-step before determining the "remediation_priority".

### Input:
{unredacted_code_snippet}

### Response:
{{
    "reasoning": "step-by-step logic here...",
    "is_genuine_secret": true/false,
    "confidence_score": 0.0 to 1.0,
    "remediation_priority": "CRITICAL|HIGH|MEDIUM|LOW|SAFE"
}}"""
    return prompt


def _parse_json_object(payload: str) -> dict[str, Any]:
    """Parse model output robustly, including partial wrappers around JSON."""
    try:
        parsed = json.loads(payload)
        if isinstance(parsed, dict):
            return parsed
        logging.warning("LLM returned non-object JSON payload: %s", payload)
        return {}
    except json.JSONDecodeError:
        start = payload.find("{")
        end = payload.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                extracted = json.loads(payload[start : end + 1])
                if isinstance(extracted, dict):
                    return extracted
            except json.JSONDecodeError:
                logging.warning("Failed to parse extracted JSON object from LLM output: %s", payload)
                return {}
        logging.warning("Failed to parse LLM JSON output: %s", payload)
        return {}


def _as_confidence(value: Any, is_secret: bool) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 1.0 if is_secret else 0.0
    if confidence < 0.0:
        return 0.0
    if confidence > 1.0:
        return 1.0
    return confidence


async def evaluate_candidate(candidate: CandidateSecret) -> LLMResponse:
    """Evaluate a candidate secret with graceful fallback behavior."""
    try:
        return get_scanner().analyze_candidate(candidate)
    except Exception as exc:
        logging.warning(
            "LLM validation failed for %s:%s. Defaulting to manual review. Error: %s",
            candidate.file_path.name,
            candidate.line_number,
            exc,
        )
        return LLMResponse(
            is_genuine_secret=True,
            confidence_score=0.0,
            remediation_priority="MANUAL_REVIEW_REQUIRED",
            reasoning="LLM inference failed or timed out. Defaulting to manual review.",
        )
