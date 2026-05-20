import os
import structlog
from pathlib import Path
from typing import Optional
from langchain_community.vectorstores import FAISS
from app.rag.embeddings import get_embeddings
from app.rag.ingestion import load_documents
from app.rag.chunking import get_all_chunks

# Get logger for this module
logger = structlog.get_logger(__name__)

# Global vector store instance (singleton pattern)
_vector_store: Optional[FAISS] = None

# Default persistence path
VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_PATH", "data/vector_store")

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

def build_vector_store_from_documents() -> FAISS:
    """
    Build a new vector store from all documents in the data directory.

    Returns:
        FAISS: The newly built vector store
    """
    embeddings = get_embeddings()

    # Load and chunk all documents
    logger.info("loading_documents_for_vector_store")
    docs = load_documents()

    all_chunks = get_all_chunks(docs)

    logger.info(
        "building_vector_store",
        total_chunks=len(all_chunks)
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
    global _vector_store

    logger.info("force_rebuilding_vector_store")
    _vector_store = initialize_vector_store(force_rebuild=True)

    return _vector_store
