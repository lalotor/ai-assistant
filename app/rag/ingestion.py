from pathlib import Path
import structlog
from app.contracts.retrieval import LoadedDocument

# Get logger for this module
logger = structlog.get_logger(__name__)

# Resolve the project root once at import time so paths are correct
# regardless of the working directory the server is launched from.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DOCS_PATH = _PROJECT_ROOT / "data" / "docs"


def load_documents(path: str | Path | None = None) -> list[LoadedDocument]:
    """Load documents from the specified directory and return a list of document dicts.

    If *path* is not supplied the function falls back to the project-root
    ``data/docs`` directory, resolved relative to this file so the path is
    correct regardless of the working directory the process was started from.
    """
    resolved = Path(path) if path else _DEFAULT_DOCS_PATH
    logger.debug(
        "load_documents",
        path=str(resolved)
    )
    docs = []

    for file in resolved.rglob("*"):
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
