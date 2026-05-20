import structlog
from app.contracts.tools import DocInput, DocOutput
from app.rag.keyword_retriever import keyword_search
from app.rag.retriever import retrieve_context
from app.rag.vector_store import get_vector_store
from app.rag.ingestion import load_documents
from app.rag.chunking import get_all_chunks
from app.utils.llm import get_llm
from app.prompts import format_prompt

# Get logger for this module
logger = structlog.get_logger(__name__)

def doc_retriever(doc_input: DocInput) -> DocOutput:
    """Tool to retrieve documentation based on a query."""
    logger.info(
        "doc_retriever",
        query=doc_input.query
    )

    results = hybrid_retrieve(doc_input.query)
    reranked_results = rerank_results(doc_input.query, results)
    if not reranked_results:
        logger.info(
            "no_relevant_documents_found",
            query=doc_input.query
        )
        return DocOutput(context="No relevant documentation found for this query. The question may be outside the scope of available technical documentation.")

    context = join_results(reranked_results)

    logger.info(
        "retrieved_context_from_hybrid_search",
        context=context[:500] + "..."
    )

    return DocOutput(context=context)

def hybrid_retrieve(query) -> list[dict]:
    """Combines vector store retrieval with keyword-based retrieval for a more comprehensive set of results."""
    vector_store = get_vector_store()
    vector_results = retrieve_context(vector_store, query, k=10)
    logger.info(
        "hybrid_stage_vector",
        count=len(vector_results),
        sources=[r['source'] for r in vector_results[:5]]
    )

    docs = load_documents()
    all_chunks = get_all_chunks(docs)
    keyword_results = keyword_search(
        all_chunks,
        query
    )
    logger.info(
        "hybrid_stage_keyword",
        count=len(keyword_results),
        sources=[r['source'] for r in keyword_results[:5]]
    )

    combined = []
    seen = set()

    for result in (
        vector_results + keyword_results
    ):
        content = result["content"]

        if content not in seen:
            combined.append(result)
            seen.add(content)

    logger.info(
        "hybrid_stage_merged",
        total_count=len(combined),
        unique_count=len(combined),
        deduped_count=len(vector_results) + len(keyword_results) - len(combined)
    )

    return combined

def rerank_results(query, results) -> list[dict]:
    """Uses the LLM to rerank retrieved results based on relevance to the query."""
    llm = get_llm()

    joined_chunks = join_results(results)

    rerank_prompt = format_prompt(
        "doc_retriever.txt",
        query=query,
        chunks=joined_chunks
    )

    response = llm.invoke(rerank_prompt)
    indexes = parse_indexes(response.content, len(results))
    reranked_results = [results[i] for i in indexes]

    logger.info(
        "hybrid_stage_reranked",
        input_count=len(results),
        output_count=len(reranked_results),
        final_sources=[r['source'] for r in reranked_results],
        selected_indexes=indexes
    )

    return reranked_results

def join_results(results) -> str:
    """Formats the retrieved results into a string for LLM input."""
    return "\n\n".join([
        f"*Index: [{i}]\n*Content: [{r['content']}]\n*Source: [{r['source']}]\n*Search Type: [{r['search_type']}]"
        for i, r in enumerate(results)
    ])

def parse_indexes(llm_response, num_results) -> list[int]:
    """Parses the LLM response to extract the ranked indexes."""
    indexes = llm_response.split(",")

    if not indexes or not all(i.strip().isdigit() for i in indexes):
        logger.info(
            "no_indexes_parsed_from_llm_response",
            response=llm_response
        )
        return []

    valid_indexes = []
    for i in indexes:
        try:
            idx = int(i)
            if 0 <= idx < num_results:
                valid_indexes.append(idx)
            else:
                logger.warning(f"Index {idx} out of bounds for results list of length {num_results}")
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid index value: {i}, error: {e}")

    return valid_indexes
