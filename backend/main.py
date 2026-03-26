from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from cli_runtime import run_cli
from src.scanner import run_pipeline


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hybrid Secret Scanner (Regex + MLX LLM validation)")
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Directory to scan (defaults to current working directory).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root_dir = Path(args.target).resolve()

    print("Starting Hybrid Secret Scanner Pipeline...")
    print(f"Target: {root_dir}")

    findings = asyncio.run(run_pipeline(root_dir))

    confirmed = [
        (candidate, verdict)
        for candidate, verdict in findings
        if verdict.remediation_priority in {"CRITICAL", "HIGH", "MEDIUM"}
    ]

    print("\nScan Summary")
    print(f"Total candidates from regex scan: {len(findings)}")
    print(f"Confirmed secrets after AI validation: {len(confirmed)}")

    if confirmed:
        print("\nConfirmed Findings")
        for candidate, verdict in confirmed:
            print(
                f"- {candidate.file_path}:{candidate.line_number} "
                f"[{candidate.secret_category}] Priority={verdict.remediation_priority}"
            )
            print(f"  Reason: {verdict.reasoning}")


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
