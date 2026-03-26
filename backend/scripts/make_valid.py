import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from cli_runtime import run_cli


def main():
    print("Splitting dataset...")
    project_root = Path(__file__).resolve().parent.parent
    train_path = project_root / "ml_pipeline" / "mlx_dataset" / "train.jsonl"
    valid_path = project_root / "ml_pipeline" / "mlx_dataset" / "valid.jsonl"

    # 1. Read all 27,458 lines
    with open(train_path, encoding="utf-8") as f:
        lines = f.readlines()

    # 2. Slice the data (Keep 26,958 for training, reserve 500 for validation)
    train_lines = lines[:-500]
    valid_lines = lines[-500:]

    # 3. Overwrite the train file with the slightly smaller version
    with open(train_path, "w", encoding="utf-8") as f:
        f.writelines(train_lines)

    # 4. Create the new validation file
    with open(valid_path, "w", encoding="utf-8") as f:
        f.writelines(valid_lines)

    print(f"Success! {len(train_lines)} rows in train.jsonl")
    print(f"Success! {len(valid_lines)} rows in valid.jsonl")


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
