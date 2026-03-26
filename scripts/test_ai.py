import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from cli_runtime import run_cli
from src.config import LLM_ADAPTER_PATH, LLM_DRY_RUN, LLM_MAX_TOKENS, LLM_MODEL_ID


def main():
    if LLM_DRY_RUN:
        print("LLM_DRY_RUN is enabled; skipping model load.")
        return

    from mlx_lm import generate, load

    print("Loading Llama 3 and your Iteration 3000 Adapter...")

    model, tokenizer = load(
        LLM_MODEL_ID,
        adapter_path=LLM_ADAPTER_PATH,
    )

    # Giving it a trick question with fake, local-testing credentials
    prompt = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
Analyze the following code snippet and output a JSON evaluating if it contains a hardcoded secret.

### Input:
import requests

def fetch_local_data():
    # Using dummy credentials for the local dev environment
    api_key = "test_api_key_12345"
    db_password = "password"

    response = requests.get(f"http://localhost:8080/data?key={api_key}")
    return response.json()

### Response:
"""

    print("\nScanning code for secrets...")
    print("-" * 50)

    # Generate the raw response
    raw_response = generate(model, tokenizer, prompt=prompt, max_tokens=LLM_MAX_TOKENS)

    # Chop off the hallucinated logos!
    clean_response = raw_response.split("<|eot_id|>")[0].strip()

    print(clean_response)
    print("-" * 50)


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
