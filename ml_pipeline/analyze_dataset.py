import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from cli_runtime import run_cli


def analyze_jsonl(file_path: Path):
    true_count = 0
    false_count = 0
    total_count = 0
    sample_entry = None

    print(f"Analyzing {file_path.name}...\n")

    with open(file_path, encoding="utf-8") as f:
        for line in f:
            total_count += 1
            data = json.loads(line)

            # The output field is a stringified JSON, so we need to parse it again
            output_dict = json.loads(data["output"])

            if output_dict.get("is_genuine_secret") is True:
                true_count += 1
            else:
                false_count += 1

            # Grab the very first entry to show as a sample
            if total_count == 1:
                sample_entry = data

    # 1. Print the Balance Stats
    print("-" * 40)
    print("📊 DATASET BALANCE REPORT")
    print("-" * 40)
    print(f"Total Examples:  {total_count:,}")
    print(f"Genuine Secrets: {true_count:,} ({ (true_count/total_count)*100:.1f}% )")
    print(f"False Positives: {false_count:,} ({ (false_count/total_count)*100:.1f}% )")
    print("-" * 40)

    # 2. Print a Sample
    print("\n🔎 SAMPLE ENTRY FORMAT:")
    print("-" * 40)
    print(json.dumps(sample_entry, indent=2))


def main():
    dataset_path = Path(__file__).parent / "qlora_dataset_master.jsonl"

    if dataset_path.exists():
        analyze_jsonl(dataset_path)
    else:
        print("Could not find the dataset. Make sure you are running this from the project root!")


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
