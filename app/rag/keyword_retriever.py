import structlog

# Get logger for this module
logger = structlog.get_logger(__name__)

def keyword_search(chunks, query):
    """Simple keyword-based retriever that scores chunks based on the number of query terms they contain."""
    results = []

    query_terms = query.lower().split()

    for chunk in chunks:
        content = chunk.page_content
        score = sum(
            1 for term in query_terms
            if term in content
        )

        if score > 0:
            logger.debug(
                "found_document_by_keyword",
                source=chunk.metadata.get("source", "unknown"),
                file_type=chunk.metadata.get("file_type", "unknown"),
                content_length=len(chunk.page_content),
                score=score
            )
            results.append({
                "content": content,
                "source": chunk.metadata.get("source", "unknown"),
                "file_type": chunk.metadata.get("file_type", "unknown"),
                "score": score,
                "search_type": "keyword"
            })

    results.sort(
        reverse=True,
        key=lambda x: x["score"]
    )

    logger.debug(
        "keyword_search",
        results=[r["content"] for r in results[:4]]
    )

    return results[:4]
