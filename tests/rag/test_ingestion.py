"""Unit tests for the load_documents() seam in app.rag.ingestion.

load_documents(path=None) -> list[LoadedDocument] is the module's only
public interface. Tests use a real temporary directory (file I/O is the
seam's whole purpose, not something to mock away), never a mocked
filesystem.
"""
from pathlib import Path

import pytest

from app.rag.ingestion import load_documents


@pytest.mark.unit
class TestLoadDocuments:
    def test_loads_all_files_with_content_and_type(self, tmp_path):
        (tmp_path / "a.md").write_text("# Hello", encoding="utf-8")
        (tmp_path / "b.py").write_text("print('hi')", encoding="utf-8")

        docs = load_documents(tmp_path)

        assert len(docs) == 2
        by_type = {d.type: d for d in docs}
        assert by_type[".md"].content == "# Hello"
        assert by_type[".py"].content == "print('hi')"

    def test_recurses_into_subdirectories(self, tmp_path):
        nested = tmp_path / "nested"
        nested.mkdir()
        (nested / "c.txt").write_text("nested content", encoding="utf-8")

        docs = load_documents(tmp_path)

        assert len(docs) == 1
        assert docs[0].content == "nested content"

    def test_ignores_directories_themselves(self, tmp_path):
        (tmp_path / "subdir").mkdir()

        docs = load_documents(tmp_path)

        assert docs == []

    def test_empty_directory_returns_empty_list(self, tmp_path):
        assert load_documents(tmp_path) == []

    def test_source_is_relative_to_project_root_not_absolute(self, tmp_path, mocker):
        """Regression test: load_documents previously produced absolute
        paths (str(Path(file)) on an already-absolute rglob result), while
        the persisted FAISS index (and evaluation datasets' expected_sources)
        use paths relative to the project root, e.g. "data/docs/foo.py".
        This mismatch caused the same file to be reported under two
        different 'source' strings depending on whether it came from a
        fresh chunk (absolute) or the persisted vector index (relative),
        breaking source deduplication and evaluation source-matching.

        Simulates a real project root layout: <tmp_path>/data/docs/foo.md,
        with _PROJECT_ROOT pointed at <tmp_path>, so the resulting source
        should be the real relative path "data/docs/foo.md".
        """
        from app.rag import ingestion

        docs_dir = tmp_path / "data" / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "foo.md").write_text("content", encoding="utf-8")

        mocker.patch.object(ingestion, "_PROJECT_ROOT", tmp_path)

        docs = load_documents(docs_dir)

        assert docs[0].source == "data/docs/foo.md"

    def test_source_falls_back_to_absolute_path_outside_project_root(self, tmp_path, mocker):
        """If a caller passes a path outside the project root (e.g. a custom
        docs directory for testing/scripts), relative_to() would raise -
        the function should fall back to an absolute path rather than
        crashing."""
        from app.rag import ingestion

        other_root = tmp_path / "unrelated_project_root"
        other_root.mkdir()
        outside_dir = tmp_path / "outside" / "docs"
        outside_dir.mkdir(parents=True)
        (outside_dir / "foo.md").write_text("content", encoding="utf-8")

        mocker.patch.object(ingestion, "_PROJECT_ROOT", other_root)

        docs = load_documents(outside_dir)

        assert docs[0].source == str(outside_dir / "foo.md")
