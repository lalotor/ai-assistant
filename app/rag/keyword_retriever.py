import re
import structlog

# Get logger for this module
logger = structlog.get_logger(__name__)

def keyword_search(chunks, query):
    """Rank chunks by term overlap, preserving split code context when needed.

    Mixed-case, uppercase, and numeric query identifiers carry extra weight,
    and matching implementation code ranks ahead of tests.
    For a matching code chunk, append its immediate same-source successor when
    the successor has no query-term match of its own.
    """
    results = []

    query_tokens = re.findall(r"\b[\w]+\b", query)
    query_terms = [token.lower() for token in query_tokens]
    identifier_terms = {
        token.lower()
        for token in query_tokens
        if (
            any(char.isupper() for char in token[1:])
            or (
                any(char.isdigit() for char in token)
                and any(char.isalpha() for char in token)
            )
            or (len(token) > 1 and token.isupper())
        )
    }

    for index, chunk in enumerate(chunks):
        content = chunk.page_content
        searchable_content = content.lower()
        score = sum(
            4 if term in identifier_terms else 1
            for term in query_terms
            if term in searchable_content
        )
        source = chunk.metadata.get("source")
        file_type = chunk.metadata.get("file_type")
        source_parts = (source or "").lower().split("/")
        is_test_source = any(part in {"test", "tests"} for part in source_parts)
        if source_parts and source_parts[-1].startswith("test_"):
            is_test_source = True
        if score and file_type in {".py", ".js", ".java", ".tf"} and not is_test_source:
            score += 2

        if (
            score
            and file_type in {".py", ".js", ".java", ".tf"}
            and index + 1 < len(chunks)
            and not any(
                term in chunks[index + 1].page_content.lower()
                for term in query_terms
            )
            and source
            and chunks[index + 1].metadata.get("source") == source
        ):
            content = f"{content}\n{chunks[index + 1].page_content}"

        if score > 0:
            logger.debug(
                "found_document_by_keyword",
                source=source or "unknown",
                file_type=file_type or "unknown",
                content_length=len(content),
                score=score
            )
            results.append({
                "content": content,
                "source": source or "unknown",
                "file_type": file_type or "unknown",
                "score": score,
                "search_type": "keyword"
            })

    results.sort(
        reverse=True,
        key=lambda x: x["score"]
    )

    logger.debug(
        "keyword_search",
        result_count=min(len(results), 4)
    )

    return results[:4]
