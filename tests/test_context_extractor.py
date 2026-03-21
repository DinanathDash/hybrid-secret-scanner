import pytest
from pathlib import Path
from src.models import CandidateSecret
from src.context_extractor import extract_and_redact_context

def test_ast_windowing_and_redaction(tmp_path):
    # Setup: Create a mock python file with a function longer than 40 lines
    code = [
        "def authenticate_aws_system():",
        "    # Initial Setup"
    ]
    # Add 20 lines of dummy code
    code.extend([f"    dummy_var_{i} = {i}" for i in range(20)])
    
    # The secret we want to find (Line 23)
    code.append("    aws_access_key_id = 'AKIAIOSFODNN7EXAMPLE'")
    
    # Add 20 more lines of dummy code
    code.extend([f"    post_var_{i} = {i}" for i in range(20)])
    code.append("    return True")
    
    file_path = tmp_path / "auth.py"
    file_path.write_text("\n".join(code))
    
    candidate = CandidateSecret(
        file_path=file_path,
        line_number=23,
        raw_secret="AKIAIOSFODNN7EXAMPLE",
        secret_category="AWS_ACCESS_KEY",
        entropy=3.4
    )
    
    # Execute Phase 3
    processed = extract_and_redact_context(candidate)
    
    # Assertions
    assert processed.variable_name == "aws_access_key_id"
    assert "AKIAIOSFODNN7EXAMPLE" not in processed.sanitized_context
    assert "<REDACTED_SECRET_LENGTH_20_ENTROPY_3.40>" in processed.sanitized_context
    
    # Verify Windowing: Signature must be kept, and it should be truncated
    assert "def authenticate_aws_system():" in processed.sanitized_context
    assert "[TRUNCATED]" in processed.sanitized_context