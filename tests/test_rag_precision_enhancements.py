from pathlib import Path

from lingjing_ai.config.settings import AppSettings
from lingjing_ai.models.rag import SourceChunk
from lingjing_ai.rag.chunker import TextChunker
from lingjing_ai.rag.fact_guard import guard_answer_facts
from lingjing_ai.rag.question_type import classify_question
from lingjing_ai.rag.embeddings import HashingEmbeddingProvider
from lingjing_ai.rag.generator import ExtractiveAnswerGenerator
from lingjing_ai.rag.pipeline import RagPipeline
from lingjing_ai.storage.vector_store import JsonVectorStore


def build_pipeline(tmp_path: Path) -> RagPipeline:
    settings = AppSettings.for_workspace(tmp_path)
    return RagPipeline(
        settings=settings,
        embedding_provider=HashingEmbeddingProvider(dimensions=64),
        vector_store=JsonVectorStore(tmp_path / "vectors.json"),
        answer_generator=ExtractiveAnswerGenerator(),
    )


def test_chunker_preserves_markdown_section_metadata_and_context():
    text = """
    # 灵境山资料

    ## 游览服务

    ### 无障碍服务

    古栈道入口设有休息点，服务中心提供轮椅咨询。
    """

    chunks = TextChunker(chunk_size=120, chunk_overlap=20).split("doc_1", "灵境山资料.md", text)

    assert chunks
    first = chunks[0]
    assert first.metadata["section_path"] == "游览服务 > 无障碍服务"
    assert first.metadata["section_title"] == "无障碍服务"
    assert first.metadata["category"] == "服务设施"
    assert first.metadata["parent_id"] == "doc_1_section_游览服务_无障碍服务"
    assert first.content.startswith("资料：灵境山资料.md / 章节：游览服务 > 无障碍服务")
    assert "古栈道入口设有休息点" in first.content


def test_question_type_classifier_covers_scenic_high_frequency_questions():
    assert classify_question("门票多少钱，有没有老人优惠？").category == "票务价格"
    assert classify_question("今天几点开放，表演几点开始？").category == "开放时间"
    assert classify_question("从停车场怎么安排游览路线？").category == "游览路线"
    assert classify_question("附近有什么餐饮和住宿推荐？").category == "餐饮住宿"
    assert classify_question("游客中心可以租婴儿车吗？").category == "服务设施"


def test_pipeline_compresses_sources_per_document(tmp_path: Path):
    pipeline = build_pipeline(tmp_path)
    document_text = "\n\n".join(
        [
            "游客服务中心提供婴儿车租赁服务。",
            "游客服务中心提供轮椅咨询服务。",
            "游客服务中心提供失物招领服务。",
            "游客服务中心设有母婴室和休息区。",
        ]
    )
    pipeline.ingest_uploaded_text("游客服务.md", document_text)

    sources = pipeline.search_sources("游客服务中心有哪些服务？")

    assert len([source for source in sources if source.document_name == "游客服务.md"]) <= 2


def test_fact_guard_removes_unsupported_high_risk_facts():
    answer = (
        "### 简要回答\n"
        "灵境山成人票为 120 元，开放时间为 8:00-18:00。\n\n"
        "### 详细说明\n"
        "- 资料显示灵境山适合轻松游览。\n\n"
        "### 温馨提示\n"
        "建议提前确认公告。\n\n"
        "依据：灵境山资料.md"
    )
    sources = [
        SourceChunk(
            chunk_id="doc_chunk_0",
            document_id="doc",
            document_name="灵境山资料.md",
            content="资料显示灵境山适合轻松游览，古栈道沿途设有休息点。",
            score=0.9,
        )
    ]

    guarded = guard_answer_facts(answer, sources)

    assert "120 元" not in guarded
    assert "8:00-18:00" not in guarded
    assert "资料中未明确说明" in guarded
    assert guarded.endswith("依据：灵境山资料.md")
