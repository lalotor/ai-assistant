"""Unit tests for the get_cached_chunks() seam in app.rag.vector_store.

get_cached_chunks() is the public interface introduced to stop
doc_retriever() from re-reading and re-chunking the entire document
corpus from disk on every query. These tests verify the caching
behavior through that public function only — they mock at the system
boundary (file I/O via load_documents) and never reach into private
caching internals.
"""
import pytest

from langchain_core.documents import Document


@pytest.fixture(autouse=True)
def reset_chunk_cache():
    """Ensure each test starts with a clean cache, regardless of test order."""
    from app.rag import vector_store
    vector_store._cached_chunks = None
    yield
    vector_store._cached_chunks = None


@pytest.mark.unit
class TestGetCachedChunks:
    def test_returns_chunks_built_from_documents(self, mocker):
        from app.rag.vector_store import get_cached_chunks
        from app.contracts.retrieval import LoadedDocument

        fake_docs = [LoadedDocument(content="hello", source="a.txt", type=".txt")]
        fake_chunks = [Document(page_content="hello", metadata={"source": "a.txt"})]

        mocker.patch("app.rag.vector_store.load_documents", return_value=fake_docs)
        mocker.patch("app.rag.vector_store.get_all_chunks", return_value=fake_chunks)

        result = get_cached_chunks()

        assert result == fake_chunks

    def test_second_call_does_not_reload_documents(self, mocker):
        """The whole point of the cache: load_documents/get_all_chunks run once, not per call."""
        from app.rag.vector_store import get_cached_chunks
        from app.contracts.retrieval import LoadedDocument

        fake_docs = [LoadedDocument(content="hello", source="a.txt", type=".txt")]
        fake_chunks = [Document(page_content="hello", metadata={"source": "a.txt"})]

        load_mock = mocker.patch("app.rag.vector_store.load_documents", return_value=fake_docs)
        chunk_mock = mocker.patch("app.rag.vector_store.get_all_chunks", return_value=fake_chunks)

        get_cached_chunks()
        get_cached_chunks()

        load_mock.assert_called_once()
        chunk_mock.assert_called_once()

    def test_rebuild_vector_store_invalidates_the_cache(self, mocker):
        """Cache shares the vector store's lifecycle: a rebuild must force a re-chunk."""
        from app.rag.vector_store import get_cached_chunks, rebuild_vector_store
        from app.contracts.retrieval import LoadedDocument

        fake_docs = [LoadedDocument(content="hello", source="a.txt", type=".txt")]
        fake_chunks = [Document(page_content="hello", metadata={"source": "a.txt"})]

        mocker.patch("app.rag.vector_store.load_documents", return_value=fake_docs)
        chunk_mock = mocker.patch("app.rag.vector_store.get_all_chunks", return_value=fake_chunks)
        mocker.patch("app.rag.vector_store.get_embeddings", return_value=object())
        mocker.patch("app.rag.vector_store.save_vector_store")

        fake_vector_store = mocker.Mock()
        from_documents_mock = mocker.patch(
            "app.rag.vector_store.FAISS.from_documents", return_value=fake_vector_store
        )

        get_cached_chunks()
        rebuild_vector_store()
        get_cached_chunks()

        # get_all_chunks is called 3 times: once to warm the cache, once
        # inside rebuild_vector_store's own re-chunking of the FAISS index,
        # and once more to rebuild the cache after invalidation. The
        # invariant under test is that the post-rebuild get_cached_chunks()
        # call did NOT reuse the pre-rebuild cached value.
        assert chunk_mock.call_count == 3
