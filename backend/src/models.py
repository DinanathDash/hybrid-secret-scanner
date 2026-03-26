from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field


@dataclass
class CandidateSecret:
    file_path: Path
    line_number: int
    raw_secret: str
    secret_category: str
    entropy: float
    sanitized_context: str | None = None
    variable_name: str | None = None


class LLMResponse(BaseModel):
    is_genuine_secret: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    remediation_priority: str = Field(
        pattern="^(CRITICAL|HIGH|MEDIUM|LOW|MANUAL_REVIEW_REQUIRED|SAFE)$"
    )
    reasoning: str
