from pathlib import Path

from lingjing_ai.config.settings import AppSettings
from lingjing_ai.rag.embeddings import HashingEmbeddingProvider
from lingjing_ai.rag.generator import ExtractiveAnswerGenerator
from lingjing_ai.rag.pipeline import RagPipeline
from scripts.rebuild_vector_store import rebuild_vector_store
from lingjing_ai.storage.qdrant_vector_store import QdrantVectorStore


def build_pipeline(tmp_path: Path) -> RagPipeline:
    settings = AppSettings.for_workspace(tmp_path)
    vector_store = QdrantVectorStore(
        path=settings.qdrant_db_dir,
        collection_name=settings.vector_collection_name,
        vector_size=settings.embedding_dimensions,
    )
    return RagPipeline(
        settings=settings,
        embedding_provider=HashingEmbeddingProvider(dimensions=settings.embedding_dimensions),
        vector_store=vector_store,
        answer_generator=ExtractiveAnswerGenerator(),
    )


def test_rebuild_vector_store_reindexes_manifest_documents_with_current_embedding(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LJ_EMBEDDING_PROVIDER", "hashing")
    monkeypatch.setenv("LJ_EMBEDDING_DIMENSIONS", "64")
    pipeline = build_pipeline(tmp_path)
    pipeline.ingest_uploaded_text("灵境山资料.md", "灵境山以云海日出和古栈道闻名。")
    pipeline.vector_store.close()

    result = rebuild_vector_store(tmp_path)
    rebuilt_store = QdrantVectorStore(
        path=AppSettings.for_workspace(tmp_path).qdrant_db_dir,
        collection_name=AppSettings.for_workspace(tmp_path).vector_collection_name,
        vector_size=64,
    )
    rebuilt = RagPipeline(
        settings=AppSettings.for_workspace(tmp_path),
        embedding_provider=HashingEmbeddingProvider(dimensions=64),
        vector_store=rebuilt_store,
        answer_generator=ExtractiveAnswerGenerator(),
    )
    answer = rebuilt.ask("灵境山有什么特色？")
    rebuilt.vector_store.close()

    assert result.document_count == 1
    assert result.indexed_chunks == 1
    assert result.collection_name == "lingjing_scenic_knowledge"
    assert result.embedding_dimensions == 64
    assert answer.is_answered is True
    assert "云海日出" in answer.answer


def test_rebuild_vector_store_removes_vectors_missing_from_manifest(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LJ_EMBEDDING_PROVIDER", "hashing")
    monkeypatch.setenv("LJ_EMBEDDING_DIMENSIONS", "64")
    pipeline = build_pipeline(tmp_path)
    pipeline.ingest_uploaded_text("新资料.md", "新资料介绍灵境山云海。")
    pipeline.vector_store.upsert(
        [
            {
                "chunk_id": "stale_chunk",
                "document_id": "stale_doc",
                "document_name": "旧资料.md",
                "content": "旧资料只介绍过时内容。",
                "metadata": {},
                "embedding": [1.0] + ([0.0] * 63),
            }
        ]
    )
    pipeline.vector_store.close()

    result = rebuild_vector_store(tmp_path)
    rebuilt_store = QdrantVectorStore(
        path=AppSettings.for_workspace(tmp_path).qdrant_db_dir,
        collection_name=AppSettings.for_workspace(tmp_path).vector_collection_name,
        vector_size=64,
    )
    records = rebuilt_store.list_records()
    rebuilt_store.close()

    assert result.document_count == 1
    assert {record["document_name"] for record in records} == {"新资料.md"}


def test_rebuild_vector_store_main_reports_when_no_manifest(tmp_path: Path, capsys):
    from scripts.rebuild_vector_store import main

    exit_code = main(["--workspace", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "没有可重建的资料" in captured.out
