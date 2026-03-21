import csv
import json
import random
from pathlib import Path
import sys

# Ensure Python can find our 'src' module from inside the 'ml_pipeline' folder
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.models import CandidateSecret
from src.context_extractor import extract_and_redact_context

def calculate_dummy_entropy(secret: str) -> float:
    # Quick mock entropy for the dataset builder
    return 3.5 if len(set(secret)) > 5 else 0.0

def process_single_csv(csv_path: Path, source_code_dir: Path, dataset: list) -> tuple[int, int]:
    """Processes a single CSV and appends results to the dataset list."""
    skipped = 0
    processed = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            # 1. Clean up the string from the CSV
            file_path_str = row['FilePath'].strip().replace('\\', '/')
            
            # If the CSV hardcoded "data/" at the front, strip it off
            if file_path_str.startswith('data/'):
                file_path_str = file_path_str[5:]
            elif file_path_str.startswith('/data/'):
                file_path_str = file_path_str[6:]
                
            # 2. Smart Path Resolution
            if file_path_str.startswith(csv_path.stem):
                target_file = source_code_dir / file_path_str
            else:
                target_file = source_code_dir / csv_path.stem / file_path_str
                
            if not target_file.exists():
                skipped += 1
                continue
                
            # Safely extract the secret string and category
            raw_secret_str = row.get('Secret') or row.get('Value') or row.get('RawSecret') or ""
            category_str = row.get('Rule') or row.get('Category') or "UNKNOWN"

            # Map Samsung's CSV columns to our DataClass
            candidate = CandidateSecret(
                file_path=target_file,
                line_number=int(row['LineStart']), 
                raw_secret=raw_secret_str,           
                secret_category=category_str,       
                entropy=calculate_dummy_entropy(raw_secret_str)
            )
            
            # THE MISSING LINE: Process using our core logic
            processed_candidate = extract_and_redact_context(candidate)
            
            # Safely extract the truth label
            truth_str = str(row.get('GroundTruth') or row.get('IsSecret') or row.get('Label') or row.get('ground_truth') or 'F').strip().upper()
            is_genuine = truth_str in ['T', 'TRUE', '1']
            
            # Format Expected Output to match our Pydantic Schema
            expected_output = {
                "is_genuine_secret": is_genuine,
                "confidence_score": 0.99 if is_genuine else 0.85,
                "remediation_priority": "CRITICAL" if is_genuine else "SAFE",
                "reasoning": "Context indicates a live, high-risk credential." if is_genuine else "Context indicates a dummy, test, or benign value."
            }
            
            instruction = (
                "You are an expert security engineer. Evaluate the following code snippet. "
                "Determine if the redacted variable represents a genuine, high-risk leaked secret, or a safe dummy/test value."
            )
            
            input_text = f"Variable Name: {processed_candidate.variable_name}\nSecret Category: {processed_candidate.secret_category}\n\nCode Context:\n{processed_candidate.sanitized_context}"
            
            dataset.append({
                "instruction": instruction,
                "input": input_text,
                "output": json.dumps(expected_output)
            })
            processed += 1
            
    return processed, skipped

def build_massive_instruction_dataset(meta_dir: Path, source_code_dir: Path, output_jsonl: Path):
    """Loops through ALL csv files in the meta directory."""
    dataset = []
    total_processed = 0
    total_skipped = 0
    
    csv_files = list(meta_dir.glob("*.csv"))
    print(f"Found {len(csv_files)} CSV files in {meta_dir.name}/. Starting extraction...")
    
    for i, csv_path in enumerate(csv_files, 1):
        # Print progress so you know it hasn't frozen!
        print(f"Processing CSV {i}/{len(csv_files)}: {csv_path.name}...")
        
        processed, skipped = process_single_csv(csv_path, source_code_dir, dataset)
        total_processed += processed
        total_skipped += skipped

    print("Shuffling dataset to prevent training bias...")
    random.shuffle(dataset)
    
    print(f"Writing to {output_jsonl.name}...")
    with open(output_jsonl, 'w', encoding='utf-8') as out_f:
        for item in dataset:
            out_f.write(json.dumps(item) + '\n')
            
    print("-" * 30)
    print("DATASET GENERATION COMPLETE")
    print(f"Total Examples Built: {total_processed}")
    print(f"Total Files Skipped (Missing): {total_skipped}")

if __name__ == "__main__":
    # Your custom paths
    meta_folder = Path(r"E:\hybrid-secret-scanner\resources\meta")
    source_folder = Path(r"E:\hybrid-secret-scanner\resources\data")
    
    # This will generate the JSONL file in the same folder as this script
    output_file = Path(__file__).parent / "qlora_dataset_master.jsonl"
    
    if meta_folder.exists() and source_folder.exists():
        build_massive_instruction_dataset(meta_folder, source_folder, output_file)
    else:
        print(f"Error: Could not find the directories.")
        print(f"Meta exists: {meta_folder.exists()} at {meta_folder}")
        print(f"Data exists: {source_folder.exists()} at {source_folder}")