from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import warnings
from collections import OrderedDict
from pathlib import Path
from typing import Any

from .config import (
    LLM_ADAPTER_PATH,
    LLM_CACHE_ENABLED,
    LLM_CACHE_MAX_ENTRIES,
    LLM_DRY_RUN,
    LLM_EFFECTIVE_MAX_TOKENS,
    LLM_MAX_TOKENS,
    LLM_MODEL_ID,
    LLM_WARMUP_ON_START,
)
from .models import CandidateSecret, LLMResponse

CONFIRMED_SECRET_PRIORITIES = {"CRITICAL", "HIGH", "MEDIUM"}
_SCANNER: HybridAIScanner | None = None
_EFFECTIVE_MAX_TOKENS = LLM_EFFECTIVE_MAX_TOKENS
_LLM_RUNTIME_READY: bool | None = None
_LLM_RUNTIME_REASON: str | None = None
_WARMUP_DONE = False
_WARMUP_MESSAGE = "Not warmed yet."
_VERDICT_CACHE: OrderedDict[str, LLMResponse] = OrderedDict()
_CACHE_HITS = 0
_CACHE_MISSES = 0
_INFERENCE_LOCK = threading.Lock()


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

    def analyze_candidate(
        self,
        candidate: CandidateSecret,
        scan_mode: str = "full",
    ) -> LLMResponse:
        """Run deterministic MLX inference and parse structured verdict safely."""
        if self.dry_run:
            return LLMResponse(
                is_genuine_secret=False,
                confidence_score=0.0,
                remediation_priority="SAFE",
                reasoning="Dry-run mode enabled. LLM inference skipped.",
            )

        from mlx_lm import generate

        prompt = _build_prompt(candidate, scan_mode=scan_mode)

        dynamic_max = 40
        with _INFERENCE_LOCK:
            raw_response = generate(
                self.model,
                self.tokenizer,
                prompt=prompt,
                max_tokens=dynamic_max,
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
        reasoning = "Reasoning disabled for throughput benchmarking."

        return LLMResponse(
            is_genuine_secret=is_secret,
            confidence_score=confidence,
            remediation_priority=priority,
            reasoning=reasoning,
        )

    def analyze_candidates_batch(
        self,
        candidates: list[CandidateSecret],
        scan_mode: str,
    ) -> dict[int, LLMResponse]:
        """Run a single LLM call for many candidates and map by line number."""
        if not candidates:
            return {}

        if self.dry_run:
            return {
                candidate.line_number: LLMResponse(
                    is_genuine_secret=False,
                    confidence_score=0.0,
                    remediation_priority="SAFE",
                    reasoning="Dry-run mode enabled. LLM inference skipped.",
                )
                for candidate in candidates
            }

        from mlx_lm import generate

        prompt = _build_batch_prompt(candidates, scan_mode=scan_mode)
        dynamic_max = min(40 * len(candidates), 400)
        with _INFERENCE_LOCK:
            raw_response = generate(
                self.model,
                self.tokenizer,
                prompt=prompt,
                max_tokens=dynamic_max,
            )
        parsed_array = _parse_json_object(raw_response, expect_array=True)

        by_line: dict[int, LLMResponse] = {}
        for item in parsed_array:
            if not isinstance(item, dict):
                continue

            try:
                line_number = int(item.get("line_number"))
            except (TypeError, ValueError):
                continue

            priority = str(item.get("remediation_priority", "SAFE")).upper()
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
            confidence = _as_confidence(item.get("confidence_score"), is_secret)
            reasoning = "Reasoning disabled for throughput benchmarking."

            by_line[line_number] = LLMResponse(
                is_genuine_secret=is_secret,
                confidence_score=confidence,
                remediation_priority=priority,
                reasoning=reasoning,
            )

        for candidate in candidates:
            if candidate.line_number not in by_line:
                by_line[candidate.line_number] = LLMResponse(
                    is_genuine_secret=True,
                    confidence_score=0.0,
                    remediation_priority="MANUAL_REVIEW_REQUIRED",
                    reasoning=(
                        "Batch LLM output missing this line number. "
                        "Defaulting to manual review."
                    ),
                )

        return by_line


def get_scanner() -> HybridAIScanner:
    """Return the singleton scanner so model load happens only once."""
    global _SCANNER
    if _SCANNER is None:
        _SCANNER = HybridAIScanner()
    return _SCANNER


def get_llm_runtime_status() -> tuple[bool, str]:
    """
    Return whether full LLM inference can run in this process, with a reason.
    This avoids repetitive per-finding failures/noise when mlx_lm is missing.
    """
    global _LLM_RUNTIME_READY, _LLM_RUNTIME_REASON

    if LLM_DRY_RUN:
        return False, "LLM_DRY_RUN is enabled."

    if _LLM_RUNTIME_READY is not None and _LLM_RUNTIME_REASON is not None:
        return _LLM_RUNTIME_READY, _LLM_RUNTIME_REASON

    try:
        probe = subprocess.run(
            [sys.executable, "-c", "import mlx_lm; print('mlx_lm_ok')"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        _LLM_RUNTIME_READY = False
        _LLM_RUNTIME_REASON = (
            "LLM runtime probe failed unexpectedly. "
            f"Full scan cannot proceed. Error: {exc}"
        )
        return _LLM_RUNTIME_READY, _LLM_RUNTIME_REASON

    if probe.returncode != 0:
        stderr = (probe.stderr or "").strip().splitlines()
        detail = stderr[-1] if stderr else "unknown runtime import failure"
        _LLM_RUNTIME_READY = False
        _LLM_RUNTIME_REASON = (
            "LLM runtime unavailable (`mlx_lm` probe failed). "
            f"Full scan cannot proceed. Error: {detail}"
        )
    else:
        _LLM_RUNTIME_READY = True
        _LLM_RUNTIME_REASON = "LLM runtime ready."

    return _LLM_RUNTIME_READY, _LLM_RUNTIME_REASON


def warmup_llm_if_configured() -> tuple[bool, str]:
    """Warm model once on server startup so later scans avoid cold start."""
    global _WARMUP_DONE, _WARMUP_MESSAGE

    if _WARMUP_DONE:
        return True, _WARMUP_MESSAGE

    if not LLM_WARMUP_ON_START:
        _WARMUP_DONE = False
        _WARMUP_MESSAGE = "Warmup disabled via LLM_WARMUP_ON_START."
        return False, _WARMUP_MESSAGE

    if LLM_DRY_RUN:
        _WARMUP_DONE = False
        _WARMUP_MESSAGE = "Warmup skipped because LLM_DRY_RUN is enabled."
        return False, _WARMUP_MESSAGE

    ready, reason = get_llm_runtime_status()
    if not ready:
        _WARMUP_DONE = False
        _WARMUP_MESSAGE = f"Warmup skipped: {reason}"
        return False, _WARMUP_MESSAGE

    started = time.perf_counter()
    try:
        scanner = get_scanner()
        # Run one tiny inference to warm kernels/caches, not just model load.
        warm_candidate = CandidateSecret(
            file_path=Path("warmup_snippet.py"),
            line_number=1,
            raw_secret="AKIA1A2B3C4D5E6F7G8H",
            secret_category="AWS_ACCESS_KEY",
            entropy=4.2,
            sanitized_context='api_key = "AKIA1A2B3C4D5E6F7G8H"',
            variable_name="api_key",
        )
        scanner.analyze_candidate(warm_candidate)
    except Exception as exc:
        _WARMUP_DONE = False
        _WARMUP_MESSAGE = f"Warmup failed: {exc}"
        return False, _WARMUP_MESSAGE

    elapsed = round(time.perf_counter() - started, 3)
    _WARMUP_DONE = True
    _WARMUP_MESSAGE = f"Warmup complete in {elapsed}s."
    return True, _WARMUP_MESSAGE


def get_warmup_status() -> tuple[bool, str]:
    return _WARMUP_DONE, _WARMUP_MESSAGE


def get_cache_stats() -> dict[str, int | bool]:
    return {
        "enabled": LLM_CACHE_ENABLED,
        "size": len(_VERDICT_CACHE),
        "hits": _CACHE_HITS,
        "misses": _CACHE_MISSES,
    }


def _build_prompt(candidate: CandidateSecret, scan_mode: str = "full") -> str:
    filename = candidate.file_path.name
    unredacted_code_snippet = candidate.sanitized_context or ""
    variable_name = candidate.variable_name or "UNKNOWN"
    line_number = candidate.line_number
    entropy = f"{candidate.entropy:.2f}"
    category = candidate.secret_category
    output_contract = "is_genuine_secret, confidence_score, remediation_priority"

    prompt = f"""You are an application security analyst.
Return ONLY valid JSON with keys:
{output_contract}.
IMPORTANT: You MUST wrap all JSON keys in double quotes.
You must respond with valid, parseable JSON only. Do not include markdown formatting, code blocks, or conversational text. All string values, including keys and the `remediation_priority` value, MUST be enclosed in double quotes (e.g., "CRITICAL", "HIGH", "SAFE"). Example: {{"is_genuine_secret": true, "confidence_score": 0.99, "remediation_priority": "CRITICAL"}}
You are a highly skeptical security analyst. Your default assumption is that the provided string is a dummy value, placeholder, or test token. You must ONLY classify `is_genuine_secret: true` if there is overwhelming contextual evidence that this is a live, production-grade credential. Aggressively flag examples, documentation snippets, obvious entropy variables (e.g., 'test_password', '12345'), and code templates as `is_genuine_secret: false`.
Allowed remediation_priority: CRITICAL,HIGH,MEDIUM,LOW,MANUAL_REVIEW_REQUIRED,SAFE.
Treat placeholders, hashes, UUIDs, PUBLIC KEY blocks, docs/examples, env-var retrieval, and any string containing 'EXAMPLE', 'DUMMY', or 'test' as SAFE.
Treat active hardcoded cloud/API credentials, private keys, JWT secrets, credentialed DB URIs, and generic high-entropy tokens in auth/key/token-like assignments as genuine secrets.
Focus on the target secret and its line first; use surrounding context only for disambiguation.

### Input:
Filename: {filename}
Line Number: {line_number}
Candidate category: {category}
Candidate variable: {variable_name}
Candidate entropy: {entropy}
Target Secret to Evaluate: {candidate.raw_secret}
Context Window:
{unredacted_code_snippet}

### Output:
{{"""
    return prompt


def _build_batch_prompt(candidates: list[CandidateSecret], scan_mode: str = "full") -> str:
    first = candidates[0]
    filename = first.file_path.name
    candidate_lines: list[str] = []

    for candidate in candidates:
        context = candidate.sanitized_context or ""
        variable_name = candidate.variable_name or "UNKNOWN"
        entropy = f"{candidate.entropy:.2f}"
        candidate_lines.append(
            "\n".join(
                [
                    f"Line {candidate.line_number}: {candidate.raw_secret}",
                    f"  category: {candidate.secret_category}",
                    f"  variable: {variable_name}",
                    f"  entropy: {entropy}",
                    "  context:",
                    context,
                ]
            )
        )

    candidate_list_string = "\n\n".join(candidate_lines)
    return f"""You are an application security analyst.
Return ONLY valid JSON.
Output must be a JSON array where each object maps to one candidate using line_number.
IMPORTANT: You MUST wrap all JSON keys in double quotes.
You must respond with valid, parseable JSON only. Do not include markdown formatting, code blocks, or conversational text. All string values, including keys and the `remediation_priority` value, MUST be enclosed in double quotes (e.g., "CRITICAL", "HIGH", "SAFE"). Example: {{"is_genuine_secret": true, "confidence_score": 0.99, "remediation_priority": "CRITICAL"}}
You are a highly skeptical security analyst. Your default assumption is that the provided string is a dummy value, placeholder, or test token. You must ONLY classify `is_genuine_secret: true` if there is overwhelming contextual evidence that this is a live, production-grade credential. Aggressively flag examples, documentation snippets, obvious entropy variables (e.g., 'test_password', '12345'), and code templates as `is_genuine_secret: false`.
Allowed remediation_priority: CRITICAL,HIGH,MEDIUM,LOW,MANUAL_REVIEW_REQUIRED,SAFE.
Treat placeholders, hashes, UUIDs, PUBLIC KEY blocks, docs/examples, env-var retrieval, and any string containing 'EXAMPLE', 'DUMMY', or 'test' as SAFE.
Treat active hardcoded cloud/API credentials, private keys, JWT secrets, credentialed DB URIs, and generic high-entropy tokens in auth/key/token-like assignments as genuine secrets.
Focus on each target secret and its line first; use surrounding context only for disambiguation.

### Input:
Filename: {filename}
Candidates to Evaluate:
{candidate_list_string}

### Output Format:
[
  {{
    "line_number": int,
        "is_genuine_secret": bool,
    "confidence_score": float,
    "remediation_priority": "..."
  }}
]

### Output:
[
"""


def _candidate_cache_key(candidate: CandidateSecret) -> str:
    payload = "||".join(
        [
            candidate.secret_category,
            candidate.raw_secret,
            candidate.variable_name or "",
            candidate.sanitized_context or "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_get(cache_key: str) -> LLMResponse | None:
    global _CACHE_HITS, _CACHE_MISSES
    if not LLM_CACHE_ENABLED:
        return None
    cached = _VERDICT_CACHE.get(cache_key)
    if cached is None:
        _CACHE_MISSES += 1
        return None
    _CACHE_HITS += 1
    _VERDICT_CACHE.move_to_end(cache_key)
    return cached


def _cache_put(cache_key: str, verdict: LLMResponse) -> None:
    if not LLM_CACHE_ENABLED:
        return
    _VERDICT_CACHE[cache_key] = verdict
    _VERDICT_CACHE.move_to_end(cache_key)
    while len(_VERDICT_CACHE) > LLM_CACHE_MAX_ENTRIES:
        _VERDICT_CACHE.popitem(last=False)


def _parse_json_object(payload: str, expect_array: bool = False) -> dict[str, Any] | list[Any]:
    """Parse model output robustly, extracting JSON object or array content."""
    if expect_array:
        full_payload = payload if payload.lstrip().startswith("[") else "[" + payload
    else:
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

    if expect_array:
        start_idx = clean_text.find("[")
        end_idx = clean_text.rfind("]")
        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            logging.warning("Failed to locate JSON array boundaries in LLM output.")
            logging.warning("Cleaned LLM output for debugging: %s", clean_text)
            return []
        clean_text = clean_text[start_idx : end_idx + 1]
    else:
        start_idx = clean_text.find("{")
        if start_idx != -1:
            clean_text = clean_text[start_idx:]
    clean_text = re.sub(r'([{,]\s*)([a-zA-Z0-9_]+)(\s*:)', r'\1"\2"\3', clean_text)

    try:
        if expect_array:
            parsed = json.loads(clean_text)
            if isinstance(parsed, list):
                return parsed
            logging.warning("LLM returned non-array JSON payload after cleaning: %s", clean_text)
            return []

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
        return [] if expect_array else {}


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


async def evaluate_candidate(
    candidate: CandidateSecret,
    strict: bool = False,
    scan_mode: str = "full",
) -> LLMResponse:
    """Evaluate a candidate secret with optional strict failure behavior."""
    cache_key = f"{scan_mode}::{_candidate_cache_key(candidate)}"
    cached_verdict = _cache_get(cache_key)
    if cached_verdict is not None:
        return cached_verdict

    try:
        verdict = get_scanner().analyze_candidate(candidate, scan_mode=scan_mode)
        _cache_put(cache_key, verdict)
        return verdict
    except Exception as exc:
        if strict:
            raise RuntimeError(
                f"LLM validation failed for {candidate.file_path.name}:{candidate.line_number}: {exc}"
            ) from exc
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


async def evaluate_candidates_batch(
    candidates: list[CandidateSecret],
    strict: bool = False,
    scan_mode: str = "full",
) -> dict[int, LLMResponse]:
    """Evaluate many candidates in one inference call, with cache-aware fallbacks."""
    if not candidates:
        return {}

    line_to_verdict: dict[int, LLMResponse] = {}
    uncached: list[CandidateSecret] = []
    uncached_keys: dict[int, str] = {}

    for candidate in candidates:
        cache_key = f"{scan_mode}::{_candidate_cache_key(candidate)}"
        cached_verdict = _cache_get(cache_key)
        if cached_verdict is not None:
            line_to_verdict[candidate.line_number] = cached_verdict
            continue
        uncached.append(candidate)
        uncached_keys[candidate.line_number] = cache_key

    if uncached:
        try:
            uncached_results = get_scanner().analyze_candidates_batch(uncached, scan_mode=scan_mode)
        except Exception as exc:
            if strict:
                first = uncached[0]
                raise RuntimeError(
                    "LLM batch validation failed for "
                    f"{first.file_path.name}:{first.line_number}: {exc}"
                ) from exc
            logging.warning("LLM batch validation failed. Defaulting to manual review. Error: %s", exc)
            uncached_results = {
                candidate.line_number: LLMResponse(
                    is_genuine_secret=True,
                    confidence_score=0.0,
                    remediation_priority="MANUAL_REVIEW_REQUIRED",
                    reasoning="LLM batch inference failed or timed out. Defaulting to manual review.",
                )
                for candidate in uncached
            }

        for candidate in uncached:
            verdict = uncached_results.get(candidate.line_number)
            if verdict is None:
                verdict = LLMResponse(
                    is_genuine_secret=True,
                    confidence_score=0.0,
                    remediation_priority="MANUAL_REVIEW_REQUIRED",
                    reasoning="Batch LLM output missing this line number. Defaulting to manual review.",
                )
            line_to_verdict[candidate.line_number] = verdict
            _cache_put(uncached_keys[candidate.line_number], verdict)

    return line_to_verdict
