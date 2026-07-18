from __future__ import annotations

from dataclasses import dataclass
import re

from lingjing_ai.services.tool_intent import should_skip_question_expansion
from lingjing_ai.services.question_expansion import QwenQuestionExpander, build_question_expansion


MAX_HISTORY_MESSAGES = 12
MAX_MESSAGE_CHARS = 800

SCENIC_NAMES = ("灵山胜境", "灵山大佛", "拈花湾", "鼋头渚", "灵境山", "青岚湖")
CITY_NAMES = ("无锡", "苏州", "南京", "上海", "杭州", "北京")


@dataclass(frozen=True)
class ConversationMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ConversationContext:
    original_question: str
    standalone_question: str
    history: list[ConversationMessage]
    context_summary: str
    needs_clarification: bool = False
    clarifying_question: str = ""
    expanded_questions: list[str] | None = None
    selected_questions: list[str] | None = None
    assumptions: str = ""


def build_conversation_context(
    question: str,
    history: list[ConversationMessage | dict] | None = None,
    question_expander: QwenQuestionExpander | None = None,
    max_expansion_candidates: int = 8,
    expansion_top_n: int = 3,
    question_expansion_auto_skip: bool = True,
) -> ConversationContext:
    normalized_history = _normalize_history(history or [])
    target = _extract_target(question) or _extract_target_from_history(normalized_history)
    standalone_question = _standalone_question(question, target)
    clarifying_question = _clarifying_question(question, standalone_question, target)
    active_expander = question_expander
    if question_expansion_auto_skip and should_skip_question_expansion(standalone_question, target):
        active_expander = None
    expansion = build_question_expansion(
        standalone_question,
        target,
        normalized_history,
        max_candidates=max_expansion_candidates,
        top_n=expansion_top_n,
        expander=active_expander,
    )
    context_summary = _context_summary(target, normalized_history)
    return ConversationContext(
        original_question=question,
        standalone_question=standalone_question,
        history=normalized_history,
        context_summary=context_summary,
        needs_clarification=bool(clarifying_question),
        clarifying_question=clarifying_question,
        expanded_questions=expansion.expanded_questions,
        selected_questions=expansion.selected_questions,
        assumptions=expansion.assumptions,
    )


def _normalize_history(history: list[ConversationMessage | dict]) -> list[ConversationMessage]:
    trimmed = history[-MAX_HISTORY_MESSAGES:]
    messages: list[ConversationMessage] = []
    for item in trimmed:
        if isinstance(item, ConversationMessage):
            role = item.role
            content = item.content
        else:
            role = str(item.get("role", "user"))
            content = str(item.get("content", ""))
        role = role if role in {"user", "assistant"} else "user"
        messages.append(ConversationMessage(role=role, content=content[:MAX_MESSAGE_CHARS]))
    return messages


def _extract_target(text: str) -> str:
    for name in SCENIC_NAMES:
        if name in text:
            return name
    for city in CITY_NAMES:
        if city in text:
            return city
    return ""


def _extract_target_from_history(history: list[ConversationMessage]) -> str:
    for message in reversed(history):
        target = _extract_target(message.content)
        if target:
            return target
    return ""


def _standalone_question(question: str, target: str) -> str:
    stripped = question.strip()
    if _is_route_question(stripped) and _has_route_origin_and_destination(stripped):
        # Explicit endpoints are stronger than historical context, which must never replace A or B.
        return stripped
    if not target:
        return stripped
    if _is_short_ticket_follow_up(stripped):
        return f"{target}门票信息"
    if _is_opening_time_follow_up(stripped) and not _extract_target(stripped):
        return f"{target}开放时间"
    if _is_weather_question(stripped) and not _extract_target(stripped):
        return f"{target}今日天气如何？"
    if _is_short_how_to_play(stripped) and target:
        return f"{target}怎么玩"
    if _is_route_question(stripped) and not _extract_target(stripped):
        return f"到{target}怎么去？"
    if _is_elder_follow_up(stripped) and not _extract_target(stripped):
        return f"{target}适合老人游玩吗？"
    return stripped


def _clarifying_question(question: str, standalone_question: str, target: str) -> str:
    if _is_weather_question(question) and not target:
        return "您想查询哪个城市或景区的天气？"
    if _is_short_how_to_play(question) and not target:
        return "您想游览哪个景区？"
    if _is_route_question(question) and not _is_route_planning_question(question) and not _has_route_origin_and_destination(standalone_question):
        return "请告诉我您的出发地和目的地。"
    return ""


def _context_summary(target: str, history: list[ConversationMessage]) -> str:
    if not target:
        return ""
    recent_user_questions = [message.content for message in history if message.role == "user"][-2:]
    suffix = "；".join(recent_user_questions)
    if suffix:
        return f"最近对话围绕{target}展开；最近问题：{suffix}"
    return f"最近对话围绕{target}展开"


def _is_short_ticket_follow_up(question: str) -> bool:
    compact = _compact(question)
    return "门票" in compact and len(compact) <= 8


def _is_opening_time_follow_up(question: str) -> bool:
    compact = _compact(question)
    return any(keyword in compact for keyword in ("开放时间", "几点开放", "几点开门", "营业时间"))


def _is_weather_question(question: str) -> bool:
    return any(keyword in question for keyword in ("天气", "气温", "温度", "下雨", "风力", "湿度"))


def _is_route_question(question: str) -> bool:
    return any(keyword in question for keyword in ("怎么去", "怎么走", "如何去", "导航", "路线"))


def _is_route_planning_question(question: str) -> bool:
    return any(keyword in question for keyword in ("规划", "游览路线", "导游路线", "行程", "怎么玩", "游玩"))


def _is_elder_follow_up(question: str) -> bool:
    return any(keyword in question for keyword in ("老人", "老年", "长辈", "适老"))


def _is_discount_question(question: str) -> bool:
    return "票" in question and any(keyword in question for keyword in ("优惠", "优待", "减免", "半价"))


def _has_ticket_identity(question: str) -> bool:
    return any(keyword in question for keyword in ("成人", "老人", "老年", "儿童", "学生", "军人", "残疾"))


def _has_people_or_duration(question: str) -> bool:
    has_people = any(keyword in question for keyword in ("老人", "儿童", "亲子", "学生", "情侣", "家庭"))
    has_duration = bool(re.search(r"\d+\s*(小时|天|日)|[一二两三四五六七八九十]+\s*(个)?\s*小时|半天|一天|两天|上午|下午", question))
    return has_people and has_duration


def _is_short_how_to_play(question: str) -> bool:
    return _compact(question) in {"怎么玩", "怎么游", "如何玩", "咋玩"}


def _has_route_origin_and_destination(question: str) -> bool:
    return "从" in question and "到" in question


def _compact(text: str) -> str:
    return re.sub(r"[\s？?。！!，,、呢吗啊呀]", "", text)
