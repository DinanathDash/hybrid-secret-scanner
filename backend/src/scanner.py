import math
import re
from pathlib import Path

from src.ingestion import yield_scannable_files
from src.models import CandidateSecret, LLMResponse

from .context_extractor import extract_fixed_window_context
from .llm_engine import evaluate_candidate

# High-Recall Regex Patterns
PATTERNS = {
    "AWS_ACCESS_KEY": re.compile(r"(?i)\b(AKIA[0-9A-Z]{16})\b"),
    "GITHUB_TOKEN": re.compile(
        r"(?i)\b(ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59})\b"
    ),
    "DATABASE_URI": re.compile(
        r"(?i)(mongodb(?:\+srv)?:\/\/[^\s'\"]+|postgres(?:ql)?:\/\/[^\s'\"]+)"
    ),
    "PRIVATE_KEY_OR_JWT": re.compile(
        r"(?i)(-----BEGIN [A-Z ]+ PRIVATE KEY-----|eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,})"
    ),
}


def calculate_shannon_entropy(data: str) -> float:
    """Calculates the Shannon entropy of a string."""
    if not data:
        return 0.0
    entropy = 0.0
    for x in set(data):
        p_x = float(data.count(x)) / len(data)
        entropy -= p_x * math.log(p_x, 2)
    return entropy


async def scan_file_for_secrets(file_path: Path) -> list[CandidateSecret]:
    """Scans a single file line-by-line using regex heuristics."""
    findings = []
    try:
        # Since ingestion.py filtered out massive files, standard open() is safe here.
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            for line_number, line in enumerate(f, 1):
                for category, pattern in PATTERNS.items():
                    for match in pattern.finditer(line):
                        # Extract the captured group if it exists, otherwise the full match
                        secret_value = match.group(1) if match.groups() else match.group(0)
                        entropy = calculate_shannon_entropy(secret_value)

                        findings.append(
                            CandidateSecret(
                                file_path=file_path,
                                line_number=line_number,
                                raw_secret=secret_value,
                                secret_category=category,
                                entropy=entropy,
                            )
                        )
    except Exception:
        # Silently skip files that trigger unexpected OS/read errors during scan
        pass

    return findings


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
        secrets = await scan_file_for_secrets(file_path)

        for secret in secrets:
            # Build a strict 11-line window (target line +/- 5) for LLM context.
            processed_secret = extract_fixed_window_context(secret, radius=5)

            # Phase 4: Ask the LLM
            llm_evaluation = await evaluate_candidate(processed_secret)

            all_findings.append((processed_secret, llm_evaluation))

            print(
                f"[!] {processed_secret.secret_category} in {processed_secret.file_path.name}:{processed_secret.line_number}"
            )
            print(
                f"    -> LLM Verdict: Genuine={llm_evaluation.is_genuine_secret} | Confidence={llm_evaluation.confidence_score} | Priority={llm_evaluation.remediation_priority}"
            )

    return all_findings
