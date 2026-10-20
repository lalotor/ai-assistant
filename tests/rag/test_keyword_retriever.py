import pytest
from langchain_core.documents import Document
from structlog.testing import capture_logs

from app.rag.keyword_retriever import keyword_search


@pytest.mark.unit
def test_keyword_search_does_not_log_document_content():
    private_content = "policy-private-needle-ae35"
    chunks = [
        Document(
            page_content=f"The retry policy contains {private_content}.",
            metadata={"source": "policy.md", "file_type": ".md"},
        )
    ]

    with capture_logs() as logs:
        results = keyword_search(chunks, "retry policy")

    assert results
    assert private_content not in repr(logs)
