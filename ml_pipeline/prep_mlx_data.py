import json
import os

# 1. Create the directory MLX expects
os.makedirs("mlx_dataset", exist_ok=True)

alpaca_prompt = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
{}

### Input:
{}

### Response:
{}<|eot_id|>""" # Llama 3's specific End-Of-Turn token

print("Converting dataset for Apple MLX...")
output_data = []

# 2. Read your pristine dataset
with open("qlora_dataset_master.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        # Format it into the single text block MLX loves
        formatted_text = alpaca_prompt.format(
            data["instruction"], 
            data["input"], 
            data["output"]
        )
        output_data.append({"text": formatted_text})

# 3. Save it to the MLX folder
with open("mlx_dataset/train.jsonl", "w", encoding="utf-8") as f:
    for item in output_data:
        f.write(json.dumps(item) + "\n")

print(f"Success! {len(output_data)} rows formatted and saved to mlx_dataset/train.jsonl")