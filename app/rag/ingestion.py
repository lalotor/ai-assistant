from pathlib import Path
import structlog
from app.agents.model import LoadedDocument

# Get logger for this module
logger = structlog.get_logger(__name__)

def load_documents(path="data/docs") -> list[LoadedDocument]:
    """Load documents from the specified directory and return a list of document dicts."""
    logger.debug(
        "load_documents", 
        path=path
    )
    docs = []

    for file in Path(path).rglob("*"):
        if file.is_file():
            content = file.read_text(encoding="utf-8", errors="ignore")
            doc = LoadedDocument(
                content=content,
                source=str(Path(file)),
                type=file.suffix
            )
            logger.debug(
                "loaded_document",
                source=doc.source,
                type=doc.type,
                content_length=len(doc.content)
            )
            docs.append(doc)

    return docs
