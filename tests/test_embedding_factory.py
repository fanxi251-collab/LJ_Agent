from pathlib import Path

from lingjing_ai.config.settings import AppSettings
from lingjing_ai.rag.embedding_factory import build_embedding_provider
from lingjing_ai.rag.embeddings import AliyunEmbeddingProvider, HashingEmbeddingProvider


def test_embedding_factory_uses_aliyun_when_key_is_configured(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LJAPI_KEY", "test-key")
    monkeypatch.setenv("LJ_EMBEDDING_PROVIDER", "aliyun")
    monkeypatch.setenv("LJ_EMBEDDING_DIMENSIONS", "1024")
    settings = AppSettings.for_workspace(tmp_path)

    provider = build_embedding_provider(settings)

    assert isinstance(provider, AliyunEmbeddingProvider)
    assert provider.model == "text-embedding-v4"
    assert provider.dimensions == 1024


def test_embedding_factory_falls_back_to_hashing_without_api_key(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LJAPI_KEY", raising=False)
    monkeypatch.setenv("LJ_EMBEDDING_PROVIDER", "aliyun")
    settings = AppSettings.for_workspace(tmp_path)

    provider = build_embedding_provider(settings)

    assert isinstance(provider, HashingEmbeddingProvider)
    assert provider.dimensions == settings.embedding_dimensions


def test_embedding_factory_can_force_hashing_provider(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LJAPI_KEY", "test-key")
    monkeypatch.setenv("LJ_EMBEDDING_PROVIDER", "hashing")
    monkeypatch.setenv("LJ_EMBEDDING_DIMENSIONS", "64")
    settings = AppSettings.for_workspace(tmp_path)

    provider = build_embedding_provider(settings)

    assert isinstance(provider, HashingEmbeddingProvider)
    assert provider.dimensions == 64


def test_embedding_factory_uses_key_loaded_from_config_yml(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LJAPI_KEY", raising=False)
    monkeypatch.setenv("LJ_EMBEDDING_PROVIDER", "aliyun")
    (tmp_path / "config.yml").write_text("LJAPI_KEY: key-from-yml\n", encoding="utf-8")
    settings = AppSettings.for_workspace(tmp_path)

    provider = build_embedding_provider(settings)

    assert isinstance(provider, AliyunEmbeddingProvider)
    assert provider.api_key == "key-from-yml"
