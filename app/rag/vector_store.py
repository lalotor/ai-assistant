import os
import structlog
from pathlib import Path
from typing import Optional
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from app.rag.embeddings import get_embeddings
from app.rag.ingestion import load_documents
from app.rag.chunking import get_all_chunks

# Get logger for this module
logger = structlog.get_logger(__name__)

# Global vector store instance (singleton pattern)
_vector_store: Optional[FAISS] = None

# Cached chunked corpus, shares the vector store's lifecycle: both are
# built from get_all_chunks(load_documents()) and both are invalidated
# together on rebuild_vector_store().
_cached_chunks: Optional[list[Document]] = None

# Resolve the persistence path relative to the project root so it works
# regardless of the working directory the server is launched from.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_VECTOR_STORE_PATH = _PROJECT_ROOT / "data" / "vector_store"

# Allow override via env var; if relative, resolve against project root.
_raw_path = os.getenv("VECTOR_STORE_PATH")
VECTOR_STORE_PATH = str(
    Path(_raw_path) if (_raw_path and Path(_raw_path).is_absolute())
    else (_PROJECT_ROOT / _raw_path if _raw_path else _DEFAULT_VECTOR_STORE_PATH)
)

def get_vector_store() -> FAISS:
    """
    Get or initialize the global vector store instance.

    Returns:
        FAISS: The initialized vector store instance
    """
    global _vector_store

    if _vector_store is None:
        logger.info("vector_store_not_initialized", action="initializing")
        _vector_store = initialize_vector_store()

    return _vector_store

def initialize_vector_store(force_rebuild: bool = False) -> FAISS:
    """
    Initialize the vector store from persistence or build from scratch.
    
    Args:
        force_rebuild: If True, rebuild even if persisted store exists
        
    Returns:
        FAISS: The initialized vector store
    """
    embeddings = get_embeddings()
    vector_store_path = Path(VECTOR_STORE_PATH)

    # Check if persisted vector store exists
    if vector_store_path.exists() and not force_rebuild:
        logger.info(
            "loading_persisted_vector_store",
            path=str(vector_store_path)
        )
        try:
            vector_store = FAISS.load_local(
                str(vector_store_path),
                embeddings,
                allow_dangerous_deserialization=True  # Required for FAISS
            )
            logger.info(
                "vector_store_loaded_successfully",
                path=str(vector_store_path)
            )
            return vector_store
        except Exception as e:
            logger.warning(
                "failed_to_load_persisted_vector_store",
                error=str(e),
                action="rebuilding_from_scratch"
            )

    # Build vector store from scratch
    logger.info("building_vector_store_from_scratch")
    vector_store = build_vector_store_from_documents()

    # Persist the vector store
    save_vector_store(vector_store)

    return vector_store

def _load_and_chunk_documents() -> list[Document]:
    """
    Load all documents from disk and chunk them.

    Shared by build_vector_store_from_documents() (building the FAISS
    index) and get_cached_chunks() (populating the chunk cache), so the
    load+chunk shape isn't duplicated across both call sites.

    Returns:
        list[Document]: The chunked corpus
    """
    logger.info("loading_documents")
    docs = load_documents()

    return get_all_chunks(docs)


def build_vector_store_from_documents() -> FAISS:
    """
    Build a new vector store from all documents in the data directory.

    Returns:
        FAISS: The newly built vector store
    """
    embeddings = get_embeddings()

    all_chunks = _load_and_chunk_documents()

    logger.info(
        "building_vector_store",
        total_chunks=len(all_chunks)
    )

    if not all_chunks:
        raise RuntimeError(
            "No document chunks found. "
            "Ensure the data/docs directory contains files before starting the server. "
            f"Resolved docs path: {_DEFAULT_VECTOR_STORE_PATH.parent / 'docs'}"
        )

    # Build FAISS vector store
    vector_store = FAISS.from_documents(all_chunks, embeddings)

    logger.info(
        "vector_store_built_successfully",
        vector_store=vector_store.__class__.__name__,
    )

    return vector_store

def save_vector_store(vector_store: FAISS) -> None:
    """
    Persist the vector store to disk.

    Args:
        vector_store: The vector store to persist
    """
    vector_store_path = Path(VECTOR_STORE_PATH)
    vector_store_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "saving_vector_store",
        path=str(vector_store_path)
    )

    try:
        vector_store.save_local(str(vector_store_path))
        logger.info(
            "vector_store_saved_successfully",
            path=str(vector_store_path)
        )
    except Exception as e:
        logger.error(
            "failed_to_save_vector_store",
            error=str(e),
            path=str(vector_store_path)
        )

def add_documents_to_vector_store(new_chunks: list) -> None:
    """
    Add new document chunks to the existing vector store.

    Args:
        new_chunks: List of LangChain Document objects to add
    """
    global _vector_store

    vector_store = get_vector_store()

    logger.info(
        "adding_documents_to_vector_store",
        new_chunk_count=len(new_chunks)
    )

    # Add new documents to the vector store
    vector_store.add_documents(new_chunks)

    # Persist the updated vector store
    save_vector_store(vector_store)

    logger.info(
        "documents_added_successfully",
        new_chunk_count=len(new_chunks)
    )


def rebuild_vector_store() -> FAISS:
    """
    Force rebuild the vector store from scratch.

    Returns:
        FAISS: The newly rebuilt vector store
    """
    global _vector_store, _cached_chunks

    logger.info("force_rebuilding_vector_store")
    _vector_store = initialize_vector_store(force_rebuild=True)
    _cached_chunks = None

    return _vector_store


def get_cached_chunks() -> list[Document]:
    """
    Get or build the cached chunked corpus.

    Shares its lifecycle with the vector store: both are built from
    get_all_chunks(load_documents()), and both are invalidated together
    by rebuild_vector_store(). Callers that need the full chunked corpus
    (e.g. keyword search) should use this instead of re-loading and
    re-chunking documents from disk on every call.

    Returns:
        list[Document]: The cached list of document chunks
    """
    global _cached_chunks

    if _cached_chunks is None:
        logger.info("chunk_cache_miss", action="building")
        _cached_chunks = _load_and_chunk_documents()
        logger.info(
            "chunk_cache_built",
            chunk_count=len(_cached_chunks)
        )

    return _cached_chunks
