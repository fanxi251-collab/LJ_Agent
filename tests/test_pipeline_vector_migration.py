from pathlib import Path

from lingjing_ai.api.bootstrap import build_pipeline_components
from lingjing_ai.config.settings import AppSettings
from lingjing_ai.rag.embeddings import HashingEmbeddingProvider
from lingjing_ai.rag.generator import ExtractiveAnswerGenerator
from lingjing_ai.rag.pipeline import RagPipeline
from lingjing_ai.storage.qdrant_vector_store import QdrantVectorStore


def test_pipeline_rebuilds_manifest_documents_after_qdrant_dimension_migration(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LJ_EMBEDDING_PROVIDER", "hashing")
    monkeypatch.setenv("LJ_EMBEDDING_DIMENSIONS", "64")
    old_settings = AppSettings.for_workspace(tmp_path)
    old_store = QdrantVectorStore(
        path=old_settings.qdrant_db_dir,
        collection_name=old_settings.vector_collection_name,
        vector_size=old_settings.embedding_dimensions,
    )
    old_pipeline = RagPipeline(
        settings=old_settings,
        embedding_provider=HashingEmbeddingProvider(dimensions=64),
        vector_store=old_store,
        answer_generator=ExtractiveAnswerGenerator(),
    )
    old_pipeline.ingest_uploaded_text("灵境山资料.md", "灵境山以云海日出和古栈道闻名。")
    old_store.close()

    monkeypatch.setenv("LJ_EMBEDDING_DIMENSIONS", "128")
    new_settings = AppSettings.for_workspace(tmp_path)
    pipeline = build_pipeline_components(new_settings)
    result = pipeline.ask("灵境山有什么特色？")

    assert pipeline.vector_store.was_recreated is True
    assert result.is_answered is True
    assert "云海日出" in result.answer
    pipeline.vector_store.close()
