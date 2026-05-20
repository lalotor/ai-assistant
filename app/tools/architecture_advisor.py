import structlog
from app.contracts.tools import ArchInput, ArchOutput
from app.prompts import format_prompt
from app.utils.llm import get_llm

# Get logger for this module
logger = structlog.get_logger(__name__)

def architecture_advisor(arch_input: ArchInput) -> ArchOutput:
    """Tool to provide architecture advice based on a question."""
    llm = get_llm()

    arch_advisor_prompt = format_prompt(
        "architecture_advisor.txt",
        question=arch_input.question
    )

    logger.info(
        "architecture_advisor",
        question=arch_input.question,
        prompt_length=len(arch_advisor_prompt)
    )

    response = llm.invoke(arch_advisor_prompt)

    return ArchOutput(advice=response.content)
