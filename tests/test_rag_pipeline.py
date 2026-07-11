from pathlib import Path
import json

from lingjing_ai.config.settings import AppSettings
from lingjing_ai.rag.embeddings import HashingEmbeddingProvider
from lingjing_ai.rag.generator import ExtractiveAnswerGenerator
from lingjing_ai.rag.pipeline import RagPipeline
from lingjing_ai.services.conversation import build_conversation_context
from lingjing_ai.services.question_expansion import QwenQuestionExpander
from lingjing_ai.storage.vector_store import JsonVectorStore


class FakeExpansionClient:
    def chat(self, messages):
        return '["灵山胜境五小时游览路线怎么安排", "灵山胜境五小时轻松游览顺序", "灵山胜境五小时核心景点游览路线"]'


def build_pipeline(tmp_path: Path) -> RagPipeline:
    settings = AppSettings.for_workspace(tmp_path)
    return RagPipeline(
        settings=settings,
        embedding_provider=HashingEmbeddingProvider(dimensions=64),
        vector_store=JsonVectorStore(tmp_path / "vectors.json"),
        answer_generator=ExtractiveAnswerGenerator(),
    )


def test_rag_pipeline_answers_from_uploaded_scenic_material(tmp_path: Path):
    pipeline = build_pipeline(tmp_path)
    document_text = """
    灵境山位于青岚湖东岸，以云海日出和古栈道闻名。
    灵境山的核心文化主题是唐代诗路文化，山顶观景台适合拍摄湖光山色。
    游客如果喜欢自然风光，推荐先游览青岚湖，再前往灵境山古栈道。
    """

    document = pipeline.ingest_text("灵境山资料.md", document_text)
    result = pipeline.ask("灵境山有什么特色？")

    assert document.name == "灵境山资料.md"
    assert result.is_answered is True
    assert "云海日出" in result.answer
    assert "古栈道" in result.answer
    assert result.sources[0].document_name == "灵境山资料.md"
    assert result.confidence > 0


def test_rag_pipeline_refuses_when_material_has_no_evidence(tmp_path: Path):
    pipeline = build_pipeline(tmp_path)
    pipeline.ingest_text("灵境山资料.md", "灵境山以云海日出和古栈道闻名。")

    result = pipeline.ask("景区里的熊猫馆开放时间是什么？")

    assert result.is_answered is False
    assert "当前资料中没有查到可靠依据" in result.answer
    assert result.sources == []


def test_rag_pipeline_ingests_file_into_uploaded_data_area(tmp_path: Path):
    pipeline = build_pipeline(tmp_path)
    source = tmp_path / "赛题资料.md"
    source.write_text("青岚湖适合乘船观景，湖畔栈桥是热门拍照点。", encoding="utf-8")

    document = pipeline.ingest_file(source)
    result = pipeline.ask("青岚湖适合做什么？")

    assert Path(document.path).exists()
    assert str(tmp_path / "data" / "uploaded") in document.path
    assert result.is_answered is True
    assert "乘船观景" in result.answer


def test_rag_pipeline_writes_question_answer_log(tmp_path: Path):
    pipeline = build_pipeline(tmp_path)
    pipeline.ingest_text("灵境山资料.md", "灵境山以云海日出和古栈道闻名。")

    result = pipeline.ask("灵境山有什么特色？")
    log_path = tmp_path / "logs" / "qa.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[-1])

    assert record["trace_id"] == result.trace_id
    assert record["question"] == "灵境山有什么特色？"
    assert record["is_answered"] is True
    assert record["retrieval_mode"] == "hybrid"
    assert record["sources"][0]["document_name"] == "灵境山资料.md"


def test_rag_pipeline_uses_expanded_route_question_for_unclear_planning_request(tmp_path: Path):
    pipeline = build_pipeline(tmp_path)
    pipeline.ingest_uploaded_text(
        "灵山胜境路线.md",
        "灵山胜境五小时游览路线建议经过灵山大佛、九龙灌浴、灵山梵宫，并结合观光车和休息区安排。",
    )
    context = build_conversation_context(
        "我览灵山胜境，请帮我规划路线想用五小时游玩时",
        [],
        question_expander=QwenQuestionExpander(FakeExpansionClient(), model_name="qwen3.7-plus"),
    )

    result = pipeline.ask(context.original_question, conversation_context=context)
    record = json.loads((tmp_path / "logs" / "qa.jsonl").read_text(encoding="utf-8").splitlines()[-1])

    assert context.needs_clarification is False
    assert result.is_answered is True
    assert "五小时" in result.answer
    assert "普通游客" in result.answer
    assert record["question"] == "灵山胜境五小时游览路线怎么安排"
