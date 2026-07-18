from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class FastToolIntent:
    tool_name: str
    source_type: str
    status_message: str
    direct_answer: bool


def classify_fast_tool_intent(question: str) -> FastToolIntent | None:
    text = question.strip()
    if not text:
        return None
    if _looks_like_weather_question(text):
        return FastToolIntent(
            tool_name="amap_weather",
            source_type="amap_weather",
            status_message="正在查询天气",
            direct_answer=True,
        )
    if _looks_like_direct_route_question(text):
        return FastToolIntent(
            tool_name="amap_route",
            source_type="amap_route",
            status_message="正在规划路线",
            direct_answer=not _looks_like_complex_route_planning(text),
        )
    if _looks_like_place_question(text):
        return FastToolIntent(
            tool_name="amap_place_search",
            source_type="amap_place",
            status_message="正在查询地图位置",
            direct_answer=True,
        )
    return None


def status_message_for_question(question: str) -> str:
    intent = classify_fast_tool_intent(question)
    if intent is not None:
        return intent.status_message
    return "正在检索资料"


def should_skip_question_expansion(question: str, target: str = "") -> bool:
    text = question.strip()
    if not text or _is_short_follow_up(text):
        return False
    if _looks_like_weather_question(text) and (target or _contains_known_place(text)):
        return True
    if _looks_like_direct_route_question(text):
        return True
    if _looks_like_place_question(text) and (target or _contains_known_place(text)):
        return True
    if len(_compact(text)) > 12 and (target or _contains_known_place(text)) and not _needs_expansion_even_when_long(text):
        return True
    return False


def route_endpoint_clarification(question: str) -> str:
    """Ask for named endpoints before map execution because Amap cannot plan a trustworthy partial route."""
    text = question.strip()
    route_words = ("怎么走", "怎么去", "如何去", "如何走", "导航")
    if not any(word in text for word in route_words) or _looks_like_direct_route_question(text):
        return ""
    has_origin = "从" in text
    has_destination = "到" in text
    if has_destination and not has_origin:
        return "请补充明确的起点，例如：从无锡站到灵山胜境怎么走？"
    if has_origin and not has_destination:
        return "请补充明确的终点，例如：从无锡站到灵山胜境怎么走？"
    return "请同时提供明确的起点和终点，例如：从无锡站到灵山胜境怎么走？"


def _looks_like_weather_question(question: str) -> bool:
    return any(keyword in question for keyword in ("天气", "气温", "温度", "下雨", "风力", "湿度"))


def _looks_like_direct_route_question(question: str) -> bool:
    return "从" in question and "到" in question and any(
        keyword in question for keyword in ("怎么走", "怎么去", "如何去", "如何走", "路线", "导航")
    )


def _looks_like_place_question(question: str) -> bool:
    if _looks_like_direct_route_question(question):
        return False
    return any(keyword in question for keyword in ("地图", "位置", "在哪里", "附近", "停车场", "卫生间", "厕所"))


def _looks_like_complex_route_planning(question: str) -> bool:
    return any(keyword in question for keyword in ("游览", "游玩", "导游", "行程", "规划", "安排", "推荐", "老人", "亲子", "儿童"))


def _needs_expansion_even_when_long(question: str) -> bool:
    return any(keyword in question for keyword in ("怎么玩", "游览路线", "导游路线", "规划路线", "行程", "推荐路线"))


def _is_short_follow_up(question: str) -> bool:
    compact = _compact(question)
    if len(compact) <= 8:
        return True
    return bool(re.fullmatch(r"(那|这个|这里|它|还有)?(门票|票价|怎么玩|怎么去|适合老人|开放时间)(呢|吗)?", compact))


def _contains_known_place(question: str) -> bool:
    return any(place in question for place in ("灵山胜境", "灵山大佛", "拈花湾", "鼋头渚", "无锡", "苏州", "南京", "上海", "杭州", "北京"))


def _compact(text: str) -> str:
    return re.sub(r"[\s？?。！!，,、呢吗啊呀]", "", text)
