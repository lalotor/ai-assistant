import structlog
from pydantic import BaseModel

# Get logger for this module
logger = structlog.get_logger(__name__)

class DocInput(BaseModel):
    query: str

class DocOutput(BaseModel):
    context: str

def doc_retriever(doc_input: DocInput) -> DocOutput:
    """Tool to retrieve documentation based on a query."""
    logger.info(
        "doc_retriever",
        query=doc_input.query
    )

    return DocOutput(
        context=f"Mocked documentation context for: {doc_input.query}"
    )
