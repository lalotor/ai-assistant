from pathlib import Path
import structlog
import json
import yaml
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
    Language,
    RecursiveJsonSplitter,
)
from langchain_core.documents import Document
from app.contracts.retrieval import LoadedDocument

# Get logger for this module
logger = structlog.get_logger(__name__)

def chunk_document(doc: LoadedDocument) -> list[Document]:
    """Chunk a document based on its type and return a list of chunks."""
    if not doc or not doc.content:
        raise ValueError("Invalid document: missing content")

    # Markdown documents
    if doc.type == ".md":
        chunks = chunk_markdown_document(doc)
    # Code documents
    elif doc.type in [".py", ".js", ".java", ".tf"]:
        chunks = chunk_code(doc)
    # Structured documents
    elif doc.type in [".json", ".yaml", ".yml"]:
        chunks = chunk_structured_document(doc)
    else:
        # Generic text documents
        logger.warning(
            "Unsupported file type, using generic chunking", 
            file_type=doc.type,
            source=doc.source
        )
        chunks = chunk_generic_text_document(doc)

    for chunk in chunks:
        chunk.metadata.update({
            "source": doc.source,
            "file_type": doc.type,
            "chunk_len": len(chunk.page_content)
      })

    return chunks

def chunk_markdown_document(doc: LoadedDocument) -> list[Document]:
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
    docs = splitter.split_text(doc.content)

    return docs

def chunk_code(doc: LoadedDocument) -> list[Document]:
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

    code_splitter = RecursiveCharacterTextSplitter.from_language(
        language=lang,
        chunk_size=600,
        chunk_overlap=90
    )

    if doc.type == ".tf":
        code_splitter = RecursiveCharacterTextSplitter(
            chunk_size=600,
            chunk_overlap=90,
            separators=["\nresource \"", "\nmodule \"", "\nvariable \"", "\noutput \"", "\n\n", "\n"]
        )

    docs = code_splitter.create_documents([doc.content])

    return docs


def chunk_structured_document(doc: LoadedDocument) -> list[Document]:
    """Chunk a JSON or YAML document into smaller pieces based on structure."""
    logger.debug(
        "chunk_structured_document", 
        file=doc.source
    )

    json_splitter = RecursiveJsonSplitter(max_chunk_size=500)

    # Determine loader based on file extension
    if doc.source.endswith(('.yaml', '.yml')):
        # yaml.safe_load converts YAML string to a Python dict
        structured_data = yaml.safe_load(doc.content)
    else:
        # Default to JSON
        structured_data = json.loads(doc.content)

    # The splitter accepts a list of dicts via the 'texts' parameter
    docs = json_splitter.create_documents(texts=[structured_data])

    # Optional: Ensure metadata from the original doc carries over
    for chunk in docs:
        chunk.metadata["source"] = doc.source

    return docs

def chunk_generic_text_document(doc: LoadedDocument) -> list[Document]:
    """Chunk a generic text document into smaller pieces and return a list of chunks."""
    logger.debug(
        "chunk_generic_text_document",
        file=doc.source
    )

    generic_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    docs = generic_splitter.create_documents([doc.content])

    return docs
