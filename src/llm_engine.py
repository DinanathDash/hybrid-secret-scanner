from __future__ import annotations

import json
import logging
import os
import re
import warnings
from typing import Any

from .config import LLM_ADAPTER_PATH, LLM_DRY_RUN, LLM_MAX_TOKENS, LLM_MODEL_ID
from .models import CandidateSecret, LLMResponse

CONFIRMED_SECRET_PRIORITIES = {"CRITICAL", "HIGH", "MEDIUM"}
_SCANNER: HybridAIScanner | None = None
_EFFECTIVE_MAX_TOKENS = 250


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
            max_tokens=min(LLM_MAX_TOKENS, _EFFECTIVE_MAX_TOKENS),
        )
        parsed = _parse_json_object(raw_response)

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
    prompt = f"""Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
You are an elite Application Security Engineer. Analyze the code snippet from '{filename}' and output a valid JSON object. 
IMPORTANT: Output ONLY valid, raw JSON. Do NOT wrap the JSON in markdown.

Evaluation Rubric:
- SAFE: UUIDs, CSS Hex colors, public keys, empty strings, placeholder/dummy values ('test_key', 'admin123' in test context), `.example` files, `.md` files, and environment variable retrievals (e.g., os.environ.get).
- CRITICAL: High-entropy API keys, cloud provider tokens (AWS, GCP, Azure), database URIs with complex passwords assigned to active variables.

### Example 1 (Safe Placeholder):
Filename: docs/setup.md
Code: api_key = "YOUR_API_KEY_HERE"
Response:
{{
    "reasoning": "The file is markdown documentation and the value is an obvious placeholder.",
    "is_genuine_secret": false,
    "confidence_score": 0.99,
    "remediation_priority": "SAFE"
}}

### Example 2 (Safe Environment Variable):
Filename: src/config.py
Code: aws_key = os.getenv("AWS_ACCESS_KEY_ID")
Response:
{{
    "reasoning": "The code is securely loading the credential from an environment variable, not hardcoding it.",
    "is_genuine_secret": false,
    "confidence_score": 0.99,
    "remediation_priority": "SAFE"
}}

The JSON format MUST exactly match the examples above.
Stop immediately after the final closing brace.

### Input:
Filename: {filename}
Code: {unredacted_code_snippet}

### Response:
{{"""
    return prompt


def _parse_json_object(payload: str) -> dict[str, Any]:
    """Parse model output robustly, extracting only the first JSON object."""
    # Rebuild the opening brace that is prefilled in the prompt.
    full_payload = payload if payload.lstrip().startswith("{") else "{" + payload

    clean_text = full_payload.split("<|eot_id|>")[0].strip()

    # Defensive guard: if redaction markers leak into output channels, ignore non-JSON prefixes.
    redaction_idx = clean_text.find("<REDACTED_SECRET_LENGTH_")
    first_brace_idx = clean_text.find("{")
    if redaction_idx != -1 and (first_brace_idx == -1 or redaction_idx < first_brace_idx):
        clean_text = clean_text[first_brace_idx:] if first_brace_idx != -1 else ""

    # Drop hallucinated continuation sections (e.g., an extra "### Response:" block).
    clean_text = clean_text.split("### Response:")[0].strip()

    # If a second JSON object starts without a heading, keep only the first block.
    if "\n\n{" in clean_text:
        clean_text = clean_text.split("\n\n{", 1)[0].strip()

    # Remove markdown fences if the model wraps the JSON in code blocks.
    clean_text = re.sub(r"^```json\s*", "", clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r"^```\s*", "", clean_text)
    clean_text = re.sub(r"\s*```$", "", clean_text)

    start_idx = clean_text.find("{")
    if start_idx != -1:
        clean_text = clean_text[start_idx:]

    try:
        # Parse only the first complete JSON object and ignore any trailing junk.
        parsed, end_idx = json.JSONDecoder().raw_decode(clean_text)
        clean_text = clean_text[:end_idx]
        if isinstance(parsed, dict):
            return parsed
        logging.warning("LLM returned non-object JSON payload after cleaning: %s", clean_text)
        return {}
    except json.JSONDecodeError as exc:
        logging.warning("Failed to parse LLM JSON output after cleaning. Error: %s", exc)
        logging.warning("Cleaned LLM output for debugging: %s", clean_text)
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
