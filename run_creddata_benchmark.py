import argparse
import asyncio
import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Dict, Iterable, Tuple


GroundTruthKey = Tuple[str, int]
VALID_LABELS = {"T", "F"}


def local_now_iso() -> str:
    """Return current system-local time with timezone offset."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass
class EvaluationMetrics:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    unlabeled_hits: int = 0
    labeled_hits: int = 0
    discarded_false: int = 0


@dataclass
class GroundTruthStats:
    labeled_rows: int = 0
    ignored_rows: int = 0
    conflicts: int = 0
    ambiguous_keys: int = 0


def normalize_meta_path(path_value: str) -> str:
    """Normalize metadata path values to POSIX style for stable keying."""
    return str(Path(path_value.strip()).as_posix())


def make_key(path_value: str, line_number: int) -> GroundTruthKey:
    return (normalize_meta_path(path_value), int(line_number))


def safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def iter_meta_csv_files(meta_root: Path) -> Iterable[Path]:
    for csv_path in sorted(meta_root.glob("*.csv")):
        if csv_path.is_file():
            yield csv_path


def build_ground_truth(meta_root: Path) -> tuple[Dict[GroundTruthKey, str], GroundTruthStats]:
    label_sets: Dict[GroundTruthKey, set[str]] = {}
    stats = GroundTruthStats()

    for csv_path in iter_meta_csv_files(meta_root):
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                label = (row.get("GroundTruth") or "").strip().upper()
                if label not in VALID_LABELS:
                    stats.ignored_rows += 1
                    continue

                file_path_value = (row.get("FilePath") or "").strip()
                line_start_raw = (row.get("LineStart") or "").strip()
                line_end_raw = (row.get("LineEnd") or "").strip()

                if not file_path_value or not line_start_raw:
                    stats.ignored_rows += 1
                    continue

                try:
                    line_start = int(line_start_raw)
                    line_end = int(line_end_raw) if line_end_raw else line_start
                except ValueError:
                    stats.ignored_rows += 1
                    continue

                if line_end < line_start:
                    line_start, line_end = line_end, line_start

                for line_no in range(line_start, line_end + 1):
                    key = make_key(file_path_value, line_no)
                    observed = label_sets.setdefault(key, set())
                    before_size = len(observed)
                    observed.add(label)
                    if before_size == 1 and len(observed) == 2:
                        stats.conflicts += 1

                stats.labeled_rows += 1

    gt_map = {key: next(iter(labels)) for key, labels in label_sets.items() if len(labels) == 1}
    stats.ambiguous_keys = sum(1 for labels in label_sets.values() if len(labels) > 1)

    return gt_map, stats


def to_meta_style_path(file_path: Path, creddata_root: Path) -> str:
    """
    Convert an absolute scanned file path into CredData metadata style (e.g. data/<repo>/...).
    """
    resolved = file_path.resolve()
    relative = resolved.relative_to(creddata_root.resolve())
    return str(relative.as_posix())


def compute_metrics(metrics: EvaluationMetrics) -> tuple[float, float, float]:
    precision = safe_div(metrics.tp, metrics.tp + metrics.fp)
    recall = safe_div(metrics.tp, metrics.tp + metrics.fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    return precision, recall, f1


def mask_secret(secret: str) -> str:
    """Return a short masked preview for auditing without leaking full secret values."""
    if not secret:
        return ""
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}...{secret[-4:]}"


def export_audit_report(
    output_path: Path,
    rows: list[dict],
    metrics: EvaluationMetrics,
    precision: float,
    recall: float,
    f1: float,
    findings_count: int,
    gt_count: int,
    gt_stats: GroundTruthStats,
    run_started_at: str,
    run_finished_at: str,
    elapsed_seconds: float,
) -> None:
    payload = {
        "summary": {
            "run_started_at_local": run_started_at,
            "run_finished_at_local": run_finished_at,
            "elapsed_seconds": round(elapsed_seconds, 3),
            "regex_llm_hits_processed": findings_count,
            "ground_truth_labeled_keys": gt_count,
            "ground_truth_labeled_rows": gt_stats.labeled_rows,
            "ground_truth_ignored_rows": gt_stats.ignored_rows,
            "ground_truth_conflicts": gt_stats.conflicts,
            "ground_truth_ambiguous_keys": gt_stats.ambiguous_keys,
            "labeled_hits_evaluated": metrics.labeled_hits,
            "unlabeled_hits_skipped": metrics.unlabeled_hits,
            "discarded_false_labels": metrics.discarded_false,
            "tp": metrics.tp,
            "fp": metrics.fp,
            "fn": metrics.fn,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
        },
        "records": rows,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def print_results(
    metrics: EvaluationMetrics,
    precision: float,
    recall: float,
    f1: float,
    findings_count: int,
    gt_count: int,
    gt_stats: GroundTruthStats,
    run_started_at: str,
    run_finished_at: str,
    elapsed_seconds: float,
) -> None:
    print("\nCredData Benchmark Results (Hybrid Scanner + Llama 3/MLX)")
    print("=" * 86)
    print(f"{'Metric':<28} | {'Value':>12}")
    print("-" * 86)
    print(f"{'Run started (Local)':<28} | {run_started_at:>12}")
    print(f"{'Run finished (Local)':<28} | {run_finished_at:>12}")
    print(f"{'Elapsed seconds':<28} | {elapsed_seconds:>12.3f}")
    print("-" * 86)
    print(f"{'Regex+LLM hits processed':<28} | {findings_count:>12}")
    print(f"{'Ground-truth labeled keys':<28} | {gt_count:>12}")
    print(f"{'Ground-truth labeled rows':<28} | {gt_stats.labeled_rows:>12}")
    print(f"{'Ground-truth ignored rows':<28} | {gt_stats.ignored_rows:>12}")
    print(f"{'Ground-truth conflicts':<28} | {gt_stats.conflicts:>12}")
    print(f"{'Ground-truth ambiguous keys':<28} | {gt_stats.ambiguous_keys:>12}")
    print(f"{'Labeled hits evaluated':<28} | {metrics.labeled_hits:>12}")
    print(f"{'Unlabeled hits skipped':<28} | {metrics.unlabeled_hits:>12}")
    print(f"{'Discarded true-F labels':<28} | {metrics.discarded_false:>12}")
    print("-" * 86)
    print(f"{'True Positives (TP)':<28} | {metrics.tp:>12}")
    print(f"{'False Positives (FP)':<28} | {metrics.fp:>12}")
    print(f"{'False Negatives (FN)':<28} | {metrics.fn:>12}")
    print("-" * 86)
    print(f"{'Precision':<28} | {precision:>12.4f}")
    print(f"{'Recall':<28} | {recall:>12.4f}")
    print(f"{'F1 Score':<28} | {f1:>12.4f}")
    print("=" * 86)


async def run_creddata_benchmark(
    creddata_root: Path,
    data_root: Path,
    meta_root: Path,
    audit_output: Path | None,
    max_hits: int | None = None,
) -> None:
    run_started_at = local_now_iso()
    t0 = perf_counter()

    project_root = Path(__file__).resolve().parent
    backend_dir = project_root / "backend"

    # Enable imports like `from src.scanner import run_pipeline`.
    sys.path.insert(0, str(backend_dir))

    # Ensure MLX adapter path resolves regardless of invocation directory.
    os.environ.setdefault("LLM_ADAPTER_PATH", str(backend_dir / "adapters"))

    from src.scanner import run_pipeline  # Imported after sys.path setup.

    if not creddata_root.exists():
        raise FileNotFoundError(f"CredData root not found: {creddata_root}")
    if not data_root.exists():
        raise FileNotFoundError(f"CredData data directory not found: {data_root}")
    if not meta_root.exists():
        raise FileNotFoundError(f"CredData meta directory not found: {meta_root}")

    print(f"Loading ground truth from: {meta_root}")
    gt_map, gt_stats = build_ground_truth(meta_root)
    print(f"Loaded {len(gt_map)} labeled (path,line) keys from metadata.")

    print(f"Scanning data directory: {data_root}")
    try:
        findings = await run_pipeline(data_root, max_hits=max_hits)
    except KeyboardInterrupt:
        print("\n[!] Ctrl+C received while scanning. Exiting gracefully without traceback.")
        return

    metrics = EvaluationMetrics()
    audit_rows: list[dict] = []
    processed_count = 0

    for candidate, verdict in findings:
        if max_hits is not None and processed_count >= max_hits:
            print(f"\n[!] Reached max-hits limit of {max_hits}. Halting evaluation.")
            break

        processed_count += 1
        case_logged_at = local_now_iso()

        try:
            key_path = to_meta_style_path(candidate.file_path, creddata_root)
        except ValueError:
            # Scanner returned a path outside CredData root.
            metrics.unlabeled_hits += 1
            audit_rows.append(
                {
                    "path": str(Path(candidate.file_path).as_posix()),
                    "line": int(candidate.line_number),
                    "category": candidate.secret_category,
                    "secret_preview": mask_secret(candidate.raw_secret),
                    "logged_at_local": case_logged_at,
                    "gt_label": None,
                    "llm_is_genuine_secret": bool(verdict.is_genuine_secret),
                    "confidence_score": verdict.confidence_score,
                    "reasoning": verdict.reasoning,
                    "evaluation": "UNLABELED",
                }
            )
            continue

        key = make_key(key_path, candidate.line_number)
        gt_label = gt_map.get(key)

        if gt_label not in VALID_LABELS:
            metrics.unlabeled_hits += 1
            audit_rows.append(
                {
                    "path": key_path,
                    "line": int(candidate.line_number),
                    "category": candidate.secret_category,
                    "secret_preview": mask_secret(candidate.raw_secret),
                    "logged_at_local": case_logged_at,
                    "gt_label": None,
                    "llm_is_genuine_secret": bool(verdict.is_genuine_secret),
                    "confidence_score": verdict.confidence_score,
                    "reasoning": verdict.reasoning,
                    "evaluation": "UNLABELED",
                }
            )
            continue

        metrics.labeled_hits += 1
        evaluation = "TN"

        if verdict.is_genuine_secret and gt_label == "T":
            metrics.tp += 1
            evaluation = "TP"
        elif verdict.is_genuine_secret and gt_label == "F":
            metrics.fp += 1
            evaluation = "FP"
        elif (not verdict.is_genuine_secret) and gt_label == "T":
            metrics.fn += 1
            evaluation = "FN"
        elif (not verdict.is_genuine_secret) and gt_label == "F":
            metrics.discarded_false += 1
            evaluation = "TN"

        audit_rows.append(
            {
                "path": key_path,
                "line": int(candidate.line_number),
                "category": candidate.secret_category,
                "secret_preview": mask_secret(candidate.raw_secret),
                "logged_at_local": case_logged_at,
                "gt_label": gt_label,
                "llm_is_genuine_secret": bool(verdict.is_genuine_secret),
                "confidence_score": verdict.confidence_score,
                "reasoning": verdict.reasoning,
                "evaluation": evaluation,
            }
        )

    precision, recall, f1 = compute_metrics(metrics)
    run_finished_at = local_now_iso()
    elapsed_seconds = perf_counter() - t0
    print_results(
        metrics,
        precision,
        recall,
        f1,
        processed_count,
        len(gt_map),
        gt_stats,
        run_started_at,
        run_finished_at,
        elapsed_seconds,
    )

    if max_hits is not None and processed_count < len(findings):
        print(f"Stopped early due to --max-hits={max_hits}.")

    if audit_output is not None:
        export_audit_report(
            output_path=audit_output,
            rows=audit_rows,
            metrics=metrics,
            precision=precision,
            recall=recall,
            f1=f1,
            findings_count=processed_count,
            gt_count=len(gt_map),
            gt_stats=gt_stats,
            run_started_at=run_started_at,
            run_finished_at=run_finished_at,
            elapsed_seconds=elapsed_seconds,
        )
        print(f"Audit report exported to: {audit_output}")


def parse_args() -> argparse.Namespace:
    default_root = Path("/Users/dinanath/Documents/CredData")
    parser = argparse.ArgumentParser(
        description="Run Hybrid Secret Scanner on CredData and evaluate against T/F metadata labels."
    )
    parser.add_argument(
        "--creddata-root",
        type=Path,
        default=default_root,
        help="Path to CredData root directory.",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=default_root / "data",
        help="Path to CredData data directory.",
    )
    parser.add_argument(
        "--meta-root",
        type=Path,
        default=default_root / "meta",
        help="Path to CredData metadata directory.",
    )
    parser.add_argument(
        "--audit-output",
        type=Path,
        default=Path("reports/creddata_benchmark_audit.json"),
        help="Path for JSON audit export.",
    )
    parser.add_argument(
        "--no-audit",
        action="store_true",
        help="Disable JSON audit export.",
    )
    parser.add_argument(
        "--max-hits",
        type=int,
        default=None,
        help="Maximum number of regex+LLM hits to process. Default: process all hits.",
    )
    args = parser.parse_args()
    if args.max_hits is not None and args.max_hits <= 0:
        parser.error("--max-hits must be a positive integer.")
    return args


def main() -> None:
    args = parse_args()
    audit_output = None if args.no_audit else args.audit_output
    try:
        asyncio.run(
            run_creddata_benchmark(
                args.creddata_root,
                args.data_root,
                args.meta_root,
                audit_output,
                args.max_hits,
            )
        )
    except KeyboardInterrupt:
        print("\n[!] Benchmark interrupted by user (Ctrl+C). Exiting gracefully.")


if __name__ == "__main__":
    main()
