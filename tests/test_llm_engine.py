import pytest
from unittest.mock import patch
from pathlib import Path

from src.models import CandidateSecret, LLMResponse
from src.llm_engine import evaluate_candidate

@pytest.fixture
def dummy_candidate():
    return CandidateSecret(
        file_path=Path("dummy.py"),
        line_number=10,
        raw_secret="AKIA...",
        secret_category="AWS_ACCESS_KEY",
        entropy=3.5,
        sanitized_context="aws_key = '<REDACTED>'",
        variable_name="aws_key"
    )

@pytest.mark.asyncio
async def test_evaluate_candidate_success(dummy_candidate):
    # Mock a successful LLM response
    mock_response = LLMResponse(
        is_genuine_secret=True,
        confidence_score=0.95,
        remediation_priority="CRITICAL",
        reasoning="Looks like a real AWS key in production code."
    )
    
    with patch('src.llm_engine._invoke_llm_with_retry', return_value=mock_response):
        result = await evaluate_candidate(dummy_candidate)
        
    assert result.is_genuine_secret is True
    assert result.remediation_priority == "CRITICAL"
    assert result.confidence_score == 0.95

@pytest.mark.asyncio
async def test_evaluate_candidate_graceful_degradation(dummy_candidate):
    # Mock a catastrophic failure (e.g., Ollama is offline)
    with patch('src.llm_engine._invoke_llm_with_retry', side_effect=Exception("Connection Refused")):
        result = await evaluate_candidate(dummy_candidate)
        
    # The fail-safe must catch this and return a safe default
    assert result.is_genuine_secret is True
    assert result.confidence_score == 0.0
    assert result.remediation_priority == "MANUAL_REVIEW_REQUIRED"
    assert "LLM Inference failed" in result.reasoning