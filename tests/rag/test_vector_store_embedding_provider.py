import json

import pytest

from app.rag.vector_store import (
    initialize_vector_store,
    save_vector_store,
)

OPENAI_CONFIG = {
    "provider": "openai",
    "model": "text-embedding-3-small",
}


@pytest.mark.unit
def test_existing_store_with_different_embedding_config_is_rebuilt(
    tmp_path, mocker, monkeypatch
):
    vector_store_path = tmp_path / "vector_store"
    vector_store_path.mkdir()
    (vector_store_path / "embedding_config.json").write_text(
        json.dumps({"provider": "gemini", "model": "gemini-test-model"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.rag.vector_store.VECTOR_STORE_PATH", str(vector_store_path))
    monkeypatch.setattr(
        "app.rag.vector_store.get_embedding_config",
        lambda: OPENAI_CONFIG,
    )
    built_store = mocker.Mock()
    build_store = mocker.patch(
        "app.rag.vector_store.build_vector_store_from_documents",
        return_value=built_store,
    )
    save_store = mocker.patch("app.rag.vector_store.save_vector_store")
    load_store = mocker.patch("app.rag.vector_store.FAISS.load_local")

    result = initialize_vector_store()

    assert result is built_store
    build_store.assert_called_once()
    save_store.assert_called_once_with(built_store)
    load_store.assert_not_called()


@pytest.mark.unit
def test_legacy_openai_store_is_loaded_and_marked_for_future_provider_checks(
    tmp_path, mocker, monkeypatch
):
    vector_store_path = tmp_path / "vector_store"
    vector_store_path.mkdir()
    monkeypatch.setattr("app.rag.vector_store.VECTOR_STORE_PATH", str(vector_store_path))
    monkeypatch.setattr(
        "app.rag.vector_store.get_embedding_config",
        lambda: OPENAI_CONFIG,
    )
    monkeypatch.setattr("app.rag.vector_store.get_embeddings", lambda: object())
    loaded_store = mocker.Mock()
    mocker.patch(
        "app.rag.vector_store.FAISS.load_local",
        return_value=loaded_store,
    )

    result = initialize_vector_store()

    assert result is loaded_store
    assert json.loads(
        (vector_store_path / "embedding_config.json").read_text(encoding="utf-8")
    ) == OPENAI_CONFIG


@pytest.mark.unit
def test_saving_store_persists_embedding_provider_metadata(
    tmp_path, mocker, monkeypatch
):
    monkeypatch.setattr("app.rag.vector_store.VECTOR_STORE_PATH", str(tmp_path / "index"))
    monkeypatch.setattr(
        "app.rag.vector_store.get_embedding_config",
        lambda: OPENAI_CONFIG,
    )
    vector_store = mocker.Mock()

    save_vector_store(vector_store)

    vector_store.save_local.assert_called_once_with(str(tmp_path / "index"))
    assert json.loads(
        (tmp_path / "index" / "embedding_config.json").read_text(encoding="utf-8")
    ) == OPENAI_CONFIG
