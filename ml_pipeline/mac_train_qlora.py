import subprocess
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from cli_runtime import run_cli


def run_mlx_lora_training():
    """
    Wrapper script to start Apple MLX QLoRA fine-tuning on macOS.
    This replaces the Unsloth/CUDA dependencies with Apple-Silicon friendly mlx_lm.
    """
    script_dir = Path(__file__).parent
    dataset_dir = script_dir / "mlx_dataset"

    # Check if dataset exists
    if not (dataset_dir / "train.jsonl").exists():
        print(f"Error: Training dataset not found in {dataset_dir}")
        print("Please run 'prep_mlx_data.py' first.")
        sys.exit(1)

    print("Starting MLX QLoRA Fine-tuning for macOS...")

    # We will use the mlx-community 4bit quantized Llama 3 model by default
    # You can change this to any model available on the Hugging Face Hub
    model_id = "mlx-community/Meta-Llama-3-8B-Instruct-4bit"

    # Build command for mlx_lm.lora
    cmd = [
        # Automatically use the venv's mlx_lm.lora if run within the venv
        "mlx_lm.lora",
        "--model",
        model_id,
        "--train",
        "--data",
        str(dataset_dir),
        "--iters",
        "100",  # Quick test run: change to a higher number for real training
        "--batch-size",
        "2",  # Keep low to fit in unified memory
        "--lora-layers",
        "8",  # Number of layers to target (matching original 8)
        "--learning-rate",
        "2e-4",  # Matching original learning rate
    ]

    print(f"Running command: {' '.join(cmd)}")

    try:
        # Run the MLX LoRA training script
        subprocess.run(cmd, check=True)
        print("\nTraining completed successfully! Adapter saved to 'adapters' directory.")
    except subprocess.CalledProcessError as e:
        print(f"\nTraining failed with exit code {e.returncode}")
        print("Make sure you have installed MLX with: pip install mlx mlx-lm")
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("\nError: The 'mlx_lm.lora' command was not found.")
        print("Make sure you are in the mlx_env virtual environment and have installed mlx-lm:")
        print("source mlx_env/bin/activate")
        print("pip install mlx mlx-lm")
        sys.exit(1)


if __name__ == "__main__":
    raise SystemExit(run_cli(run_mlx_lora_training))
