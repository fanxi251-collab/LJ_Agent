from __future__ import annotations

import json
import re
from typing import Any

from lingjing_ai.evaluation.models import EvaluationCase
from lingjing_ai.rag.llm_client import LlmClient


class OptionalLlmJudge:
    def __init__(self, client: LlmClient) -> None:
        self.client = client

    def evaluate(self, case: EvaluationCase, answer: str) -> dict[str, Any]:
        prompt = (
            "你是旅游问答评测员。只评价表达质量，不重新判定事实真伪。"
            "请根据问题、参考答案和实际答案，对完整性、实用性、连贯性、导游表达分别给0到5分，"
            "并给出一句中文理由。仅输出JSON对象。\n\n"
            f"问题：{case.question}\n"
            f"参考答案：{case.expected.get('reference_answer', '')}\n"
            f"实际答案：{answer}\n"
            'JSON格式：{"completeness": 0, "helpfulness": 0, "coherence": 0, "guide_style": 0, "reason": ""}'
        )
        raw = self.client.chat([{"role": "user", "content": prompt}]).strip()
        payload = _parse_json_object(raw)
        scores = {
            key: max(0.0, min(5.0, float(payload.get(key, 0))))
            for key in ("completeness", "helpfulness", "coherence", "guide_style")
        }
        weighted = (
            scores["completeness"] * 0.4
            + scores["helpfulness"] * 0.3
            + scores["coherence"] * 0.2
            + scores["guide_style"] * 0.1
        ) * 20
        return {**scores, "score": round(weighted, 2), "reason": str(payload.get("reason", ""))[:300]}


def _parse_json_object(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match is None:
            raise ValueError("LLM 评判器未返回JSON对象。")
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("LLM 评判器返回值必须是JSON对象。")
    return value
