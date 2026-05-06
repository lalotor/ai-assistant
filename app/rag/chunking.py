from pathlib import Path
import structlog
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter, Language
from app.agents.model import LoadedDocument

# Get logger for this module
logger = structlog.get_logger(__name__)

def chunk_markdown_document(doc: LoadedDocument):
    """Chunk a markdown document into sections based on headers and return a list of chunks."""
    logger.debug(
        "chunk_markdown_document", 
        file=doc.source
    )

    # Define which headers to split on and what metadata key to assign them
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]

    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    splits = splitter.split_text(doc.content)

    return splits

def chunk_code(doc: LoadedDocument):
    """Chunk a code document into smaller pieces based on language-specific rules and return a list of chunks."""
    logger.debug(
        "chunk_code", 
        file=doc.source
    )

    lang = Language.PYTHON
    if doc.type == ".js":
        lang = Language.JS
    elif doc.type == ".java":
        lang = Language.JAVA

    python_splitter = RecursiveCharacterTextSplitter.from_language(
        language=lang,
        chunk_size=600,
        chunk_overlap=90
    )

    texts = python_splitter.create_documents([doc.content])

    return texts
