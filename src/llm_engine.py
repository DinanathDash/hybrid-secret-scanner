import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from .models import CandidateSecret, LLMResponse

# We'll use Llama-3-8B (or any small fast model you have in Ollama)
llm = ChatOllama(model="llama3", temperature=0.1, timeout=15)
parser = PydanticOutputParser(pydantic_object=LLMResponse)

prompt_template = ChatPromptTemplate.from_messages([
    ("system", "You are an expert security engineer. Evaluate the following code snippet. Determine if the redacted variable represents a genuine, high-risk leaked secret, or a safe dummy/test value.\n{format_instructions}"),
    ("human", "Variable Name: {variable_name}\nSecret Category: {category}\n\nCode Context:\n{context}")
])

chain = prompt_template | llm | parser

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def _invoke_llm_with_retry(candidate: CandidateSecret) -> LLMResponse:
    """Internal function wrapped with Tenacity to handle timeouts and JSON parse errors."""
    return await chain.ainvoke({
        "variable_name": candidate.variable_name,
        "category": candidate.secret_category,
        "context": candidate.sanitized_context,
        "format_instructions": parser.get_format_instructions()
    })

async def evaluate_candidate(candidate: CandidateSecret) -> LLMResponse:
    """Evaluates the candidate secret with a graceful degradation fail-safe."""
    try:
        response = await _invoke_llm_with_retry(candidate)
        return response
    except Exception as e:
        logging.warning(f"LLM validation failed for {candidate.file_path.name}:{candidate.line_number}. Defaulting to manual review. Error: {str(e)}")
        # Graceful Degradation (Phase 8.1 & 8.2)
        return LLMResponse(
            is_genuine_secret=True,
            confidence_score=0.0,
            remediation_priority="MANUAL_REVIEW_REQUIRED",
            reasoning="LLM Inference failed or timed out. Defaulting to safe assumption."
        )