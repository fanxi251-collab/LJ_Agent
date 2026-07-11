from lingjing_ai.models.rag import SourceChunk
from lingjing_ai.rag.answer_formatter import (
    format_extract_answer,
    format_route_suggestion_answer,
    format_weather_answer,
    normalize_model_answer,
)
from lingjing_ai.rag.fact_guard import guard_answer_facts
from lingjing_ai.rag.llm_client import LlmCallError, LlmClient
from lingjing_ai.rag.prompt_loader import DEFAULT_SYSTEM_PROMPT
from lingjing_ai.rag.question_type import answer_focus_for_question, classify_question


class ExtractiveAnswerGenerator:
    refusal = "当前资料中没有查到可靠依据，暂时无法回答这个问题。"

    def generate(self, question: str, sources: list[SourceChunk], context_summary: str = "") -> str:
        if not sources:
            return self.refusal
        if _is_weather_source(sources[0]):
            return format_weather_answer(sources[0].document_name, sources[0].metadata, sources[0].content)
        if _should_use_route_suggestion(question, sources):
            return guard_answer_facts(format_route_suggestion_answer(sources[0].document_name, _merge_source_content(sources)), sources)
        return guard_answer_facts(format_extract_answer(sources[0].document_name, sources[0].content), sources)

    def generate_stream(self, question: str, sources: list[SourceChunk], context_summary: str = ""):
        yield from _split_text(self.generate(question, sources))


class QwenAnswerGenerator:
    refusal = ExtractiveAnswerGenerator.refusal

    def __init__(self, llm_client: LlmClient, system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> None:
        self.llm_client = llm_client
        self.system_prompt = system_prompt

    def generate(self, question: str, sources: list[SourceChunk], context_summary: str = "") -> str:
        if not sources:
            return self.refusal
        if _is_weather_source(sources[0]):
            return format_weather_answer(sources[0].document_name, sources[0].metadata, sources[0].content)

        messages = [
            {
                "role": "system",
                "content": self.system_prompt,
            },
            {
                "role": "user",
                "content": self._build_user_prompt(question, sources, context_summary=context_summary),
            },
        ]
        try:
            answer = normalize_model_answer(self.llm_client.chat(messages).strip(), sources[0].document_name)
            if _is_rigid_route_refusal(question, answer, sources):
                answer = format_route_suggestion_answer(sources[0].document_name, _merge_source_content(sources))
            return guard_answer_facts(answer, sources)
        except LlmCallError:
            return ExtractiveAnswerGenerator().generate(question, sources)

    def generate_stream(self, question: str, sources: list[SourceChunk], context_summary: str = ""):
        if not sources:
            yield self.refusal
            return
        if _is_weather_source(sources[0]):
            yield from _split_text(format_weather_answer(sources[0].document_name, sources[0].metadata, sources[0].content))
            return

        messages = [
            {
                "role": "system",
                "content": self.system_prompt,
            },
            {
                "role": "user",
                "content": self._build_user_prompt(question, sources, context_summary=context_summary),
            },
        ]
        try:
            chunks = []
            for token in self.llm_client.chat_stream(messages):
                chunks.append(token)
            answer = normalize_model_answer("".join(chunks), sources[0].document_name)
            if _is_rigid_route_refusal(question, answer, sources):
                answer = format_route_suggestion_answer(sources[0].document_name, _merge_source_content(sources))
            yield from _split_text(guard_answer_facts(answer, sources))
        except LlmCallError:
            if chunks:
                answer = normalize_model_answer("".join(chunks), sources[0].document_name)
                if _is_rigid_route_refusal(question, answer, sources):
                    answer = format_route_suggestion_answer(sources[0].document_name, _merge_source_content(sources))
                yield from _split_text(guard_answer_facts(answer, sources))
            else:
                yield from ExtractiveAnswerGenerator().generate_stream(question, sources)

    def _build_user_prompt(self, question: str, sources: list[SourceChunk], context_summary: str = "") -> str:
        profile = classify_question(question)
        evidence = []
        for index, source in enumerate(sources, start=1):
            evidence.append(
                f"[资料{index}] 来源：{source.document_name}\n"
                f"章节：{source.metadata.get('section_path', '未标注')}\n"
                f"类别：{source.metadata.get('category', '未标注')}\n"
                f"相关度：{source.score:.4f}\n"
                f"内容：{source.content.strip()}"
            )
        return (
            "请基于以下景区资料回答游客问题，并用自然、简洁的导游语气表达。\n\n"
            f"游客问题：{question}\n\n"
            f"对话上下文：{context_summary or '无'}\n\n"
            f"问题类型：{profile.category}\n"
            f"回答侧重点：{answer_focus_for_question(question)}\n\n"
            "景区资料：\n"
            + "\n\n".join(evidence)
            + "\n\n回答要求：\n"
            "1. 只回答游客问题本身，不要输出资料之外的景区事实。\n"
            "2. 如果资料不足，请明确说明当前资料无法确认。\n"
            "3. 可以概括、整合资料，但不要虚构开放时间、票价、地址、路线或历史细节。\n"
            "4. 回答应适合游客阅读，语气亲切、简洁、自然。\n"
            "5. 禁止照搬资料中的 Markdown 标题、表格、分隔符、原始项目符号或重复段落。\n"
            "6. 时间、价格、电话、地点、路线等事实必须能在资料中找到原文依据；找不到就说明资料未明确。\n"
            "7. 如果游客是在请你规划路线，但资料没有完整起点和顺序，不要直接硬拒答；"
            "可以基于已有景点、观光车、休息点、服务设施等资料给出“建议型路线”，"
            "并明确说明完整起点、顺序或时长资料未明确。\n"
            "8. 输出必须使用以下固定格式，不要增加其他一级标题：\n"
            "### 简要回答\n"
            "直接回答游客问题，用 1 到 3 句话概括结论。\n\n"
            "### 详细说明\n"
            "- 用要点列出资料支持的关键信息；简单问题可以只写 1 条。\n\n"
            "### 温馨提示\n"
            "给出资料支持范围内的实用提醒；如果资料不足，请说明无法确认。\n\n"
            "依据：资料名称"
        )


def _split_text(text: str, size: int = 24):
    for start in range(0, len(text), size):
        yield text[start : start + size]


def _should_use_route_suggestion(question: str, sources: list[SourceChunk]) -> bool:
    profile = classify_question(question)
    if profile.category != "游览路线":
        return False
    evidence = _merge_source_content(sources)
    return any(keyword in evidence for keyword in ("观光车", "休息", "服务中心", "无障碍", "轮椅", "老人", "景点"))


def _is_weather_source(source: SourceChunk) -> bool:
    return source.metadata.get("source_type") == "amap_weather" or source.document_id == "amap_weather"


def _is_rigid_route_refusal(question: str, answer: str, sources: list[SourceChunk]) -> bool:
    if not _should_use_route_suggestion(question, sources):
        return False
    rigid_markers = ("没有查到具体的游玩路线", "暂时无法为您确认详细", "无法为您确认详细的", "资料中未明确说明路线顺序")
    return any(marker in answer for marker in rigid_markers)


def _merge_source_content(sources: list[SourceChunk]) -> str:
    return " ".join(source.content.strip() for source in sources if source.content.strip())
