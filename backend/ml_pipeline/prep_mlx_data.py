import json
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from cli_runtime import run_cli


def main():
    # Get the directory of the current script
    script_dir = Path(__file__).parent

    # 1. Create the directory MLX expects
    mlx_dataset_dir = script_dir / "mlx_dataset"
    os.makedirs(mlx_dataset_dir, exist_ok=True)

    alpaca_prompt = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
{}

### Input:
{}

### Response:
{}<|eot_id|>"""  # Llama 3's specific End-Of-Turn token

    print("Converting dataset for Apple MLX...")
    output_data = []

    # 2. Read your pristine dataset
    master_file = script_dir / "qlora_dataset_master.jsonl"
    with open(master_file, encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            # Format it into the single text block MLX loves
            formatted_text = alpaca_prompt.format(
                data["instruction"],
                data["input"],
                data["output"],
            )
            output_data.append({"text": formatted_text})

    # 3. Save it to the MLX folder
    train_file = mlx_dataset_dir / "train.jsonl"
    with open(train_file, "w", encoding="utf-8") as f:
        for item in output_data:
            f.write(json.dumps(item) + "\n")

    print(f"Success! {len(output_data)} rows formatted and saved to {train_file}")


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
