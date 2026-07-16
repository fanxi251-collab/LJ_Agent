from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from time import perf_counter
from typing import Any

from lingjing_ai.agent.executor import AgentExecutor
from lingjing_ai.agent.langgraph_executor import LangGraphAgentExecutor
from lingjing_ai.api.bootstrap import build_pipeline_components
from lingjing_ai.config.settings import AppSettings
from lingjing_ai.evaluation.judge import OptionalLlmJudge
from lingjing_ai.evaluation.models import CaseScore, EvaluationCase, EvaluationDataset
from lingjing_ai.evaluation.scoring import score_case
from lingjing_ai.rag.llm_client import AliyunQwenClient
from lingjing_ai.services.conversation import ConversationMessage, build_conversation_context
from lingjing_ai.services.question_expansion import QwenQuestionExpander
from lingjing_ai.tools.amap_client import AmapClient
from lingjing_ai.tools.amap_tools import AmapPlaceSearchTool, AmapRouteTool, AmapWeatherTool
from lingjing_ai.tools.document_search_tool import DocumentSearchTool
from lingjing_ai.tools.kg_search_tool import KnowledgeGraphSearchTool
from lingjing_ai.tools.query_rewrite_tool import QueryRewriteTool
from lingjing_ai.tools.rag_search_tool import RagSearchTool
from lingjing_ai.tools.web_search_tool import WebSearchTool


class FixtureAmapClient:
    """Return stable tool data so benchmark differences come from QA code, not changing map data."""

    def __init__(self, fixtures: dict[str, dict[str, Any]]) -> None:
        self.fixtures = fixtures
        self.locations = {
            "无锡站": "120.305,31.590",
            "无锡东站": "120.460,31.598",
            "灵山胜境": "120.102,31.426",
            "灵山大佛": "120.106,31.428",
            "九龙灌浴": "120.104,31.426",
            "灵山梵宫": "120.108,31.424",
            "拈花湾": "120.066,31.488",
        }

    def weather(self, city: str, extensions: str = "base") -> dict[str, Any]:
        return dict(self.fixtures["amap_weather_wuxi"]["payload"])

    def place_search(self, keywords: str, city: str = "", offset: int = 5) -> dict[str, Any]:
        payload = dict(self.fixtures["amap_place_lingshan"]["payload"])
        return payload

    def geocode(self, address: str, city: str = "") -> dict[str, Any]:
        location = next((value for key, value in self.locations.items() if key in address), "120.100,31.500")
        return {"status": "1", "infocode": "10000", "geocodes": [{"formatted_address": address, "location": location}]}

    def walking_route(self, origin: str, destination: str) -> dict[str, Any]:
        return dict(self.fixtures["amap_route_walking"]["payload"])

    def driving_route(self, origin: str, destination: str) -> dict[str, Any]:
        return dict(self.fixtures["amap_route_driving"]["payload"])


def run_evaluation(
    dataset: EvaluationDataset,
    *,
    mode: str,
    workspace_dir: Path,
    cases: list[EvaluationCase] | None = None,
    judge_llm: bool = False,
    judge_model: str = "",
) -> tuple[list[CaseScore], dict[str, Any]]:
    selected = cases or dataset.cases
    if mode == "offline":
        scores = [score_case(case, case.offline_response) for case in selected]
        return scores, {"response_source": "fixed_offline_responses", "cache_enabled": False}
    if mode not in {"benchmark", "smoke"}:
        raise ValueError(f"不支持的评测模式：{mode}")

    settings = AppSettings.for_workspace(workspace_dir)
    if not settings.llm_api_key:
        raise RuntimeError(f"{mode} 模式需要配置 LJAPI_KEY。")
    if mode == "smoke" and not settings.map_api_key:
        raise RuntimeError("smoke 模式需要配置 MAP_API。")
    evaluation_settings = replace(settings, answer_cache_enabled=False, redis_enabled=False)
    pipeline = build_pipeline_components(evaluation_settings)
    amap_client: AmapClient | FixtureAmapClient | None = None
    if mode == "benchmark":
        amap_client = FixtureAmapClient(dataset.tool_fixtures)
    executor = _build_executor(pipeline, amap_client=amap_client)
    expander = _build_expander(evaluation_settings)
    judge = _build_judge(evaluation_settings, judge_model) if judge_llm else None

    scores: list[CaseScore] = []
    for case in selected:
        started = perf_counter()
        try:
            context = build_conversation_context(
                case.question,
                [ConversationMessage(role=item["role"], content=item["content"]) for item in case.history],
                question_expander=expander,
                max_expansion_candidates=evaluation_settings.question_expansion_max_candidates,
                expansion_top_n=evaluation_settings.question_expansion_top_n,
                question_expansion_auto_skip=evaluation_settings.question_expansion_auto_skip,
            )
            response = _stream_response(executor, case, context, started)
        except Exception as exc:
            elapsed_ms = (perf_counter() - started) * 1000
            response = {
                "answer": f"评测执行失败：{type(exc).__name__}",
                "is_answered": False,
                "sources": [],
                "tool_trace": [],
                "total_ms": elapsed_ms,
            }
        judge_result = None
        if judge is not None:
            try:
                judge_result = judge.evaluate(case, response["answer"])
            except Exception as exc:
                # Keep deterministic benchmark results usable when the optional judge is unavailable.
                judge_result = {"error": f"{type(exc).__name__}: {exc}"}
        scores.append(score_case(case, response, llm_judge=judge_result))

    runtime = {
        "model": evaluation_settings.llm_model,
        "embedding_model": evaluation_settings.embedding_model,
        "agent_executor_mode": evaluation_settings.agent_executor_mode,
        "cache_enabled": False,
        "map_response_source": "live_amap" if mode == "smoke" else "fixed_amap_fixtures",
        "llm_judge_enabled": judge_llm,
        "judge_model": judge_model or evaluation_settings.question_expansion_model if judge_llm else "",
    }
    return scores, runtime


def _build_executor(pipeline, *, amap_client=None):
    settings = pipeline.settings
    tools = [
        QueryRewriteTool(),
        RagSearchTool(pipeline),
        KnowledgeGraphSearchTool(pipeline),
        DocumentSearchTool(pipeline),
        AmapWeatherTool(settings, client=amap_client),
        AmapRouteTool(settings, client=amap_client),
        AmapPlaceSearchTool(settings, client=amap_client),
        WebSearchTool(settings),
    ]
    executor_type = LangGraphAgentExecutor if settings.agent_executor_mode == "langgraph" else AgentExecutor
    return executor_type(settings=settings, tools=tools)


def _build_expander(settings: AppSettings) -> QwenQuestionExpander:
    model = settings.question_expansion_model or settings.llm_model
    client = AliyunQwenClient(
        api_key=settings.llm_api_key or "",
        model=model,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    return QwenQuestionExpander(client, model_name=model)


def _build_judge(settings: AppSettings, model: str) -> OptionalLlmJudge:
    client = AliyunQwenClient(
        api_key=settings.llm_api_key or "",
        model=model or settings.question_expansion_model or settings.llm_model,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    return OptionalLlmJudge(client)


def _stream_response(executor, case: EvaluationCase, context, started: float) -> dict[str, Any]:
    answer_parts: list[str] = []
    metadata: dict[str, Any] = {}
    first_token_ms: float | None = None
    for event in executor.run_stream(case.question, conversation_context=context):
        event_type = event.get("type")
        if event_type == "meta":
            metadata = event
        elif event_type == "token":
            if first_token_ms is None:
                first_token_ms = (perf_counter() - started) * 1000
            answer_parts.append(str(event.get("content", "")))
        elif event_type == "error":
            raise RuntimeError(str(event.get("message", "评测流式响应失败")))
    return {
        "answer": "".join(answer_parts).strip(),
        "is_answered": bool(metadata.get("is_answered")),
        "needs_clarification": bool(metadata.get("needs_clarification")),
        "clarifying_question": str(metadata.get("clarifying_question", "")),
        "sources": list(metadata.get("sources") or []),
        "tool_trace": list(metadata.get("tool_trace") or []),
        "first_token_ms": first_token_ms,
        "total_ms": (perf_counter() - started) * 1000,
    }
