import structlog
from app.contracts.tools import CodeInput, CodeOutput
from app.prompts import format_prompt
from app.utils.llm import get_llm

# Get logger for this module
logger = structlog.get_logger(__name__)

def code_explainer(code_input: CodeInput) -> CodeOutput:
    """Tool to explain code snippets using an LLM."""
    llm = get_llm()

    # Build the prompt with formatted context
    code_explanation_prompt = format_prompt(
        "code_explainer.txt",
        code=code_input.code
    )

    logger.info(
        "code_explainer",
        code_snippet=code_input.code,
        prompt_length=len(code_explanation_prompt)
    )

    response = llm.invoke(code_explanation_prompt)

    return CodeOutput(explanation=response.content)
