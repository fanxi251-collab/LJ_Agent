from pathlib import Path

from lingjing_ai.config.settings import AppSettings
from lingjing_ai.kg.extractor import KnowledgeGraphExtractor
from lingjing_ai.kg.store import DisabledKnowledgeGraphStore
from lingjing_ai.models.rag import SourceChunk
from lingjing_ai.rag.chunker import TextChunk
from lingjing_ai.rag.embeddings import HashingEmbeddingProvider
from lingjing_ai.rag.generator import ExtractiveAnswerGenerator
from lingjing_ai.rag.pipeline import RagPipeline
from lingjing_ai.storage.vector_store import JsonVectorStore


class FakeKnowledgeGraphStore:
    def __init__(self, sources: list[SourceChunk] | None = None) -> None:
        self.sources = sources or []
        self.indexed_document_ids: list[str] = []
        self.cleared_document_ids: list[str] = []
        self.deleted_document_ids: list[str] = []

    def index_chunks(self, chunks) -> None:
        self.indexed_document_ids.extend(sorted({chunk.document_id for chunk in chunks}))

    def search(self, question: str, top_k: int, scenario: str = "") -> list[SourceChunk]:
        return self.sources[:top_k]

    def delete_document(self, document_id: str) -> None:
        self.deleted_document_ids.append(document_id)

    def clear_document(self, document_id: str) -> None:
        self.cleared_document_ids.append(document_id)

    def status(self) -> dict:
        return {"enabled": True, "node_count": 2, "relationship_count": 1, "schema_version": "scenic_v1", "message": "fake"}


def build_pipeline(tmp_path: Path, knowledge_graph=None) -> RagPipeline:
    settings = AppSettings.for_workspace(tmp_path)
    return RagPipeline(
        settings=settings,
        embedding_provider=HashingEmbeddingProvider(dimensions=64),
        vector_store=JsonVectorStore(tmp_path / "vectors.json"),
        answer_generator=ExtractiveAnswerGenerator(),
        knowledge_graph=knowledge_graph,
    )


def test_knowledge_graph_extractor_builds_entities_and_relations_from_chunks():
    chunk = TextChunk(
        id="doc1_chunk_0",
        document_id="doc1",
        document_name="灵山胜境资料.md",
        content=(
            "资料：灵山胜境资料.md / 章节：推荐路线\n"
            "灵山大佛挨着九龙灌浴，步行难度中等。"
            "灵山梵宫附近有观光车站和休息区。"
            "灵山大佛适合老人轻松游览，也适合亲子游客。"
            "玄奘是唐代高僧，与小灵山传说相关。"
            "半日路线建议经过灵山大佛、九龙灌浴、灵山梵宫。"
        ),
        metadata={"section_path": "推荐路线", "category": "游览路线"},
    )

    graph = KnowledgeGraphExtractor().extract([chunk])
    entities = {(entity.name, entity.type) for entity in graph.entities}
    relations = {(relation.source, relation.type, relation.target) for relation in graph.relations}

    assert ("灵山大佛", "景点") in entities
    assert ("九龙灌浴", "景点") in entities
    assert ("观光车站", "设施") in entities
    assert ("老人友好", "标签") in entities
    assert ("亲子", "标签") in entities
    assert ("玄奘", "人物") in entities
    assert ("小灵山传说", "事件") in entities
    assert not any(entity.type == "资料" for entity in graph.entities)
    assert ("灵山大佛", "NEAR", "九龙灌浴") in relations
    assert ("灵山大佛", "SUITABLE_FOR", "老人友好") in relations
    assert ("灵山大佛", "SUITABLE_FOR", "亲子") in relations
    assert ("灵山梵宫", "HAS_FACILITY", "观光车站") in relations
    assert ("灵山梵宫", "HAS_FACILITY", "休息区") in relations
    assert ("半日路线", "PASS_BY", "灵山大佛") in relations
    assert ("玄奘", "PARTICIPATED_IN", "小灵山传说") in relations
    assert ("小灵山传说", "HAPPENED_AT", "灵山大佛") in relations
    assert "资料提及" not in {relation.type for relation in graph.relations}


def test_knowledge_graph_extractor_limits_relations_and_skips_dynamic_information():
    chunk = TextChunk(
        id="doc1_chunk_0",
        document_id="doc1",
        document_name="灵山胜境资料.md",
        content=(
            "灵山大佛挨着九龙灌浴，灵山梵宫附近有观光车站、休息区、厕所和餐厅。"
            "灵山大佛适合老人、儿童、亲子、情侣和摄影游客。"
            "今日天气多云，门票价格为210元，开放时间以公告为准，用户评论很多。"
            + "历史介绍" * 200
        ),
        metadata={"section_path": "推荐路线", "category": "游览路线"},
    )

    graph = KnowledgeGraphExtractor(max_relations_per_chunk=4).extract([chunk])
    entity_names = {entity.name for entity in graph.entities}
    relation_types = {relation.type for relation in graph.relations}

    assert len(graph.relations) <= 4
    assert all(len(relation.evidence) <= 180 for relation in graph.relations)
    assert "天气" not in entity_names
    assert "门票价格" not in entity_names
    assert "开放时间" not in entity_names
    assert "用户评论" not in entity_names
    assert "资料提及" not in relation_types


def test_disabled_knowledge_graph_store_is_safe_noop():
    store = DisabledKnowledgeGraphStore("Neo4j 未配置")
    chunk = TextChunk("c1", "d1", "资料.md", "灵山胜境包含灵山大佛。", {})

    store.index_chunks([chunk])
    store.delete_document("d1")
    results = store.search("灵山大佛", top_k=3)
    status = store.status()

    assert results == []
    assert status["enabled"] is False
    assert "Neo4j 未配置" in status["message"]


def test_pipeline_indexes_and_merges_knowledge_graph_sources(tmp_path: Path):
    kg_source = SourceChunk(
        chunk_id="kg_doc1_chunk_0",
        document_id="doc1",
        document_name="知识图谱",
        content="图谱事实：灵山胜境 适合 老人；灵山胜境 提供服务 观光车。",
        score=0.96,
        metadata={"source_type": "knowledge_graph"},
    )
    graph_store = FakeKnowledgeGraphStore([kg_source])
    pipeline = build_pipeline(tmp_path, graph_store)

    document = pipeline.ingest_uploaded_text("灵山胜境资料.md", "灵山胜境适合老人游览，景区提供观光车服务。")
    sources = pipeline.search_sources("老人游灵山胜境怎么安排？")

    assert graph_store.indexed_document_ids == [document.id]
    assert any(source.metadata.get("source_type") == "knowledge_graph" for source in sources)
    assert sources[0].content.startswith("图谱事实")


def test_pipeline_delete_clears_knowledge_graph_document(tmp_path: Path):
    graph_store = FakeKnowledgeGraphStore()
    pipeline = build_pipeline(tmp_path, graph_store)
    document = pipeline.ingest_uploaded_text("灵山胜境资料.md", "灵山胜境包含灵山大佛。")

    deleted = pipeline.delete_document(document.id)

    assert deleted is True
    assert document.id in graph_store.cleared_document_ids
    assert graph_store.deleted_document_ids == [document.id]
