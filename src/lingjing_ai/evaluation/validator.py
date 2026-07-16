from __future__ import annotations

from collections import Counter
from datetime import date
import re

from lingjing_ai.evaluation.models import EvaluationDataset


EXPECTED_CATEGORIES = {
    "factual": 30,
    "explanation": 15,
    "planning": 20,
    "tool": 15,
    "multi_turn": 15,
    "refusal_safety": 15,
    "robustness": 10,
}
EXPECTED_DIFFICULTIES = {"easy": 40, "medium": 55, "hard": 25}
EXPECTED_DESTINATIONS = {"灵山胜境": 102, "拈花湾": 18}
VALID_FRESHNESS = {"not_applicable", "verified", "conflict", "dynamic_fixture", "needs_review"}
MD5_PATTERN = re.compile(r"^[a-f0-9]{32}$")


def validate_dataset(dataset: EvaluationDataset) -> list[str]:
    errors: list[str] = []
    if dataset.schema_version != "tourism_qa_eval_v1":
        errors.append("schema_version 必须为 tourism_qa_eval_v1。")
    if len(dataset.cases) != 120:
        errors.append(f"评测集必须恰好包含120题，实际为{len(dataset.cases)}题。")

    ids = [case.case_id for case in dataset.cases]
    duplicates = sorted(case_id for case_id, count in Counter(ids).items() if count > 1)
    if duplicates:
        errors.append("存在重复用例ID：" + "、".join(duplicates))
    if any(not re.fullmatch(r"qa_[a-z_]+_\d{3}", case_id) for case_id in ids):
        errors.append("用例ID必须符合 qa_<category>_<三位序号>。")

    _validate_distribution(errors, "分类", Counter(case.category for case in dataset.cases), EXPECTED_CATEGORIES)
    _validate_distribution(errors, "难度", Counter(case.difficulty for case in dataset.cases), EXPECTED_DIFFICULTIES)
    _validate_distribution(errors, "景区", Counter(case.destination for case in dataset.cases), EXPECTED_DESTINATIONS)

    for case in dataset.cases:
        _validate_case(dataset, case, errors)
    return errors


def _validate_distribution(errors: list[str], label: str, actual: Counter, expected: dict[str, int]) -> None:
    if dict(actual) != expected:
        errors.append(f"{label}分布不正确：期望{expected}，实际{dict(actual)}。")


def _validate_case(dataset: EvaluationDataset, case, errors: list[str]) -> None:
    prefix = case.case_id or "<missing-id>"
    if not case.question.strip():
        errors.append(f"{prefix}: question 不能为空。")
    if case.interaction not in {"single_turn", "multi_turn"}:
        errors.append(f"{prefix}: interaction 非法。")
    if case.interaction == "multi_turn" and not case.history:
        errors.append(f"{prefix}: 多轮用例必须包含 history。")

    expected = case.expected
    answerable = expected.get("answerable")
    if not isinstance(answerable, bool):
        errors.append(f"{prefix}: expected.answerable 必须是布尔值。")
    if not str(expected.get("reference_answer", "")).strip():
        errors.append(f"{prefix}: 必须提供 reference_answer。")
    if answerable and not case.truth.get("local_evidence"):
        errors.append(f"{prefix}: 可回答题必须提供 local_evidence。")

    freshness = str(case.truth.get("freshness_status", ""))
    if freshness not in VALID_FRESHNESS:
        errors.append(f"{prefix}: freshness_status 非法。")
    for evidence in case.truth.get("local_evidence", []):
        md5 = str(evidence.get("document_md5", ""))
        if not MD5_PATTERN.fullmatch(md5):
            errors.append(f"{prefix}: local_evidence.document_md5 必须是32位MD5。")
        if not str(evidence.get("excerpt", "")).strip():
            errors.append(f"{prefix}: local_evidence.excerpt 不能为空。")

    official_refs = [str(item) for item in case.truth.get("official_source_refs", [])]
    if freshness in {"verified", "conflict"} and not official_refs:
        errors.append(f"{prefix}: 动态核验题必须引用官方来源。")
    for source_id in official_refs:
        if source_id not in dataset.official_sources:
            errors.append(f"{prefix}: 官方来源 {source_id} 不存在。")
    if freshness in {"verified", "conflict"}:
        verified_at = str(case.truth.get("verified_at", ""))
        valid_until = str(case.truth.get("valid_until", ""))
        try:
            if date.fromisoformat(valid_until) < date.fromisoformat(verified_at):
                errors.append(f"{prefix}: valid_until 不能早于 verified_at。")
        except ValueError:
            errors.append(f"{prefix}: verified_at/valid_until 必须使用 YYYY-MM-DD。")

    if case.fixture_ref and case.fixture_ref not in dataset.tool_fixtures:
        errors.append(f"{prefix}: fixture_ref {case.fixture_ref} 不存在。")
    if not case.offline_response:
        errors.append(f"{prefix}: 必须提供固定 offline_response。")

    sensitive_text = str(case.offline_response).lower()
    for marker in ("api_key", "redis_url", "visitor_id", "user_nickname", "tourist_id"):
        if marker in sensitive_text:
            errors.append(f"{prefix}: offline_response 包含敏感字段 {marker}。")
