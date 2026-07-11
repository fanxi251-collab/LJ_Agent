import re

from lingjing_ai.models.rag import SourceChunk


_RISK_FACT_PATTERNS = (
    r"\d+(?:\.\d+)?\s*元",
    r"\d{1,2}:\d{2}(?:\s*[-~至到]\s*\d{1,2}:\d{2})?",
    r"\d{3,4}[-\s]?\d{7,8}",
    r"1[3-9]\d{9}",
)


def guard_answer_facts(answer: str, sources: list[SourceChunk]) -> str:
    if not answer or not sources:
        return answer

    evidence_text = " ".join(source.content for source in sources)
    unsupported = _unsupported_facts(answer, evidence_text)
    if not unsupported:
        return answer

    guarded = answer
    for fact in unsupported:
        guarded = guarded.replace(fact, "")
    guarded = re.sub(r"[，,。；;]\s*[，,。；;]+", "。", guarded)
    guarded = re.sub(r"\s+", " ", guarded)
    guarded = _insert_uncertainty_note(guarded)
    return _restore_structured_newlines(guarded)


def _unsupported_facts(answer: str, evidence_text: str) -> list[str]:
    facts: list[str] = []
    for pattern in _RISK_FACT_PATTERNS:
        for match in re.findall(pattern, answer):
            fact = str(match).strip()
            if fact and fact not in evidence_text:
                facts.append(fact)
    return list(dict.fromkeys(facts))


def _insert_uncertainty_note(answer: str) -> str:
    note = "资料中未明确说明具体价格、时间或联系方式，请以景区官方公告为准。"
    if note in answer:
        return answer
    if "### 温馨提示" in answer:
        return answer.replace("### 温馨提示", f"### 温馨提示\n{note}\n", 1)
    if "依据：" in answer:
        return answer.replace("依据：", f"{note}\n\n依据：", 1)
    return f"{answer.rstrip()}\n\n{note}"


def _restore_structured_newlines(answer: str) -> str:
    text = answer.strip()
    for heading in ("### 简要回答", "### 详细说明", "### 温馨提示"):
        text = text.replace(heading, f"\n{heading}\n")
    text = text.replace("依据：", "\n\n依据：")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
