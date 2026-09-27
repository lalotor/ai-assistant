"""Unit tests for the doc_retriever() seam in app.tools.doc_retriever.

doc_retriever(DocInput) -> DocOutput is the only public interface tested
here. Internals (hybrid retrieval, reranking, formatting, index parsing)
are exercised only through this seam, mocked at their system boundaries
(vector store, chunk cache, LLM) so tests stay behavior-focused and
survive internal refactors.
"""
import pytest

from langchain_core.documents import Document

from app.contracts.tools import DocInput


@pytest.mark.unit
class TestDocRetriever:
    def test_returns_context_and_sources_from_reranked_results(self, mocker):
        from app.tools.doc_retriever import doc_retriever

        fake_vector_store = mocker.Mock()
        mocker.patch("app.tools.doc_retriever.get_vector_store", return_value=fake_vector_store)
        mocker.patch(
            "app.tools.doc_retriever.retrieve_context",
            return_value=[
                {"content": "vector chunk", "source": "a.md", "file_type": ".md", "score": 0.1, "search_type": "similarity"},
            ],
        )
        mocker.patch(
            "app.tools.doc_retriever.get_cached_chunks",
            return_value=[Document(page_content="keyword chunk", metadata={"source": "b.md", "file_type": ".md"})],
        )
        mocker.patch(
            "app.tools.doc_retriever.keyword_search",
            return_value=[
                {"content": "keyword chunk", "source": "b.md", "file_type": ".md", "score": 1, "search_type": "keyword"},
            ],
        )

        fake_llm = mocker.Mock()
        fake_llm.invoke.return_value = mocker.Mock(content="0,1", usage_metadata=None)
        mocker.patch("app.tools.doc_retriever.get_llm", return_value=fake_llm)
        mocker.patch("app.tools.doc_retriever.format_prompt", return_value="prompt")

        result = doc_retriever(DocInput(query="what is X?"))

        assert "vector chunk" in result.context
        assert "keyword chunk" in result.context
        assert set(result.sources) == {"a.md", "b.md"}
        assert result.retrieval_trace.vector_results_count == 1
        assert result.retrieval_trace.keyword_results_count == 1
        assert result.retrieval_trace.merged_count == 2
        assert result.retrieval_trace.reranked_count == 2

    def test_does_not_reload_documents_from_disk(self, mocker):
        """Regression test for the fix: doc_retriever must use the chunk
        cache instead of calling load_documents()/get_all_chunks() itself."""
        from app.tools.doc_retriever import doc_retriever

        mocker.patch("app.tools.doc_retriever.get_vector_store", return_value=mocker.Mock())
        mocker.patch("app.tools.doc_retriever.retrieve_context", return_value=[])
        cached_chunks_mock = mocker.patch(
            "app.tools.doc_retriever.get_cached_chunks",
            return_value=[Document(page_content="c", metadata={"source": "a.md"})],
        )
        mocker.patch("app.tools.doc_retriever.keyword_search", return_value=[])
        fake_llm = mocker.Mock()
        fake_llm.invoke.return_value = mocker.Mock(content="", usage_metadata=None)
        mocker.patch("app.tools.doc_retriever.get_llm", return_value=fake_llm)
        mocker.patch("app.tools.doc_retriever.format_prompt", return_value="prompt")
        # If doc_retriever still imported load_documents/get_all_chunks
        # directly, patching them here would be required for the module to
        # even function; their absence from doc_retriever's namespace is
        # itself part of what this test locks in via the passing call below.

        doc_retriever(DocInput(query="anything"))

        cached_chunks_mock.assert_called_once()

    def test_no_relevant_documents_found_returns_fallback_message(self, mocker):
        from app.tools.doc_retriever import doc_retriever

        mocker.patch("app.tools.doc_retriever.get_vector_store", return_value=mocker.Mock())
        mocker.patch("app.tools.doc_retriever.retrieve_context", return_value=[])
        mocker.patch("app.tools.doc_retriever.get_cached_chunks", return_value=[])
        mocker.patch("app.tools.doc_retriever.keyword_search", return_value=[])
        fake_llm = mocker.Mock()
        fake_llm.invoke.return_value = mocker.Mock(content="", usage_metadata=None)
        mocker.patch("app.tools.doc_retriever.get_llm", return_value=fake_llm)
        mocker.patch("app.tools.doc_retriever.format_prompt", return_value="prompt")

        result = doc_retriever(DocInput(query="unmatched query"))

        assert result.sources == []
        assert "No relevant documentation found" in result.context
        # Regression guard: DocOutput.sources and .retrieval_trace are
        # required fields; the fallback path must supply both or
        # construction raises pydantic.ValidationError instead of
        # returning gracefully.
        assert result.retrieval_trace is not None
        assert result.retrieval_trace.query == "unmatched query"


@pytest.mark.unit
class TestDocRetrieverLlmUsage:
    """Week 9: doc_retriever's reranking step is its one LLM call - reported
    as DocOutput.llm_calls=1 and token_usage, distinct from the Planner and
    Reviewer's own calls, and present even on the no-relevant-docs fallback
    path (the reranking call still happened; it just returned no indexes).
    """

    def test_reports_one_llm_call_and_its_token_usage(self, mocker):
        from app.tools.doc_retriever import doc_retriever

        mocker.patch("app.tools.doc_retriever.get_vector_store", return_value=mocker.Mock())
        mocker.patch(
            "app.tools.doc_retriever.retrieve_context",
            return_value=[{"content": "chunk", "source": "a.md", "file_type": ".md", "score": 0.1, "search_type": "similarity"}],
        )
        mocker.patch("app.tools.doc_retriever.get_cached_chunks", return_value=[])
        mocker.patch("app.tools.doc_retriever.keyword_search", return_value=[])
        fake_llm = mocker.Mock()
        fake_llm.model_name = "gpt-5.4-mini"
        fake_llm.invoke.return_value = mocker.Mock(
            content="0",
            usage_metadata={"input_tokens": 300, "output_tokens": 10, "total_tokens": 310},
        )
        mocker.patch("app.tools.doc_retriever.get_llm", return_value=fake_llm)
        mocker.patch("app.tools.doc_retriever.format_prompt", return_value="prompt")

        result = doc_retriever(DocInput(query="what is X?"))

        assert result.llm_calls == 1
        assert result.token_usage == {"input_tokens": 300, "output_tokens": 10, "model": "gpt-5.4-mini"}

    def test_reports_llm_calls_and_none_usage_on_the_no_relevant_docs_fallback(self, mocker):
        """The reranking LLM call still happens even when it returns no
        usable indexes - llm_calls must be 1, not 0, on this path too."""
        from app.tools.doc_retriever import doc_retriever

        mocker.patch("app.tools.doc_retriever.get_vector_store", return_value=mocker.Mock())
        mocker.patch("app.tools.doc_retriever.retrieve_context", return_value=[])
        mocker.patch("app.tools.doc_retriever.get_cached_chunks", return_value=[])
        mocker.patch("app.tools.doc_retriever.keyword_search", return_value=[])
        fake_llm = mocker.Mock()
        fake_llm.invoke.return_value = mocker.Mock(content="", usage_metadata=None)
        mocker.patch("app.tools.doc_retriever.get_llm", return_value=fake_llm)
        mocker.patch("app.tools.doc_retriever.format_prompt", return_value="prompt")

        result = doc_retriever(DocInput(query="unmatched query"))

        assert result.llm_calls == 1
        assert result.token_usage is None
