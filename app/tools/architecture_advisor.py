import structlog
from app.contracts.tools import ArchInput, ArchOutput
from app.utils.llm import get_llm

# Get logger for this module
logger = structlog.get_logger(__name__)

def architecture_advisor(arch_input: ArchInput) -> ArchOutput:
    """Tool to provide architecture advice based on a question."""
    llm = get_llm()

    # Build the prompt with formatted context
    arch_advisor_prompt = f"""
    Answer this question:
    {arch_input.question}

    Guidelines:
    - You are an expert Senior Software Architect
    - Explain in a clear and detailed way
    - User MarkDown as the formatting language for the answer, and include code snippets if necessary
    """

    logger.info(
        "architecture_advisor",
        question=arch_input.question,
        prompt_length=len(arch_advisor_prompt)
    )

    response = llm.invoke(arch_advisor_prompt)

    return ArchOutput(advice=response.content)
