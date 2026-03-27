from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from src.ingestion import yield_scannable_files
from src.models import CandidateSecret, LLMResponse

from .context_extractor import extract_fixed_window_context
from .fast_scanner import heuristic_verdict, scan_file_for_secrets
from .llm_engine import evaluate_candidate, get_llm_runtime_status


class FullScanError(Exception):
    def __init__(self, message: str, logs: list[str] | None = None) -> None:
        super().__init__(message)
        self.logs = logs or []


async def run_pipeline(target_path: Path) -> list[tuple[CandidateSecret, LLMResponse]]:
    """
    The main orchestrator.
    Phase 1 (Ingest) -> Phase 2 (Scan) -> Phase 3 (Context) -> Phase 4 (LLM Validate).
    """
    all_findings = []
    target_path = target_path.resolve()

    if target_path.is_file():
        file_paths = [target_path]
    elif target_path.is_dir():
        file_paths = [path async for path in yield_scannable_files(target_path)]
    else:
        return all_findings

    for file_path in file_paths:
        secrets = await scan_file_for_secrets(file_path, profile="full")

        for secret in secrets:
            # Build a strict 11-line window (target line +/- 5) for LLM context.
            processed_secret = extract_fixed_window_context(secret, radius=5)

            # Phase 4: Ask the LLM
            llm_evaluation = await evaluate_candidate(processed_secret, scan_mode="full")

            all_findings.append((processed_secret, llm_evaluation))

            print(
                f"[!] {processed_secret.secret_category} in {processed_secret.file_path.name}:{processed_secret.line_number}"
            )
            print(
                f"    -> LLM Verdict: Genuine={llm_evaluation.is_genuine_secret} | Confidence={llm_evaluation.confidence_score} | Priority={llm_evaluation.remediation_priority}"
            )

    return all_findings


async def scan_snippet(
    code: str,
    filename: str = "snippet.txt",
    scan_mode: Literal["fast", "lite", "full"] = "fast",
) -> tuple[list[tuple[CandidateSecret, LLMResponse]], Literal["fast", "lite", "full"]]:
    """
    Scan an in-memory code snippet by writing it to a temporary file and
    reusing the existing regex + LLM pipeline stages.
    """
    suffix = Path(filename).suffix if Path(filename).suffix else ".txt"
    with NamedTemporaryFile(mode="w", encoding="utf-8", suffix=suffix, delete=True) as tmp:
        tmp.write(code)
        tmp.flush()

        file_path = Path(tmp.name)
        findings: list[tuple[CandidateSecret, LLMResponse]] = []
        candidate_profile: Literal["fast", "full"] = "full" if scan_mode in {"lite", "full"} else "fast"
        secrets = await scan_file_for_secrets(file_path, profile=candidate_profile)
        effective_mode: Literal["fast", "lite", "full"] = scan_mode

        if scan_mode in {"lite", "full"}:
            llm_ready, llm_reason = get_llm_runtime_status()
            if not llm_ready:
                raise FullScanError(
                    f"{scan_mode.title()} scan failed before inference started.",
                    logs=[
                        f"Requested mode: {scan_mode}",
                        f"Runtime check failed: {llm_reason}",
                        "Action: install and configure MLX runtime (`mlx_lm`) or run fast scan.",
                    ],
                )

        processed_secrets = [extract_fixed_window_context(secret, radius=5) for secret in secrets]

        if effective_mode in {"lite", "full"}:
            for secret in processed_secrets:
                try:
                    verdict = await evaluate_candidate(
                        secret,
                        strict=True,
                        scan_mode=effective_mode,
                    )
                except Exception as exc:
                    verdict = LLMResponse(
                        is_genuine_secret=True,
                        confidence_score=0.0,
                        remediation_priority="MANUAL_REVIEW_REQUIRED",
                        reasoning=f"Inference failed: {exc}",
                    )
                findings.append((secret, verdict))
        else:
            for secret in processed_secrets:
                findings.append((secret, heuristic_verdict(secret)))

        return findings, effective_mode
