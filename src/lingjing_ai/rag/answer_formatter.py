from __future__ import annotations

import re


STRUCTURED_HEADINGS = ("### 简要回答", "### 详细说明", "### 温馨提示")


def clean_evidence_text(text: str, max_length: int = 260) -> str:
    lines = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"^[•·]\s*", "", line)
        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
        line = re.sub(r"`([^`]*)`", r"\1", line)
        if "|" in line:
            parts = [part.strip() for part in line.strip("|").split("|") if part.strip()]
            line = "，".join(parts)
        line = re.sub(r"[-—_]{3,}", "", line).strip()
        if line:
            lines.append(line)

    cleaned = " ".join(lines)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_length:
        return cleaned[:max_length].rstrip("，,。；; ") + "。"
    return cleaned


def format_extract_answer(document_name: str, evidence: str) -> str:
    cleaned = clean_evidence_text(evidence)
    if not cleaned:
        cleaned = "当前资料中没有查到可用于回答该问题的明确内容。"
    return (
        "### 简要回答\n"
        f"根据景区资料，{cleaned}\n\n"
        "### 详细说明\n"
        f"- {cleaned}\n\n"
        "### 温馨提示\n"
        "如需更准确的开放时间、票价或路线信息，请以景区官方公告或服务中心信息为准。\n\n"
        f"依据：{document_name}"
    )


def format_route_suggestion_answer(document_name: str, evidence: str) -> str:
    cleaned = clean_evidence_text(evidence, max_length=320)
    if not cleaned:
        cleaned = "资料中只提供了部分游览条件，暂未提供完整的起点和游览顺序。"
    return (
        "### 简要回答\n"
        "可以按“少步行、观光车优先、适当休息”的思路规划；资料未提供完整的起点和游览顺序，"
        "所以以下是基于已知资料整理的建议型路线。\n\n"
        "### 详细说明\n"
        "- 优先使用资料中提到的观光车，减少老人长距离步行。\n"
        "- 游览过程中可结合资料中提到的休息点安排停留，避免连续赶路。\n"
        f"- 已知依据：{cleaned}\n\n"
        "### 温馨提示\n"
        "资料未提供完整的起点和游览顺序；建议到景区后先确认观光车站点、运营时间和当日开放安排，再按体力调整节奏。\n\n"
        f"依据：{document_name}"
    )


def format_weather_answer(document_name: str, metadata: dict, evidence: str = "") -> str:
    city = str(metadata.get("city") or "当地").replace("市", "")
    weather = str(metadata.get("weather") or "未知")
    temperature = str(metadata.get("temperature") or "未知")
    winddirection = str(metadata.get("winddirection") or "未知")
    windpower = str(metadata.get("windpower") or "未知")
    humidity = str(metadata.get("humidity") or "未知")
    reporttime = str(metadata.get("reporttime") or "未知")
    fallback = clean_evidence_text(evidence)
    summary = f"{city}当前天气{weather}，气温{temperature}℃，{winddirection}风{windpower}级。"
    if weather == "未知" and fallback:
        summary = fallback

    return (
        "### 简要回答\n"
        f"{summary}\n\n"
        "### 详细说明\n"
        f"- 天气：{weather}\n"
        f"- 气温：{temperature}℃\n"
        f"- 风力：{winddirection}风{windpower}级\n"
        f"- 湿度：{humidity}%\n"
        f"- 发布时间：{reporttime}\n\n"
        "### 温馨提示\n"
        "天气会随时间变化，出发前建议再次查看实时天气；如遇降雨或大风，优先选择防滑鞋、雨具和更轻松的游览节奏。\n\n"
        f"依据：{document_name}"
    )


def normalize_model_answer(answer: str, fallback_document_name: str = "") -> str:
    text = _remove_after_first_source(answer.strip())
    text = _keep_first_structured_answer(text)
    text = _clean_lines_preserving_template(text)

    if not all(heading in text for heading in STRUCTURED_HEADINGS):
        return format_extract_answer(fallback_document_name or "景区资料", text)
    if "依据：" not in text:
        text = f"{text.rstrip()}\n\n依据：{fallback_document_name or '景区资料'}"
    return text.strip()


def _remove_after_first_source(text: str) -> str:
    match = re.search(r"依据：([^\n#]+)", text)
    if not match:
        return text
    return text[: match.end()].strip()


def _keep_first_structured_answer(text: str) -> str:
    first = text.find("### 简要回答")
    if first == -1:
        return text
    second = text.find("### 简要回答", first + len("### 简要回答"))
    if second == -1:
        return text
    return text[:second].strip()


def _clean_lines_preserving_template(text: str) -> str:
    cleaned_lines = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line in STRUCTURED_HEADINGS or line.startswith("依据："):
            cleaned_lines.append(line)
            continue
        if line.startswith("### "):
            continue
        line = clean_evidence_text(line, max_length=500)
        if line:
            cleaned_lines.append(line)
        elif cleaned_lines and cleaned_lines[-1] != "":
            cleaned_lines.append("")
    return "\n".join(cleaned_lines).strip()
