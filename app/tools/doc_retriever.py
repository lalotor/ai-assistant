import structlog
from app.contracts.tools import DocInput, DocOutput
from app.rag.retriever import retrieve_context
from app.rag.vector_store import get_vector_store

# Get logger for this module
logger = structlog.get_logger(__name__)

def doc_retriever(doc_input: DocInput) -> DocOutput:
    """Tool to retrieve documentation based on a query."""
    logger.info(
        "doc_retriever",
        query=doc_input.query
    )

    vector_store = get_vector_store()
    results = retrieve_context(vector_store, doc_input.query, k=10)

    if not results:
        logger.info(
            "no_relevant_documents_found",
            query=doc_input.query
        )
        return DocOutput(context="No relevant documentation found for this query. The question may be outside the scope of available technical documentation.")

    context = "\n\n".join(
        [f"[{r['source']}]\n{r['content']}" for r in results]
    )

    logger.info(
        "retrieved_context_from_vector_store",
        context=context
    )

    return DocOutput(context=context)
