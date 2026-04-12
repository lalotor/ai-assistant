import structlog

# Get logger for this module
logger = structlog.get_logger(__name__)

def code_explainer(code_snippet: str, llm: any) -> str:
    """Tool to explain code snippets using an LLM."""
    # Build the prompt with formatted context
    code_explanation_prompt = f"""
    Explain the following code snippet:
    {code_snippet}

    Guidelines:
    - You are an expert Senior Software Engineer
    - Explain in a clear and detailed way
    - User MarkDown as the formatting language for the answer, and include code snippets if necessary
    """

    logger.info(
        "code_explainer",
        code_snippet=code_snippet,
        prompt_length=len(code_explanation_prompt)
    )

    response = llm.invoke(code_explanation_prompt)

    return response.content
