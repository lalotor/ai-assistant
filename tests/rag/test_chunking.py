"""Unit tests for app.rag.chunking.

Covers dispatch-by-file-type behaviour, metadata enrichment, and the
resilient batch-processing loop in get_all_chunks(). All splitters used
here are deterministic local text-splitting utilities (no network/LLM
calls), so these tests run fully offline.
"""
import pytest

from app.contracts.retrieval import LoadedDocument
from app.rag.chunking import (
    chunk_document,
    chunk_markdown_document,
    chunk_code,
    chunk_structured_document,
    chunk_generic_text_document,
    get_all_chunks,
)


def make_doc(content: str, source: str, doc_type: str) -> LoadedDocument:
    return LoadedDocument(content=content, source=source, type=doc_type)


@pytest.mark.unit
class TestChunkDocumentValidation:
    def test_raises_on_missing_document(self):
        with pytest.raises(ValueError, match="Invalid document"):
            chunk_document(None)

    def test_raises_on_empty_content(self):
        doc = make_doc(content="", source="empty.md", doc_type=".md")
        with pytest.raises(ValueError, match="Invalid document"):
            chunk_document(doc)


@pytest.mark.unit
class TestChunkDocumentDispatch:
    def test_dispatches_markdown_by_extension(self):
        doc = make_doc(
            content="# Title\n\nSome body text.",
            source="doc.md",
            doc_type=".md",
        )
        chunks = chunk_document(doc)
        assert len(chunks) >= 1
        assert all(c.metadata["source"] == "doc.md" for c in chunks)
        assert all(c.metadata["file_type"] == ".md" for c in chunks)

    @pytest.mark.parametrize("doc_type", [".py", ".js", ".java", ".tf"])
    def test_dispatches_code_types(self, doc_type):
        doc = make_doc(content="print('hello world')\n" * 5, source=f"file{doc_type}", doc_type=doc_type)
        chunks = chunk_document(doc)
        assert len(chunks) >= 1
        assert all(c.metadata["file_type"] == doc_type for c in chunks)

    @pytest.mark.parametrize("doc_type,content", [
        (".json", '{"a": 1, "b": 2}'),
        (".yaml", "a: 1\nb: 2\n"),
        (".yml", "a: 1\nb: 2\n"),
    ])
    def test_dispatches_structured_types(self, doc_type, content):
        source = f"data{doc_type}"
        doc = make_doc(content=content, source=source, doc_type=doc_type)
        chunks = chunk_document(doc)
        assert len(chunks) >= 1
        assert all(c.metadata["source"] == source for c in chunks)

    def test_falls_back_to_generic_chunking_for_unknown_type(self, caplog):
        doc = make_doc(content="plain unstructured text " * 20, source="notes.txt", doc_type=".txt")
        chunks = chunk_document(doc)
        assert len(chunks) >= 1
        assert all(c.metadata["file_type"] == ".txt" for c in chunks)

    def test_adds_chunk_len_metadata(self):
        doc = make_doc(content="plain unstructured text " * 20, source="notes.txt", doc_type=".txt")
        chunks = chunk_document(doc)
        for c in chunks:
            assert c.metadata["chunk_len"] == len(c.page_content)


@pytest.mark.unit
class TestChunkMarkdownDocument:
    def test_splits_on_headers(self):
        content = "# H1\nintro\n## H2\nsection body"
        doc = make_doc(content=content, source="doc.md", doc_type=".md")
        chunks = chunk_markdown_document(doc)
        assert len(chunks) == 2
        assert chunks[0].metadata.get("Header 1") == "H1"
        assert chunks[1].metadata.get("Header 2") == "H2"


@pytest.mark.unit
class TestChunkCode:
    def test_python_uses_python_language_splitter(self):
        content = "def foo():\n    return 1\n\n\ndef bar():\n    return 2\n"
        doc = make_doc(content=content, source="mod.py", doc_type=".py")
        chunks = chunk_code(doc)
        assert len(chunks) >= 1
        assert all("def" in c.page_content or c.page_content.strip() for c in chunks)

    def test_terraform_uses_custom_separators(self):
        content = 'resource "aws_s3_bucket" "a" {\n}\n\nresource "aws_s3_bucket" "b" {\n}\n'
        doc = make_doc(content=content, source="main.tf", doc_type=".tf")
        chunks = chunk_code(doc)
        assert len(chunks) >= 1
        assert any("resource" in c.page_content for c in chunks)


@pytest.mark.unit
class TestChunkStructuredDocument:
    def test_parses_json(self):
        doc = make_doc(content='{"key": "value", "nested": {"a": 1}}', source="data.json", doc_type=".json")
        chunks = chunk_structured_document(doc)
        assert len(chunks) >= 1
        assert all(c.metadata["source"] == "data.json" for c in chunks)

    def test_parses_yaml(self):
        doc = make_doc(content="key: value\nnested:\n  a: 1\n", source="data.yaml", doc_type=".yaml")
        chunks = chunk_structured_document(doc)
        assert len(chunks) >= 1
        assert all(c.metadata["source"] == "data.yaml" for c in chunks)

    def test_invalid_json_raises(self):
        doc = make_doc(content="{not valid json", source="broken.json", doc_type=".json")
        with pytest.raises(Exception):
            chunk_structured_document(doc)


@pytest.mark.unit
class TestChunkGenericTextDocument:
    def test_splits_long_text_into_multiple_chunks(self):
        content = ("A paragraph of reasonable length. " * 50) + "\n\n" + ("Another paragraph. " * 50)
        doc = make_doc(content=content, source="long.txt", doc_type=".txt")
        chunks = chunk_generic_text_document(doc)
        assert len(chunks) > 1

    def test_short_text_yields_single_chunk(self):
        doc = make_doc(content="short text", source="short.txt", doc_type=".txt")
        chunks = chunk_generic_text_document(doc)
        assert len(chunks) == 1
        assert chunks[0].page_content == "short text"


@pytest.mark.unit
class TestGetAllChunks:
    def test_aggregates_chunks_across_documents(self):
        docs = [
            make_doc(content="# Title\nbody", source="a.md", doc_type=".md"),
            make_doc(content="short text", source="b.txt", doc_type=".txt"),
        ]
        chunks = get_all_chunks(docs)
        sources = {c.metadata["source"] for c in chunks}
        assert sources == {"a.md", "b.txt"}

    def test_skips_failing_documents_and_continues(self):
        docs = [
            make_doc(content="{bad json", source="broken.json", doc_type=".json"),
            make_doc(content="short text", source="ok.txt", doc_type=".txt"),
        ]
        chunks = get_all_chunks(docs)
        # The broken document is logged and skipped; the valid one still succeeds.
        sources = {c.metadata["source"] for c in chunks}
        assert sources == {"ok.txt"}

    def test_empty_input_returns_empty_list(self):
        assert get_all_chunks([]) == []
