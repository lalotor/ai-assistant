import structlog
from pathlib import Path
import re

# Get logger for this module
logger = structlog.get_logger(__name__)

PROMPTS_DIR = Path(__file__).parent

def load_prompt(prompt_path: str) -> str:
    """Load a prompt template from the specified path."""
    full_path = PROMPTS_DIR / prompt_path

    if not full_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {full_path}")

    return full_path.read_text(encoding='utf-8').strip()

def format_prompt(prompt_path: str, **kwargs) -> str:
    """Load and format a prompt with provided variables."""

    logger.debug(
        "loading_prompt",
        prompt_path=prompt_path,
        variables=list(kwargs.keys())
    )

    template = load_prompt(prompt_path)

    # Optional: Validate all required variables are provided
    required_vars = set(re.findall(r'\{(\w+)\}', template))
    missing_vars = required_vars - set(kwargs.keys())

    if missing_vars:
        raise ValueError(f"Missing required variables: {missing_vars}")

    return template.format(**kwargs)
