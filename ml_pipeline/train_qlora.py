import torch
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments

# 1. Model Configuration (Optimized for 8GB VRAM)
max_seq_length = 2048 # 2048 is plenty for our 15-line code snippets
dtype = None          
load_in_4bit = True   # CRITICAL: This shrinks the 8B model to ~5.7GB

print("Loading Llama-3 8B Instruct model...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/llama-3-8b-Instruct-bnb-4bit",
    max_seq_length = max_seq_length,
    dtype = dtype,
    load_in_4bit = load_in_4bit,
)

# 2. Attach LoRA Adapters
model = FastLanguageModel.get_peft_model(
    model,
    r = 16, 
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj",],
    lora_alpha = 16,
    lora_dropout = 0, 
    bias = "none",    
    # CRITICAL FOR 8GB VRAM: Unsloth's checkpointing saves massive amounts of memory
    use_gradient_checkpointing = "unsloth", 
    random_state = 3407,
)

# 3. Format the Dataset for the LLM
alpaca_prompt = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
{}

### Input:
{}

### Response:
{}"""

EOS_TOKEN = tokenizer.eos_token 

def formatting_prompts_func(examples):
    instructions = examples["instruction"]
    inputs       = examples["input"]
    outputs      = examples["output"]
    texts = []
    for instruction, input, output in zip(instructions, inputs, outputs):
        text = alpaca_prompt.format(instruction, input, output) + EOS_TOKEN
        texts.append(text)
    return { "text" : texts, }

print("Loading and formatting dataset...")
# Point this to your pristine JSONL dataset
dataset = load_dataset("json", data_files="ml_pipeline/qlora_dataset_master.jsonl", split="train")
dataset = dataset.map(formatting_prompts_func, batched = True)

# 4. Training Engine Setup (Optimized for RTX 4060)
trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text",
    max_seq_length = max_seq_length,
    dataset_num_proc = 2,
    packing = False, 
    args = TrainingArguments(
        per_device_train_batch_size = 2, # Keep this low for 8GB VRAM
        gradient_accumulation_steps = 4, # Simulates a batch size of 8
        warmup_steps = 5,
        max_steps = 60, # UNCOMMENT this to do a quick 5-minute test run to make sure it doesn't crash!
        num_train_epochs = 1, # Does one full pass over your 27,000 examples
        learning_rate = 2e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        logging_steps = 10,
        optim = "adamw_8bit", # Uses 8-bit optimizer to save even more VRAM
        weight_decay = 0.01,
        lr_scheduler_type = "linear",
        seed = 3407,
        output_dir = "outputs",
    ),
)

# 5. Start Training
print("Starting QLoRA Fine-Tuning...")
trainer_stats = trainer.train()

# 6. Save the resulting LoRA Adapter
model.save_pretrained("secret_detection_lora")
tokenizer.save_pretrained("secret_detection_lora")
print("\nSuccess! LoRA adapter saved to 'secret_detection_lora' folder.")