import math
import re
from pathlib import Path
from typing import List

from src.models import CandidateSecret
from src.ingestion import yield_scannable_files
from .context_extractor import extract_and_redact_context
from .context_extractor import extract_and_redact_context
from .llm_engine import evaluate_candidate

# High-Recall Regex Patterns
PATTERNS = {
    "AWS_ACCESS_KEY": re.compile(r"(?i)\b(AKIA[0-9A-Z]{16})\b"),
    "GITHUB_TOKEN": re.compile(r"(?i)\b(ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59})\b"),
    "DATABASE_URI": re.compile(r"(?i)(mongodb(?:\+srv)?:\/\/[^\s'\"]+|postgres(?:ql)?:\/\/[^\s'\"]+)"),
    "PRIVATE_KEY_OR_JWT": re.compile(r"(?i)(-----BEGIN [A-Z ]+ PRIVATE KEY-----|eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,})")
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

async def scan_file_for_secrets(file_path: Path) -> List[CandidateSecret]:
    """Scans a single file line-by-line using regex heuristics."""
    findings = []
    try:
        # Since ingestion.py filtered out massive files, standard open() is safe here.
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
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
                                entropy=entropy
                            )
                        )
    except Exception:
        # Silently skip files that trigger unexpected OS/read errors during scan
        pass
    
    return findings

async def run_pipeline(root_dir: Path) -> List[tuple[CandidateSecret, object]]:
    """
    The main orchestrator. 
    Phase 1 (Ingest) -> Phase 2 (Scan) -> Phase 3 (Context) -> Phase 4 (LLM Validate).
    """
    all_findings = []
    
    async for file_path in yield_scannable_files(root_dir):
        secrets = await scan_file_for_secrets(file_path)
        
        for secret in secrets:
            processed_secret = extract_and_redact_context(secret)
            
            # Phase 4: Ask the LLM
            llm_evaluation = await evaluate_candidate(processed_secret)
            
            all_findings.append((processed_secret, llm_evaluation))
            
            print(f"[!] {processed_secret.secret_category} in {processed_secret.file_path.name}:{processed_secret.line_number}")
            print(f"    -> LLM Verdict: Genuine={llm_evaluation.is_genuine_secret} | Confidence={llm_evaluation.confidence_score} | Priority={llm_evaluation.remediation_priority}")
            
    return all_findings