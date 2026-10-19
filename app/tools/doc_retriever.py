import structlog
from datetime import datetime
import openai
from app.contracts.tools import DocInput, DocOutput
from app.contracts.retrieval import RetrievalUnavailableError
from app.contracts.trace import RetrievalTrace
from app.rag.keyword_retriever import keyword_search
from app.rag.retriever import retrieve_context
from app.rag.vector_store import get_vector_store, get_cached_chunks
from app.utils.util import calculate_duration_ms
from app.utils.llm import get_llm, extract_usage
from app.prompts import format_prompt

# Get logger for this module
logger = structlog.get_logger(__name__)


# Number of candidates requested from FAISS similarity search. Week 9
# Session 2b considered reducing this from 10 to 5 after the Session 2a
# baseline showed vector search averaging 587ms/call (39% of
# doc_retriever's own time) - but a live 3-run full-dataset eval showed
# no latency improvement (vector_search avg rose to 687ms) and a small
# answer-score dip within normal run-to-run noise, so the change was
# reverted (see evaluation/reports/optimized.md's "Reverted candidate"
# note). Kept at 10: vector search's cost here is dominated by the
# embedding API round-trip, not FAISS's local candidate-count scoring,
# so k isn't the lever this bottleneck needs.
_VECTOR_SEARCH_K = 10
_TRANSIENT_PROVIDER_ERRORS = (
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
    openai.RateLimitError,
)


def _is_transient_status_error(error: openai.APIStatusError) -> bool:
    return error.status_code in {408, 409, 429} or error.status_code >= 500


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
    reranked_results, sources, token_usage, llm_calls = _rerank_results(doc_input.query, results, retrieval_trace)
    limitation = _retrieval_limitation(retrieval_trace)
    if not reranked_results:
        logger.info(
            "no_relevant_documents_found",
            query=doc_input.query
        )
        retrieval_trace.duration_ms = calculate_duration_ms(started, datetime.now())
        context = "No relevant documentation found for this query. The question may be outside the scope of available technical documentation."
        if limitation:
            context = f"{limitation}\n\n{context}"
        return DocOutput(
            context=context,
            sources=[],
            retrieval_trace=retrieval_trace,
            llm_calls=llm_calls,
            token_usage=token_usage,
        )

    context = _join_results(reranked_results)
    if limitation:
        context = f"{limitation}\n\n{context}"
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
    failed_strategies: list[str] = []

    vector_started = datetime.now()
    try:
        vector_store = get_vector_store()
        vector_results = retrieve_context(vector_store, query, k=_VECTOR_SEARCH_K)
    except (*_TRANSIENT_PROVIDER_ERRORS, openai.APIStatusError, OSError, RuntimeError) as exc:
        if isinstance(exc, openai.APIStatusError) and not _is_transient_status_error(exc):
            raise
        vector_results = []
        retrieval_trace.vector_search_status = "failed"
        retrieval_trace.vector_search_error_type = type(exc).__name__
        failed_strategies.append("vector")
        logger.warning(
            "hybrid_stage_vector_failed",
            error_type=type(exc).__name__,
            fallback="keyword",
        )
    else:
        retrieval_trace.vector_search_status = "succeeded"
    retrieval_trace.vector_search_ms = calculate_duration_ms(vector_started, datetime.now())
    logger.info(
        "hybrid_stage_vector",
        count=len(vector_results),
        sources=[r['source'] for r in vector_results[:5]]
    )

    retrieval_trace.vector_results_count = len(vector_results)

    keyword_started = datetime.now()
    try:
        all_chunks = get_cached_chunks()
        keyword_results = keyword_search(all_chunks, query)
    except (OSError, RuntimeError) as exc:
        keyword_results = []
        retrieval_trace.keyword_search_status = "failed"
        retrieval_trace.keyword_search_error_type = type(exc).__name__
        failed_strategies.append("keyword")
        logger.warning(
            "hybrid_stage_keyword_failed",
            error_type=type(exc).__name__,
            fallback="vector",
        )
    else:
        retrieval_trace.keyword_search_status = "succeeded"
    retrieval_trace.keyword_search_ms = calculate_duration_ms(keyword_started, datetime.now())
    logger.info(
        "hybrid_stage_keyword",
        count=len(keyword_results),
        sources=[r['source'] for r in keyword_results[:5]]
    )

    retrieval_trace.keyword_results_count = len(keyword_results)

    if len(failed_strategies) == 2:
        logger.error(
            "hybrid_retrieval_failed",
            vector_error_type=retrieval_trace.vector_search_error_type,
            keyword_error_type=retrieval_trace.keyword_search_error_type,
        )
        raise RetrievalUnavailableError(
            "Both vector and keyword retrieval strategies failed."
        ) from None

    retrieval_trace.fallback_used = bool(failed_strategies)

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


def _rerank_results(query: str, results: list[dict], retrieval_trace: RetrievalTrace) -> tuple[list[dict], list[str], dict | None, int]:
    """Uses the LLM to rerank retrieved results based on relevance to the query.

    Returns (reranked_results, final_sources, token_usage, llm_calls) -
    llm_calls is reported here, at the one place that knows whether the
    LLM was actually invoked, rather than re-derived by the caller from
    the same _TRIVIAL_RERANK_THRESHOLD check (Week 9 Session 2b: a prior
    version of this change checked the threshold in both doc_retriever()
    and here, which was flagged as a Duplicated Code/Shotgun Surgery risk
    in review - a future threshold change would otherwise need both call
    sites updated in lockstep).

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
        final_sources = list(dict.fromkeys(r["source"] for r in results))
        retrieval_trace.rerank_ms = calculate_duration_ms(rerank_started, datetime.now())
        retrieval_trace.reranked_count = len(results)
        retrieval_trace.final_sources = final_sources
        retrieval_trace.rerank_status = "skipped"
        logger.info(
            "hybrid_stage_reranked_skipped_trivial",
            input_count=len(results),
            final_sources=final_sources,
        )
        return results, final_sources, None, 0

    try:
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
        if not indexes:
            retrieval_trace.rerank_error_type = "InvalidRerankerOutput"
            return _fallback_to_merged_order(results, retrieval_trace, rerank_started)

        reranked_results = [results[i] for i in indexes]
        final_sources = list(dict.fromkeys(r["source"] for r in reranked_results))
    except (*_TRANSIENT_PROVIDER_ERRORS, openai.APIStatusError, TimeoutError) as exc:
        if isinstance(exc, openai.APIStatusError) and not _is_transient_status_error(exc):
            raise
        retrieval_trace.rerank_error_type = type(exc).__name__
        logger.warning(
            "hybrid_stage_rerank_failed",
            error_type=type(exc).__name__,
            fallback="merged_order",
        )
        return _fallback_to_merged_order(results, retrieval_trace, rerank_started)

    retrieval_trace.rerank_ms = calculate_duration_ms(rerank_started, datetime.now())
    retrieval_trace.rerank_status = "succeeded"

    logger.info(
        "hybrid_stage_reranked",
        input_count=len(results),
        output_count=len(reranked_results),
        final_sources=final_sources,
        selected_indexes=indexes
    )

    retrieval_trace.reranked_count = len(reranked_results)
    retrieval_trace.final_sources = final_sources

    return reranked_results, final_sources, token_usage, 1


def _fallback_to_merged_order(
    results: list[dict],
    retrieval_trace: RetrievalTrace,
    rerank_started: datetime,
) -> tuple[list[dict], list[str], None, int]:
    """Keep retrieved candidates when reranking cannot provide a usable order."""
    final_sources = list(dict.fromkeys(result["source"] for result in results))
    retrieval_trace.rerank_ms = calculate_duration_ms(rerank_started, datetime.now())
    retrieval_trace.reranked_count = len(results)
    retrieval_trace.final_sources = final_sources
    retrieval_trace.rerank_status = "fallback"
    retrieval_trace.fallback_used = True
    logger.info(
        "hybrid_stage_rerank_fallback",
        candidate_count=len(results),
        final_sources=final_sources,
    )
    return results, final_sources, None, 1


def _retrieval_limitation(retrieval_trace: RetrievalTrace) -> str | None:
    """Describe any unavailable retrieval capability for the answer model."""
    limitations = []
    failed_strategies = [
        strategy
        for strategy, status in (
            ("vector", retrieval_trace.vector_search_status),
            ("keyword", retrieval_trace.keyword_search_status),
        )
        if status == "failed"
    ]
    if failed_strategies:
        available_strategies = [
            strategy
            for strategy, status in (
                ("vector", retrieval_trace.vector_search_status),
                ("keyword", retrieval_trace.keyword_search_status),
            )
            if status == "succeeded"
        ]
        limitations.append(
            f"{', '.join(failed_strategies)} retrieval failed; available evidence came from "
            f"{', '.join(available_strategies)} retrieval"
        )
    if retrieval_trace.rerank_status == "fallback":
        limitations.append("reranking failed and candidates remain in retrieval order")

    if not limitations:
        return None

    return (
        "Retrieval limitation: "
        + "; ".join(limitations)
        + ". Qualify the answer to reflect this limitation."
    )


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
