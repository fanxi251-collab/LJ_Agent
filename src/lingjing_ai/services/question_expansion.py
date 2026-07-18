from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, Protocol

from lingjing_ai.realtime.transcript import TranscriptCorrection


class QuestionExpansionClient(Protocol):
    def chat(self, messages: list[dict[str, str]]) -> str:
        ...


@dataclass(frozen=True)
class QuestionExpansionResult:
    expanded_questions: list[str]
    selected_questions: list[str]
    assumptions: str


@dataclass(frozen=True)
class VoiceQuestionUnderstanding:
    normalized_question: str = ""
    correction_confidence: float = 0.0
    expanded_questions: list[str] | None = field(default_factory=list)
    correction: TranscriptCorrection | None = None


class QwenQuestionExpander:
    def __init__(self, client: QuestionExpansionClient, model_name: str = "qwen3.7-plus") -> None:
        self.client = client
        self.model_name = model_name

    def expand(
        self,
        question: str,
        target: str,
        history: list[Any],
        max_candidates: int,
    ) -> list[str]:
        messages = [
            {
                "role": "system",
                "content": (
                    f"你是景区 AI 导游的问题理解模块，当前使用模型：{self.model_name}。\n"
                    "请把游客原问题扩写成多个可能的检索问题，只输出 JSON 字符串数组。\n"
                    "要求：保留游客原始意图；不要新增游客没表达的硬条件；不要编造老人、亲子、门票、天气等条件；"
                    "每个问题不超过 40 个中文字符。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"游客问题：{question}\n"
                    f"已识别景区或城市：{target or '无'}\n"
                    f"最近历史：{_history_text(history)}\n"
                    f"最多生成：{max_candidates - 1} 个"
                ),
            },
        ]
        return _parse_model_candidates(self.client.chat(messages), max_candidates=max_candidates)

    def understand_voice(
        self,
        question: str,
        correction_candidates: list[str],
        history: list[Any],
        max_candidates: int,
    ) -> VoiceQuestionUnderstanding:
        allowed = _unique([question, *correction_candidates])
        messages = [
            {
                "role": "system",
                "content": (
                    f"你是景区 AI 导游的语音理解模块，当前使用模型：{self.model_name}。\n"
                    "normalized_question 只能选择候选中的完整文本，不能改写候选以外的数字、时间、数量或否定含义。"
                    "同时生成检索扩写问题，只输出 JSON 对象，字段为 normalized_question、"
                    "correction_confidence、expanded_questions。每个扩写不超过40个中文字符。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"原始转写：{question}\n"
                    f"只能选择候选：{json.dumps(allowed, ensure_ascii=False)}\n"
                    f"最近历史：{_history_text(history)}\n"
                    f"最多生成：{max(0, max_candidates - 1)} 个扩写"
                ),
            },
        ]
        return _parse_voice_understanding(
            self.client.chat(messages),
            question,
            allowed,
            max_candidates,
        )


def expand_question(
    question: str,
    target: str,
    history: list[Any],
    max_candidates: int = 8,
    expander: QwenQuestionExpander | None = None,
) -> list[str]:
    original = question.strip()
    if not original:
        return []
    if expander is None:
        return [original]
    try:
        candidates = expander.expand(original, target, history, max_candidates=max_candidates)
    except Exception:
        return [original]
    return _unique([original, *candidates])[: max(1, max_candidates)]


def build_question_expansion(
    question: str,
    target: str,
    history: list[Any],
    max_candidates: int = 8,
    top_n: int = 3,
    expander: QwenQuestionExpander | None = None,
) -> QuestionExpansionResult:
    expanded = expand_question(
        question,
        target,
        history,
        max_candidates=max_candidates,
        expander=expander,
    )
    selected_pool = expanded[1:] if len(expanded) > 1 else expanded
    return QuestionExpansionResult(
        expanded_questions=expanded,
        selected_questions=selected_pool[: max(1, top_n)],
        assumptions=_assumptions(question),
    )


def rank_question_candidates(
    original_question: str,
    candidates: list[str],
    records: list[dict[str, Any]],
    top_n: int = 3,
) -> list[str]:
    scored = []
    for index, candidate in enumerate(candidates):
        candidate_tokens = set(_tokens(candidate))
        original_tokens = set(_tokens(original_question))
        record_text = " ".join(
            f"{record.get('document_name', '')} {record.get('content', '')} {record.get('metadata', {}).get('category', '')}"
            for record in records
        )
        record_tokens = set(_tokens(record_text))
        original_overlap = len(candidate_tokens & original_tokens) / max(1, len(original_tokens))
        record_overlap = len(candidate_tokens & record_tokens) / max(1, len(candidate_tokens))
        category_match = 1.0 if _classify_category(candidate) in record_text else 0.0
        score = (original_overlap * 0.38) + (record_overlap * 0.52) + (category_match * 0.10)
        scored.append((score, -index, candidate))
    scored.sort(reverse=True)
    return [candidate for _, _, candidate in scored[: max(1, top_n)]]


def _parse_model_candidates(content: str, max_candidates: int) -> list[str]:
    text = _strip_code_fence(content.strip())
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = [line.strip("-•  \t") for line in text.splitlines() if line.strip()]
    if not isinstance(data, list):
        return []
    return [
        str(item).strip()
        for item in data
        if isinstance(item, str) and str(item).strip()
    ][: max(0, max_candidates - 1)]


def _parse_voice_understanding(
    content: str,
    original: str,
    allowed: list[str],
    max_candidates: int,
) -> VoiceQuestionUnderstanding:
    try:
        data = json.loads(_strip_code_fence(content.strip()))
    except (json.JSONDecodeError, TypeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    normalized = str(data.get("normalized_question") or original).strip()
    if normalized not in allowed:
        normalized = original
    try:
        confidence = min(1.0, max(0.0, float(data.get("correction_confidence", 0))))
    except (TypeError, ValueError):
        confidence = 0.0
    expansions = data.get("expanded_questions")
    if not isinstance(expansions, list):
        expansions = []
    return VoiceQuestionUnderstanding(
        normalized_question=normalized,
        correction_confidence=confidence,
        expanded_questions=_unique(
            [str(item).strip() for item in expansions if isinstance(item, str)]
        )[: max(0, max_candidates - 1)],
    )


def _history_text(history: list[Any]) -> str:
    snippets = []
    for message in history[-4:]:
        content = getattr(message, "content", "")
        if content:
            snippets.append(str(content)[:120])
    return "；".join(snippets) or "无"


def _assumptions(question: str) -> str:
    if _looks_like_route_planning(question):
        return "我先按普通游客、正常体力规划；如有老人、儿童或行动不便游客，可继续补充后调整。"
    return ""


def _tokens(text: str) -> list[str]:
    lowered = text.lower()
    words = re.findall(r"[a-z0-9]+", lowered)
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", lowered)
    bigrams = ["".join(chinese_chars[index : index + 2]) for index in range(max(0, len(chinese_chars) - 1))]
    return words + chinese_chars + bigrams


def _unique(candidates: list[str]) -> list[str]:
    result = []
    for candidate in candidates:
        compact = candidate.strip()
        if compact and compact not in result:
            result.append(compact)
    return result


def _looks_like_route_planning(question: str) -> bool:
    return any(keyword in question for keyword in ("规划", "游览路线", "导游路线", "行程", "怎么玩", "游玩", "玩"))


def _classify_category(question: str) -> str:
    if any(keyword in question for keyword in ("路线", "怎么走", "顺序", "游玩", "游览", "行程")):
        return "游览路线"
    if any(keyword in question for keyword in ("老人", "儿童", "亲子", "休息", "无障碍", "服务")):
        return "服务设施"
    if any(keyword in question for keyword in ("门票", "票价", "优惠")):
        return "票务价格"
    return "景点介绍"


def _strip_code_fence(text: str) -> str:
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()
