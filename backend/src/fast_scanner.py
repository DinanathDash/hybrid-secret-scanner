from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Literal

from .models import CandidateSecret, LLMResponse

# Signature-based fast scan patterns (gitleaks/trufflehog-style heuristics).
REGEX_PATTERNS = {
    "AWS_ACCESS_KEY": re.compile(r"(?i)\b(AKIA[0-9A-Z]{16})\b"),
    "STRIPE_SECRET_KEY": re.compile(r"(?i)\b(sk_(?:live|test)_[0-9a-zA-Z]{16,})\b"),
    "OPENAI_API_KEY": re.compile(r"(?i)\b(sk-(?:proj-|live-|test-)?[a-zA-Z0-9_-]{20,})\b"),
    "GOOGLE_API_KEY": re.compile(r"\b(AIza[0-9A-Za-z\-_]{35})\b"),
    "SLACK_TOKEN": re.compile(r"\b(xox[baprs]-[0-9A-Za-z-]{10,})\b"),
    "GITHUB_TOKEN": re.compile(
        r"(?i)\b(ghp_[a-zA-Z0-9]{30,255}|github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59})\b"
    ),
    "DATABASE_URI": re.compile(
        r"(?i)(mongodb(?:\+srv)?:\/\/[^\s'\"]+|postgres(?:ql)?:\/\/[^\s'\"]+)"
    ),
    "PRIVATE_KEY_OR_JWT": re.compile(
        r"(?i)(-----BEGIN [A-Z ]+ PRIVATE KEY-----|eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,})"
    ),
    "GENERIC_HIGH_ENTROPY_TOKEN": re.compile(
        r"(?i)[a-z0-9_]*(?:key|token|secret|password|auth|jwt|hash|signature)[a-z0-9_]*[\s]*[=:]\s*['\"]([A-Za-z0-9+/=_-]{16,})['\"]"
    ),
}
# Backward-compatible alias.
PATTERNS = REGEX_PATTERNS

HIGH_RISK_CATEGORIES = {
    "AWS_ACCESS_KEY",
    "STRIPE_SECRET_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "SLACK_TOKEN",
    "GITHUB_TOKEN",
    "DATABASE_URI",
    "PRIVATE_KEY_OR_JWT",
    "GENERIC_HIGH_ENTROPY_TOKEN",
}


def calculate_shannon_entropy(data: str) -> float:
    if not data:
        return 0.0
    entropy = 0.0
    for token in set(data):
        probability = float(data.count(token)) / len(data)
        entropy -= probability * math.log(probability, 2)
    return entropy


def _is_obvious_non_secret(value: str) -> bool:
    # UUID-like values
    if re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        value,
    ):
        return True
    # SHA-256 / SHA-1 style hashes
    if re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", value):
        return True
    return False


def _is_local_dev_database_uri(value: str) -> bool:
    lowered = value.lower()
    local_host = any(host in lowered for host in ("localhost", "127.0.0.1", "::1"))
    dev_context = any(token in lowered for token in ("/dev", "/test", "user:pass@", "root:root@"))
    return local_host and dev_context


async def scan_file_for_secrets(
    file_path: Path,
    profile: Literal["fast", "full"] = "fast",
) -> list[CandidateSecret]:
    """Fast, signature-based candidate extraction."""
    findings: list[CandidateSecret] = []
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as handle:
            for line_number, line in enumerate(handle, 1):
                seen_values: set[str] = set()
                for category, pattern in REGEX_PATTERNS.items():
                    for match in pattern.finditer(line):
                        secret_value = match.group(1) if match.groups() else match.group(0)
                        if (
                            profile == "fast"
                            and category == "DATABASE_URI"
                            and _is_local_dev_database_uri(secret_value)
                        ):
                            continue
                        if category == "GENERIC_HIGH_ENTROPY_TOKEN" and _is_obvious_non_secret(
                            secret_value
                        ):
                            continue
                        entropy = calculate_shannon_entropy(secret_value)
                        if category == "GENERIC_HIGH_ENTROPY_TOKEN" and entropy <= 3.0:
                            continue
                        seen_values.add(secret_value)
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
        # Ignore unreadable files while preserving scan continuity.
        pass

    return findings


def heuristic_verdict(secret: CandidateSecret) -> LLMResponse:
    """Traditional scanner-style confidence based on pattern + entropy."""
    if secret.secret_category in HIGH_RISK_CATEGORIES:
        priority = "HIGH" if secret.entropy >= 3.2 else "MEDIUM"
        return LLMResponse(
            is_genuine_secret=True,
            confidence_score=0.7 if priority == "HIGH" else 0.6,
            remediation_priority=priority,
            reasoning=(
                "Fast scan matched a known high-risk secret signature. "
                "Run full scan for model-backed contextual reasoning."
            ),
        )

    return LLMResponse(
        is_genuine_secret=False,
        confidence_score=0.5,
        remediation_priority="SAFE",
        reasoning="Fast scan did not classify this candidate as a confirmed secret.",
    )
