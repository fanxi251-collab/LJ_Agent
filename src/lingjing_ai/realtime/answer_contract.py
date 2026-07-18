from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from lingjing_ai.agent.models import AgentEvidence
from lingjing_ai.models.rag import SourceChunk


AnswerProfile = Literal["text_detailed", "avatar_summary", "route_text", "route_avatar"]


@dataclass(frozen=True)
class AnswerContract:
    profile: AnswerProfile
    instructions: str
    route_summary: dict[str, Any] | None = None
    route_error: str = ""
    clarification: str = ""


@dataclass(frozen=True)
class FinalizedAnswer:
    text: str
    appended_text: str = ""


def build_answer_contract(evidence: AgentEvidence, mode: str) -> AnswerContract:
    """Choose one explicit response shape so text and spoken modes no longer share a length limit."""
    route_summary = _find_route_summary(evidence.sources)
    route_trace = next((trace for trace in evidence.tool_trace if trace.tool_name == "amap_route"), None)
    is_route = route_summary is not None or route_trace is not None
    route_error = ""
    if route_trace is not None and route_trace.status != "ok" and route_summary is None:
        route_error = route_trace.message.strip() or "未获得可用路线"

    if evidence.needs_clarification:
        return AnswerContract(
            profile="avatar_summary" if mode == "avatar" else "text_detailed",
            instructions=(
                f"只提出这个澄清问题，不要推测答案：{evidence.clarifying_question}"
            ),
            clarification=evidence.clarifying_question,
        )

    if is_route and mode == "avatar":
        return AnswerContract(
            profile="route_avatar",
            instructions=(
                "这是数字人路线回答：仅用3—6句朗读起点、终点、出行方式、距离、耗时和核心方向；"
                "不要逐条朗读路线，完整步骤由路线面板展示；工具失败时只说明具体失败原因，不得猜测路线。"
            ),
            route_summary=route_summary,
            route_error=route_error,
        )
    if is_route:
        return AnswerContract(
            profile="route_text",
            instructions=(
                "这是常规路线回答：必须明确起点、终点、出行方式、距离和耗时，并按顺序给出证据中的"
                "8—12条关键步骤，最后补充交通或安全提醒；只能采用高德第一推荐路线，不得猜测缺失步骤。"
            ),
            route_summary=route_summary,
            route_error=route_error,
        )
    if mode == "avatar":
        return AnswerContract(
            profile="avatar_summary",
            instructions=(
                "这是数字人口播回答：先直接回答，再用3—6句概括最重要的事实和一条实用建议；"
                "保持适合朗读的自然短句，详细资料与引用由界面展示。"
            ),
        )
    return AnswerContract(
        profile="text_detailed",
        instructions=(
            "这是常规文字回答：先直接给出结论，再列出3—5个有证据支持的事实要点，最后给出游览建议、"
            "限制或需要确认的信息；证据充分时整体约300—600字，但不得为达到字数编造内容。"
        ),
    )


def finalize_answer(
    evidence: AgentEvidence,
    contract: AnswerContract,
    answer: str,
) -> FinalizedAnswer:
    """Apply deterministic completeness checks because model prose alone cannot guarantee route fields."""
    normalized = str(answer or "").strip()
    if contract.clarification:
        return FinalizedAnswer(contract.clarification)
    if contract.route_error:
        message = contract.route_error.rstrip("。")
        return FinalizedAnswer(f"路线查询失败：{message}。请稍后重试或核对起点和终点。")

    if contract.profile == "route_text" and contract.route_summary:
        required = _required_route_values(contract.route_summary)
        if any(value and value not in normalized for value in required):
            appended = _route_block(contract.route_summary)
            return FinalizedAnswer(_join_answer(normalized, appended), appended)
        return FinalizedAnswer(normalized)

    if contract.profile != "text_detailed":
        return FinalizedAnswer(normalized)
    if (
        len(normalized) >= 220
        or not evidence.is_answered
        or evidence.confidence < 0.5
        or evidence.needs_clarification
        or not evidence.sources
    ):
        return FinalizedAnswer(normalized)

    appended = _source_facts(evidence.sources)
    return FinalizedAnswer(_join_answer(normalized, appended), appended)


def _find_route_summary(sources: list[SourceChunk]) -> dict[str, Any] | None:
    for source in sources:
        metadata = source.metadata or {}
        if metadata.get("source_type") != "amap_route":
            continue
        summary = metadata.get("route_summary") or metadata
        if isinstance(summary, dict):
            return summary
    return None


def _required_route_values(summary: dict[str, Any]) -> list[str]:
    return [
        str(summary.get("origin") or ""),
        str(summary.get("destination") or ""),
        str(summary.get("mode_text") or ""),
        str(summary.get("distance_text") or ""),
        str(summary.get("duration_text") or ""),
    ]


def _route_block(summary: dict[str, Any]) -> str:
    origin, destination, mode, distance, duration = _required_route_values(summary)
    lines = [
        "### 完整路线",
        f"- 路线总览：从{origin or '未确认起点'}到{destination or '未确认终点'}，"
        f"出行方式为{mode or '未确认'}，距离{distance or '未知'}，预计耗时{duration or '未知'}。",
        "- 关键步骤：",
    ]
    for display_index, step in enumerate(summary.get("steps") or [], start=1):
        instruction = str(step.get("instruction") or "").strip()
        if instruction:
            lines.append(f"  {display_index}. {instruction}")
    lines.append("- 提醒：请以高德实时路况和现场交通标识为准，出发前留意拥堵、施工及景区停车安排。")
    return "\n".join(lines)


def _source_facts(sources: list[SourceChunk]) -> str:
    selected = []
    seen_sources = set()
    seen_facts = set()
    for source in sources:
        source_key = source.document_id or source.document_name
        fact = _first_fact(source.content)
        if not fact or source_key in seen_sources or fact in seen_facts:
            continue
        selected.append(f"- {fact}（来源：{source.document_name or '景区资料'}）")
        seen_sources.add(source_key)
        seen_facts.add(fact)
        if len(selected) == 3:
            break
    if not selected:
        return ""
    supplement = "### 资料要点\n" + "\n".join(selected)
    return supplement[:450].rstrip()


def _first_fact(content: str) -> str:
    normalized = " ".join(str(content or "").split()).strip()
    if not normalized:
        return ""
    endings = [position for marker in "。！？；" if (position := normalized.find(marker)) >= 0]
    end = min(endings) + 1 if endings else min(len(normalized), 120)
    return normalized[: min(end, 120)].strip()


def _join_answer(answer: str, appended: str) -> str:
    if not appended:
        return answer
    return f"{answer}\n\n{appended}" if answer else appended
