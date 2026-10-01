import structlog
from datetime import datetime
from app.contracts.tools import DocInput, DocOutput
from app.contracts.trace import RetrievalTrace
from app.rag.keyword_retriever import keyword_search
from app.rag.retriever import retrieve_context
from app.rag.vector_store import get_vector_store, get_cached_chunks
from app.utils.util import calculate_duration_ms
from app.utils.llm import get_llm, extract_usage
from app.prompts import format_prompt

# Get logger for this module
logger = structlog.get_logger(__name__)


def doc_retriever(doc_input: DocInput) -> DocOutput:
    """Tool to retrieve documentation based on a query.

    Runs Hybrid Retrieval (vector search + keyword search, merged and
    reranked by the LLM) and returns the resulting context, sources, and
    a RetrievalTrace. This is the module's only public interface; the
    hybrid-retrieval, reranking, and formatting steps are internal
    implementation details reached only through this function.
    """
    logger.info(
        "doc_retriever",
        query=doc_input.query
    )

    started = datetime.now()
    retrieval_trace = RetrievalTrace(
        query=doc_input.query
    )

    results = _hybrid_retrieve(doc_input.query, retrieval_trace)
    reranked_results, sources, token_usage = _rerank_results(doc_input.query, results, retrieval_trace)
    # Week 9 Session 2b: reranking is skipped (llm_calls=0) when the merged
    # set was <= _TRIVIAL_RERANK_THRESHOLD; otherwise the LLM call always
    # happened (llm_calls=1), whether or not it returned usable indexes.
    llm_calls = 0 if len(results) <= _TRIVIAL_RERANK_THRESHOLD else 1
    if not reranked_results:
        logger.info(
            "no_relevant_documents_found",
            query=doc_input.query
        )
        retrieval_trace.duration_ms = calculate_duration_ms(started, datetime.now())
        return DocOutput(
            context="No relevant documentation found for this query. The question may be outside the scope of available technical documentation.",
            sources=[],
            retrieval_trace=retrieval_trace,
            llm_calls=llm_calls,
            token_usage=token_usage,
        )

    context = _join_results(reranked_results)
    ended = datetime.now()
    retrieval_trace.duration_ms = calculate_duration_ms(started, ended)

    logger.info(
        "retrieved_context_from_hybrid_search",
        context=context[:500] + "...",
        sources=sources
    )

    return DocOutput(
        context=context,
        sources=sources,
        retrieval_trace=retrieval_trace,
        llm_calls=llm_calls,
        token_usage=token_usage,
    )


def _hybrid_retrieve(query: str, retrieval_trace: RetrievalTrace) -> list[dict]:
    """Combines vector store retrieval with keyword-based retrieval for a more comprehensive set of results.

    Uses the cached chunked corpus (app.rag.vector_store.get_cached_chunks)
    for keyword search instead of reloading and re-chunking documents from
    disk on every call.
    """
    vector_started = datetime.now()
    vector_store = get_vector_store()
    vector_results = retrieve_context(vector_store, query, k=10)
    retrieval_trace.vector_search_ms = calculate_duration_ms(vector_started, datetime.now())
    logger.info(
        "hybrid_stage_vector",
        count=len(vector_results),
        sources=[r['source'] for r in vector_results[:5]]
    )

    retrieval_trace.vector_results_count = len(vector_results)

    keyword_started = datetime.now()
    all_chunks = get_cached_chunks()
    keyword_results = keyword_search(
        all_chunks,
        query
    )
    retrieval_trace.keyword_search_ms = calculate_duration_ms(keyword_started, datetime.now())
    logger.info(
        "hybrid_stage_keyword",
        count=len(keyword_results),
        sources=[r['source'] for r in keyword_results[:5]]
    )

    retrieval_trace.keyword_results_count = len(keyword_results)

    merge_started = datetime.now()
    combined = []
    seen = set()

    for result in (
        vector_results + keyword_results
    ):
        content = result["content"]

        if content not in seen:
            combined.append(result)
            seen.add(content)

    retrieval_trace.merge_ms = calculate_duration_ms(merge_started, datetime.now())
    logger.info(
        "hybrid_stage_merged",
        total_count=len(combined),
        unique_count=len(combined),
        deduped_count=len(vector_results) + len(keyword_results) - len(combined)
    )

    retrieval_trace.merged_count = len(combined)

    return combined


# Below this many merged candidates, the LLM reranker has nothing
# meaningful to choose between - its own prompt instructs it to return
# the "best 3" anyway, so a set this small would just come back
# unchanged. Week 9 Session 2b: skip the LLM call entirely in that case,
# since it's pure latency overhead with zero quality trade-off (there's
# nothing to rank away, unlike skipping reranking on a large set would be).
_TRIVIAL_RERANK_THRESHOLD = 3


def _rerank_results(query: str, results: list[dict], retrieval_trace: RetrievalTrace) -> tuple[list[dict], list[str], dict | None]:
    """Uses the LLM to rerank retrieved results based on relevance to the query.

    This is doc_retriever's only possible LLM call (Week 9 Session 1:
    reported via DocOutput.llm_calls by the caller), distinct from the
    Planner's tool-selection call and the Reviewer's review call - a
    Worker dispatching to doc_retriever makes at most 1 LLM call here,
    even though worker_node itself never calls an LLM directly. Week 9
    Session 2b: "at most", not "always exactly" 1 - see
    _TRIVIAL_RERANK_THRESHOLD; a call with <= that many merged results
    makes 0 LLM calls, since there's nothing to rerank.
    """
    rerank_started = datetime.now()

    if len(results) <= _TRIVIAL_RERANK_THRESHOLD:
        final_sources = list(set(r['source'] for r in results))
        retrieval_trace.rerank_ms = calculate_duration_ms(rerank_started, datetime.now())
        retrieval_trace.reranked_count = len(results)
        retrieval_trace.final_sources = final_sources
        logger.info(
            "hybrid_stage_reranked_skipped_trivial",
            input_count=len(results),
            final_sources=final_sources,
        )
        return results, final_sources, None

    llm = get_llm()

    joined_chunks = _join_results(results)

    rerank_prompt = format_prompt(
        "doc_retriever.txt",
        query=query,
        chunks=joined_chunks
    )

    response = llm.invoke(rerank_prompt)
    token_usage = extract_usage(response, model_name=llm.model_name)
    indexes = _parse_indexes(response.content, len(results))
    reranked_results = [results[i] for i in indexes]
    final_sources = list(set(r['source'] for r in reranked_results))

    retrieval_trace.rerank_ms = calculate_duration_ms(rerank_started, datetime.now())

    logger.info(
        "hybrid_stage_reranked",
        input_count=len(results),
        output_count=len(reranked_results),
        final_sources=final_sources,
        selected_indexes=indexes
    )

    retrieval_trace.reranked_count = len(reranked_results)
    retrieval_trace.final_sources = final_sources

    return reranked_results, final_sources, token_usage


def _join_results(results) -> str:
    """Formats the retrieved results into a string for LLM input."""
    return "\n\n".join([
        f"*Index: [{i}]\n*Content: [{r['content']}]\n*Source: [{r['source']}]\n*Search Type: [{r['search_type']}]"
        for i, r in enumerate(results)
    ])


def _parse_indexes(llm_response, num_results) -> list[int]:
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
