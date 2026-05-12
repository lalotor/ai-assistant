import structlog
import os
from langchain_community.vectorstores import FAISS

# Get logger for this module
logger = structlog.get_logger(__name__)

def build_vector_store(chunks: list, embeddings):
    """Builds a FAISS vector store from a list of LangChain Document objects."""
    logger.info(
        "Building vector store", 
        chunk_count=len(chunks)
    )

    # Use from_documents to automatically handle text + metadata
    vector_store = FAISS.from_documents(chunks, embeddings)

    return vector_store

def retrieve_context(vector_store, query, k=7, score_threshold=None):
    """Retrieves relevant context from the vector store based on a query."""
    if score_threshold is None: 
        score_threshold = float(os.getenv("SIMILARITY_THRESHOLD", "1.2"))

    # similarity_search returns a list of Document objects
    docs_with_scores = vector_store.similarity_search_with_score(query, k=k)

    filtered_docs = []
    for d, score in docs_with_scores:
        logger.debug(
            "retrieved_document",
            source=d.metadata.get("source", "unknown"),
            file_type=d.metadata.get("file_type", "unknown"),
            content_length=len(d.page_content),
            similarity_score=score
        )
        if score < score_threshold:
            filtered_docs.append({
                "content": d.page_content,
                "source": d.metadata.get("source", "unknown"),
                "file_type": d.metadata.get("file_type", "unknown"),
                "similarity_score": score
            })

    return filtered_docs
