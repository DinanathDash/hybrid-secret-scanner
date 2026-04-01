import sys
import os
import json
import asyncio
from pathlib import Path

# Add the backend directory to Python path to import scanner components
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

# Explicitly set adapter path so MLX finds it relative to backend
os.environ["LLM_ADAPTER_PATH"] = str(backend_dir / "adapters")

from src.scanner import run_pipeline

async def main():
    target_dir = Path("/Users/dinanath/Documents/scanner-benchmarks/datasets/test_keys")
    output_path = Path("/Users/dinanath/Documents/scanner-benchmarks/hybrid_baseline.json")

    print(f"Scanning target directory: {target_dir}")
    print("Initializing Hybrid Scanner pipeline (Regex -> MLX Llama 3)...")
    
    # Run the existing pipeline from the backend
    findings = await run_pipeline(target_dir)

    results = []
    tp_count = 0
    fp_count = 0

    print(f"Processing {len(findings)} candidates found by regex...")
    
    for candidate, verdict in findings:
        is_true_positive = verdict.is_genuine_secret
        
        if is_true_positive:
            tp_count += 1
        else:
            fp_count += 1
            
        results.append({
            "file": str(candidate.file_path),
            "line": candidate.line_number,
            "secret": candidate.raw_secret,
            "category": candidate.secret_category,
            "is_genuine_secret": is_true_positive,
            "confidence_score": verdict.confidence_score,
            "remediation_priority": verdict.remediation_priority,
            "reasoning": verdict.reasoning
        })

    # Export to JSON
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)
        
    print("\nScan Complete!")
    print("-" * 30)
    print(f"Total Regex Hits Validated: {len(findings)}")
    print(f"LLM Classified True Positives:  {tp_count}")
    print(f"LLM Classified False Positives: {fp_count}")
    print(f"Results successfully saved to: {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
