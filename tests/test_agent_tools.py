from pathlib import Path

from lingjing_ai.agent.executor import AgentExecutor
from lingjing_ai.agent.planner import AgentPlanner
from lingjing_ai.config.settings import AppSettings
from lingjing_ai.models.rag import SourceChunk
from lingjing_ai.rag.embeddings import HashingEmbeddingProvider
from lingjing_ai.rag.generator import ExtractiveAnswerGenerator
from lingjing_ai.rag.pipeline import RagPipeline
from lingjing_ai.storage.vector_store import JsonVectorStore
from lingjing_ai.tools.document_search_tool import DocumentSearchTool
from lingjing_ai.tools.kg_search_tool import KnowledgeGraphSearchTool
from lingjing_ai.tools.query_rewrite_tool import QueryRewriteTool
from lingjing_ai.tools.rag_search_tool import RagSearchTool
from lingjing_ai.tools.web_search_tool import WebSearchTool


class ScenarioRecordingKnowledgeGraph:
    def __init__(self) -> None:
        self.scenarios: list[str] = []

    def search(self, question: str, top_k: int, scenario: str = "") -> list[SourceChunk]:
        self.scenarios.append(scenario)
        return [
            SourceChunk(
                chunk_id="kg_1",
                document_id="kg_doc",
                document_name="知识图谱",
                content=f"图谱事实：场景={scenario}",
                score=0.9,
                metadata={"source_type": "knowledge_graph", "scenario": scenario},
            )
        ]

    def status(self) -> dict:
        return {"enabled": True, "schema_version": "scenic_v1", "node_count": 1, "relationship_count": 1, "message": "ok"}


def build_pipeline(tmp_path: Path) -> RagPipeline:
    settings = AppSettings.for_workspace(tmp_path)
    pipeline = RagPipeline(
        settings=settings,
        embedding_provider=HashingEmbeddingProvider(dimensions=64),
        vector_store=JsonVectorStore(tmp_path / "vectors.json"),
        answer_generator=ExtractiveAnswerGenerator(),
    )
    pipeline.ingest_uploaded_text(
        "灵境山资料.md",
        "灵境山适合老人轻松游览，古栈道沿途设有休息点。景区以云海日出和唐代诗路文化闻名。",
    )
    return pipeline


def test_agent_planner_uses_query_rewrite_rag_and_document_tools(tmp_path: Path):
    settings = AppSettings.for_workspace(tmp_path)
    planner = AgentPlanner(settings)

    plan = planner.plan("灵境山适合老人游玩吗？")

    assert plan.question == "灵境山适合老人游玩吗？"
    assert [step.tool_name for step in plan.steps] == [
        "query_rewrite",
        "rag_search",
        "kg_search",
        "document_search",
    ]


def test_agent_planner_skips_kg_search_for_plain_attraction_intro(tmp_path: Path):
    settings = AppSettings.for_workspace(tmp_path)
    planner = AgentPlanner(settings)

    plan = planner.plan("灵境山有什么特色？")

    assert "kg_search" not in [step.tool_name for step in plan.steps]


def test_agent_planner_uses_shared_tool_intent_rules_for_map_questions(tmp_path: Path):
    settings = AppSettings.for_workspace(tmp_path)
    planner = AgentPlanner(settings)

    weather_plan = planner.plan("灵山胜境今日天气如何？")
    route_plan = planner.plan("从无锡站到灵山胜境怎么走？")
    place_plan = planner.plan("灵山胜境停车场在哪里？")

    assert "amap_weather" in [step.tool_name for step in weather_plan.steps]
    assert "amap_route" in [step.tool_name for step in route_plan.steps]
    assert "amap_place_search" in [step.tool_name for step in place_plan.steps]


def test_knowledge_graph_tool_passes_question_scenario(tmp_path: Path):
    pipeline = build_pipeline(tmp_path)
    graph = ScenarioRecordingKnowledgeGraph()
    pipeline.knowledge_graph = graph

    route_result = KnowledgeGraphSearchTool(pipeline).run("老人游灵山胜境怎么安排比较轻松？")
    recommend_result = KnowledgeGraphSearchTool(pipeline).run("带孩子适合去哪些景点？")
    story_result = KnowledgeGraphSearchTool(pipeline).run("灵山胜境和玄奘有什么关系？")

    assert graph.scenarios == ["route", "recommend", "story"]
    assert route_result.sources[0].metadata["scenario"] == "route"
    assert recommend_result.sources[0].metadata["scenario"] == "recommend"
    assert story_result.sources[0].metadata["scenario"] == "story"


def test_query_rewrite_tool_generates_focused_unique_queries():
    result = QueryRewriteTool().run("灵境山适合老人游玩吗？")

    assert result.status == "ok"
    assert result.data["queries"][0] == "灵境山适合老人游玩吗？"
    assert len(result.data["queries"]) <= 3
    assert len(result.data["queries"]) == len(set(result.data["queries"]))
    assert any("老人" in query or "休息" in query for query in result.data["queries"])


def test_query_rewrite_tool_expands_parking_food_and_show_questions():
    parking = QueryRewriteTool().run("停车场在哪里？")
    food = QueryRewriteTool().run("景区有什么餐饮住宿？")
    show = QueryRewriteTool().run("晚上有什么表演？")

    assert any("停车场" in query and "自驾" in query for query in parking.data["queries"])
    assert any("餐饮" in query and "住宿" in query for query in food.data["queries"])
    assert any("表演" in query and "场次" in query for query in show.data["queries"])
    assert len(parking.data["queries"]) <= 3


def test_rag_and_document_tools_return_local_evidence(tmp_path: Path):
    pipeline = build_pipeline(tmp_path)

    rag_result = RagSearchTool(pipeline).run("老人 休息点")
    document_result = DocumentSearchTool(pipeline).run("老人 休息点")

    assert rag_result.status == "ok"
    assert rag_result.sources[0].document_name == "灵境山资料.md"
    assert "休息点" in rag_result.sources[0].content
    assert document_result.status == "ok"
    assert document_result.sources[0].document_name == "灵境山资料.md"
    assert "适合老人" in document_result.sources[0].content


def test_web_search_tool_is_disabled_without_configuration(tmp_path: Path):
    settings = AppSettings.for_workspace(tmp_path)

    result = WebSearchTool(settings).run("灵境山 最新公告")

    assert result.status == "disabled"
    assert result.message == "外部搜索未启用"
    assert result.sources == []


def test_agent_executor_runs_whitelisted_tools_and_returns_trace(tmp_path: Path):
    pipeline = build_pipeline(tmp_path)
    executor = AgentExecutor(
        settings=pipeline.settings,
        tools=[
            QueryRewriteTool(),
            RagSearchTool(pipeline),
            KnowledgeGraphSearchTool(pipeline),
            DocumentSearchTool(pipeline),
            WebSearchTool(pipeline.settings),
        ],
    )

    result = executor.run("灵境山适合老人游玩吗？")

    assert result.is_answered is True
    assert "### 简要回答" in result.answer
    assert "依据：" in result.answer
    assert result.sources[0].document_name == "灵境山资料.md"
    assert [trace.tool_name for trace in result.tool_trace] == [
        "query_rewrite",
        "rag_search",
        "kg_search",
        "document_search",
    ]
    assert all(trace.status in {"ok", "disabled", "empty"} for trace in result.tool_trace)
