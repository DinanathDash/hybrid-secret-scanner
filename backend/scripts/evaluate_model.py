from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from cli_runtime import run_cli
import src.llm_engine as llm_engine
from src.llm_engine import HybridAIScanner, get_scanner
from src.models import CandidateSecret

POSITIVE_PRIORITIES = {"CRITICAL", "HIGH", "MEDIUM"}


@dataclass
class ConfusionMatrix:
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate HybridAIScanner on a golden JSONL dataset")
    parser.add_argument(
        "--dataset",
        default="examples/golden_dataset.jsonl",
        help="Path to JSONL golden dataset (default: examples/golden_dataset.jsonl)",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=0,
        help="Optional cap on number of rows to evaluate (0 = all rows).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=250,
        help="Max output tokens per sample for eval speed (default: 250).",
    )
    return parser.parse_args()


def analyze_snippet(scanner: HybridAIScanner, code: str, filename: str):
    """Adapter for evals: build a candidate and run scanner inference on raw snippet."""
    candidate = CandidateSecret(
        file_path=Path(filename),
        line_number=1,
        raw_secret="",
        secret_category="EVAL",
        entropy=0.0,
        sanitized_context=code,
        variable_name="UNKNOWN",
    )
    return scanner.analyze_candidate(candidate)


def _priority_to_bool(priority: str) -> bool:
    return priority.upper() in POSITIVE_PRIORITIES


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _print_report(matrix: ConfusionMatrix, total: int) -> None:
    precision = _safe_ratio(matrix.tp, matrix.tp + matrix.fp)
    recall = _safe_ratio(matrix.tp, matrix.tp + matrix.fn)

    print("\n" + "=" * 72)
    print("Hybrid Secret Scanner LLM Evaluation Report")
    print("=" * 72)
    print(f"Samples Evaluated: {total}")
    print("\nConfusion Matrix")
    print("-" * 72)
    print(f"True Positives (TP):  {matrix.tp}")
    print(f"False Positives (FP): {matrix.fp}")
    print(f"True Negatives (TN):  {matrix.tn}")
    print(f"False Negatives (FN): {matrix.fn}")
    print("-" * 72)
    print(f"Precision: {precision * 100:.2f}%")
    print(f"Recall:    {recall * 100:.2f}%")
    print("=" * 72)


def main() -> None:
    args = _parse_args()
    dataset_path = Path(args.dataset).resolve()

    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    # Keep eval runs fast and deterministic regardless shell env values.
    llm_engine.LLM_MAX_TOKENS = max(32, int(args.max_tokens))

    # Explicitly re-use the singleton scanner for the full eval run.
    scanner = get_scanner()
    matrix = ConfusionMatrix()
    total = 0

    with open(dataset_path, encoding="utf-8") as handle:
        total_rows = sum(1 for line in handle if line.strip())

    target_rows = total_rows if args.max_samples <= 0 else min(total_rows, args.max_samples)
    print(f"Starting eval on {target_rows} sample(s) from {dataset_path}", flush=True)

    with open(dataset_path, encoding="utf-8") as handle:
        eval_start = time.time()
        for line_no, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            if args.max_samples > 0 and total >= args.max_samples:
                break

            total += 1

            try:
                row = json.loads(line)
                code = str(row["code"])
                expected = bool(row["is_real_secret"])
                filename = str(row["filename"])
            except Exception as exc:
                # Bad eval row is treated as a missed detection for security-first accounting.
                print(f"[WARN] Invalid dataset row at line {line_no}: {exc}")
                matrix.fn += 1
                continue

            try:
                row_start = time.time()
                verdict = analyze_snippet(scanner, code=code, filename=filename)
                predicted = _priority_to_bool(verdict.remediation_priority)
            except Exception as exc:
                # Worst-case policy: inference/parsing failures count as false negatives.
                print(f"[WARN] Inference failed at line {line_no}: {exc}")
                matrix.fn += 1
                continue

            elapsed = time.time() - eval_start
            sample_seconds = time.time() - row_start
            avg = elapsed / total
            eta = max(target_rows - total, 0) * avg
            print(
                f"[{total}/{target_rows}] {filename} -> {verdict.remediation_priority} "
                f"({sample_seconds:.1f}s, elapsed={elapsed:.1f}s, eta={eta:.1f}s)",
                flush=True,
            )

            if predicted and expected:
                matrix.tp += 1
            elif predicted and not expected:
                matrix.fp += 1
            elif not predicted and expected:
                matrix.fn += 1
            else:
                matrix.tn += 1

    _print_report(matrix, total)


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
