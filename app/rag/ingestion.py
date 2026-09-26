from pathlib import Path
import structlog
from app.contracts.retrieval import LoadedDocument

# Get logger for this module
logger = structlog.get_logger(__name__)

# Resolve the project root once at import time so paths are correct
# regardless of the working directory the server is launched from.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DOCS_PATH = _PROJECT_ROOT / "data" / "docs"


def _relative_source(file: Path) -> str:
    """Return *file*'s path relative to the project root, as a string.

    Sources must be stable across the codebase: the persisted FAISS index
    and evaluation datasets' expected_sources both use paths relative to
    the project root (e.g. "data/docs/foo.py"), so this must match rather
    than producing an absolute path, which would report the same file
    under two different "source" strings depending on which code path
    produced it (a fresh chunk vs. a persisted vector-store entry).

    Falls back to an absolute path if *file* is outside the project root
    (e.g. a caller-supplied path for testing or scripts), since relative_to
    would otherwise raise. Note: this fallback assumes *file* is itself an
    absolute path (true for every current caller: load_documents() is only
    ever invoked without a *path* argument, which resolves to the absolute
    _DEFAULT_DOCS_PATH). If a future caller passes a relative path from a
    different working directory, this could reintroduce the exact
    same-file/different-source-string bug this function was added to fix.
    """
    try:
        return str(file.relative_to(_PROJECT_ROOT))
    except ValueError:
        return str(file)


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
                source=_relative_source(file),
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
