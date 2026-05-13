import structlog
from app.contracts.tools import CodeInput, CodeOutput
from app.utils.llm import get_llm

# Get logger for this module
logger = structlog.get_logger(__name__)

def code_explainer(code_input: CodeInput) -> CodeOutput:
    """Tool to explain code snippets using an LLM."""
    llm = get_llm()

    # Build the prompt with formatted context
    code_explanation_prompt = f"""
    Explain the following code clearly:
    {code_input.code}

    Guidelines:
    - You are an expert Senior Software Engineer
    - Explain in a clear and detailed way
    - User MarkDown as the formatting language for the answer, and include code snippets if necessary
    """

    logger.info(
        "code_explainer",
        code_snippet=code_input.code,
        prompt_length=len(code_explanation_prompt)
    )

    response = llm.invoke(code_explanation_prompt)

    return CodeOutput(explanation=response.content)
