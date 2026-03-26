import os
import sys
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import TrainingArguments
from trl import SFTTrainer
from unsloth import FastLanguageModel

sys.path.append(str(Path(__file__).resolve().parent.parent))
from cli_runtime import run_cli


def main():
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

    # 1. Model Configuration (Optimized for 8GB VRAM)
    max_seq_length = 512  # Ultra-tight memory profile
    dtype = None
    load_in_4bit = True  # CRITICAL: This shrinks the 8B model to ~5.7GB

    print("Loading Llama-3 8B Instruct model...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/llama-3-8b-Instruct-bnb-4bit",
        max_seq_length=max_seq_length,
        dtype=dtype,
        load_in_4bit=load_in_4bit,
    )

    # 2. Attach LoRA Adapters
    model = FastLanguageModel.get_peft_model(
        model,
        r=8,  # <-- CHANGE THIS FROM 16 TO 8
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        lora_alpha=8,  # <-- CHANGE THIS FROM 16 TO 8
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    # 3. Format the Dataset for the LLM
    alpaca_prompt = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
{}

### Input:
{}

### Response:
{}"""

    eos_token = tokenizer.eos_token

    def formatting_prompts_func(examples):
        instructions = examples["instruction"]
        inputs = examples["input"]
        outputs = examples["output"]
        texts = []
        for instruction, input_text, output in zip(instructions, inputs, outputs):
            text = alpaca_prompt.format(instruction, input_text, output) + eos_token
            texts.append(text)
        return {"text": texts}

    print("Loading and formatting dataset...")
    # Point this to your pristine JSONL dataset
    dataset = load_dataset(
        "json", data_files="ml_pipeline/qlora_dataset_master.jsonl", split="train"
    )
    dataset = dataset.map(formatting_prompts_func, batched=True)

    # 4. Training Engine Setup (Optimized for RTX 4060)
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=max_seq_length,
        dataset_num_proc=2,
        packing=False,
        args=TrainingArguments(
            per_device_train_batch_size=1,  # Keep this low for 8GB VRAM
            gradient_accumulation_steps=8,  # Simulates a batch size of 8
            warmup_steps=5,
            max_steps=60,  # quick sanity run
            num_train_epochs=1,  # one full pass over the dataset
            learning_rate=2e-4,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=10,
            optim="paged_adamw_8bit",  # Uses 8-bit optimizer to save even more VRAM
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=3407,
            output_dir="outputs",
        ),
    )

    # 5. Start Training
    print("Starting QLoRA Fine-Tuning...")
    torch.cuda.empty_cache()
    trainer.train()

    # 6. Save the resulting LoRA Adapter
    model.save_pretrained("secret_detection_lora")
    tokenizer.save_pretrained("secret_detection_lora")
    print("\nSuccess! LoRA adapter saved to 'secret_detection_lora' folder.")


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
