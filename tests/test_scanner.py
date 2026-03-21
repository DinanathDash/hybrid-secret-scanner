import pytest
from pathlib import Path
from src.scanner import calculate_shannon_entropy, scan_file_for_secrets, run_pipeline

def test_calculate_shannon_entropy():
    # Low entropy: highly repetitive
    assert calculate_shannon_entropy("AAAAA") == 0.0
    
    # High entropy: highly randomized
    high_entropy = calculate_shannon_entropy("a1B2c3D4e5F6g7H8")
    assert high_entropy > 3.0

@pytest.mark.asyncio
async def test_scan_file_for_secrets(tmp_path):
    test_file = tmp_path / "config.py"
    test_file.write_text(
        "aws_key = 'AKIAIOSFODNN7EXAMPLE'\n"
        "db_url = 'mongodb+srv://admin:pass@cluster.mongodb.net/test'\n"
        "normal_code = 'print(hello)'\n"
    )
    
    secrets = await scan_file_for_secrets(test_file)
    
    assert len(secrets) == 2
    categories = [s.secret_category for s in secrets]
    assert "AWS_ACCESS_KEY" in categories
    assert "DATABASE_URI" in categories
    
    aws_secret = next(s for s in secrets if s.secret_category == "AWS_ACCESS_KEY")
    assert aws_secret.line_number == 1
    assert aws_secret.raw_secret == "AKIAIOSFODNN7EXAMPLE"
    assert aws_secret.entropy > 0.0

@pytest.mark.asyncio
async def test_run_pipeline(tmp_path):
    # Setup: Mix valid files and files that should be ignored by Phase 1
    (tmp_path / "node_modules").mkdir()
    
    # This secret is in an ignored directory, so run_pipeline should NOT find it
    (tmp_path / "node_modules" / "bad.py").write_text("AKIAIOSFODNN7EXAMPLE") 
    
    (tmp_path / "src").mkdir()
    # This secret is in a valid directory, so run_pipeline SHOULD find it
    (tmp_path / "src" / "api.py").write_text("token = 'ghp_123456789012345678901234567890123456'") 
    
    findings = await run_pipeline(tmp_path)
    
    # Assertions
    assert len(findings) == 1
    
    # Unpack the tuple: (CandidateSecret, LLMResponse)
    secret, llm_response = findings[0] 
    
    assert secret.secret_category == "GITHUB_TOKEN"
    assert secret.file_path.name == "api.py"
    
    # We can also verify that the LLM engine was called (even if it fell back to default)
    assert llm_response.is_genuine_secret is True