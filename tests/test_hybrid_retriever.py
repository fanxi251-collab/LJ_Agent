from pathlib import Path

from lingjing_ai.config.settings import AppSettings
from lingjing_ai.rag.embeddings import HashingEmbeddingProvider
from lingjing_ai.rag.generator import ExtractiveAnswerGenerator
from lingjing_ai.rag.pipeline import RagPipeline
from lingjing_ai.rag.retriever import HybridRetriever
from lingjing_ai.storage.vector_store import JsonVectorStore


def _record(chunk_id: str, document_name: str, content: str, embedding: list[float]) -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": chunk_id.split("_chunk_")[0],
        "document_name": document_name,
        "content": content,
        "metadata": {"chunk_index": "0"},
        "embedding": embedding,
    }


def _record_with_category(
    chunk_id: str,
    document_name: str,
    content: str,
    category: str,
    embedding: list[float],
) -> dict:
    record = _record(chunk_id, document_name, content, embedding)
    record["metadata"] = {"chunk_index": "0", "category": category}
    return record


def test_hybrid_retriever_keyword_search_matches_precise_scenic_terms(tmp_path: Path):
    store = JsonVectorStore(tmp_path / "vectors.json")
    store.upsert(
        [
            _record("doc_1_chunk_0", "灵境山票价.md", "灵境山成人票价为 80 元，学生可享优惠。", [1.0, 0.0]),
            _record("doc_2_chunk_0", "青岚湖路线.md", "青岚湖适合乘船观景，湖畔栈桥是热门拍照点。", [0.0, 1.0]),
        ]
    )
    retriever = HybridRetriever(
        vector_store=store,
        embedding_provider=HashingEmbeddingProvider(dimensions=2),
        vector_top_k=0,
        keyword_top_k=5,
        rerank_top_k=4,
        rrf_k=60,
    )

    results = retriever.retrieve("灵境山票价是多少？", top_k=1, min_score=0.0)

    assert results[0]["chunk_id"] == "doc_1_chunk_0"
    assert results[0]["score"] > 0


def test_hybrid_retriever_rrf_promotes_records_found_by_both_routes(tmp_path: Path):
    store = JsonVectorStore(tmp_path / "vectors.json")
    store.upsert(
        [
            _record("doc_1_chunk_0", "灵境山资料.md", "灵境山以云海日出和古栈道闻名。", [1.0, 0.0]),
            _record("doc_2_chunk_0", "古城资料.md", "古城夜游项目包含灯光秀和非遗集市。", [0.9, 0.1]),
        ]
    )
    retriever = HybridRetriever(
        vector_store=store,
        embedding_provider=HashingEmbeddingProvider(dimensions=2),
        vector_top_k=2,
        keyword_top_k=2,
        rerank_top_k=4,
        rrf_k=60,
    )

    results = retriever.retrieve("灵境山古栈道", top_k=2, min_score=0.0)

    assert results[0]["chunk_id"] == "doc_1_chunk_0"


def test_hybrid_retriever_boosts_question_category_matching_metadata(tmp_path: Path):
    store = JsonVectorStore(tmp_path / "vectors.json")
    same_content = "灵境山门票相关信息请参考游客服务公告。"
    store.upsert(
        [
            _record_with_category("doc_a_chunk_0", "灵境山广场.md", same_content, "景点介绍", [1.0, 0.0]),
            _record_with_category("doc_b_chunk_0", "灵境山票务.md", same_content, "票务价格", [1.0, 0.0]),
        ]
    )
    retriever = HybridRetriever(
        vector_store=store,
        embedding_provider=HashingEmbeddingProvider(dimensions=2),
        vector_top_k=0,
        keyword_top_k=5,
        rerank_top_k=4,
        rrf_k=60,
    )

    results = retriever.retrieve("灵境山门票多少钱？", top_k=1, min_score=0.0)

    assert results[0]["chunk_id"] == "doc_b_chunk_0"


def test_rag_pipeline_uses_hybrid_retrieval_for_uploaded_documents(tmp_path: Path):
    settings = AppSettings.for_workspace(tmp_path)
    pipeline = RagPipeline(
        settings=settings,
        embedding_provider=HashingEmbeddingProvider(dimensions=64),
        vector_store=JsonVectorStore(tmp_path / "vectors.json"),
        answer_generator=ExtractiveAnswerGenerator(),
    )

    pipeline.ingest_uploaded_text("游客服务.md", "游客服务中心提供婴儿车租赁和失物招领服务。")
    result = pipeline.ask("哪里可以租婴儿车？")

    assert result.is_answered is True
    assert result.sources[0].document_name == "游客服务.md"
    assert "婴儿车租赁" in result.answer
