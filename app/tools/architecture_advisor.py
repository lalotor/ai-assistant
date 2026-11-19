import structlog
from app.contracts.tools import ArchInput, ArchOutput
from app.prompts import format_prompt
from app.utils.llm import get_llm, extract_model_usage

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
        question_length=len(arch_input.question),
        prompt_length=len(arch_advisor_prompt)
    )

    response = llm.invoke(arch_advisor_prompt)
    token_usage = extract_model_usage(response, model=llm)

    return ArchOutput(advice=response.content, token_usage=token_usage)
