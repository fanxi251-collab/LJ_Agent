from dataclasses import replace
from datetime import date
import json
from pathlib import Path

from lingjing_ai.evaluation.judge import OptionalLlmJudge
from lingjing_ai.evaluation.loader import load_dataset
from lingjing_ai.evaluation.reporter import build_report, write_report
from lingjing_ai.evaluation.scoring import score_case
from lingjing_ai.evaluation.validator import validate_dataset


DATASET_PATH = Path("evaluation/datasets/lingjing_qa_v1.json")


class FakeJudgeClient:
    def chat(self, messages):
        return json.dumps(
            {
                "completeness": 5,
                "helpfulness": 4,
                "coherence": 5,
                "guide_style": 4,
                "reason": "答案完整且表达自然。",
            },
            ensure_ascii=False,
        )


def test_dataset_has_required_version_distributions_and_legacy_migrations():
    dataset = load_dataset(DATASET_PATH)

    assert validate_dataset(dataset) == []
    assert len(dataset.cases) == 120
    assert sum("online-smoke" in case.tags for case in dataset.cases) == 8
    assert sum("legacy-rag-eval" in case.tags for case in dataset.cases) == 3
    assert dataset.metadata["distribution"] == {
        "category": {
            "factual": 30,
            "explanation": 15,
            "planning": 20,
            "tool": 15,
            "multi_turn": 15,
            "refusal_safety": 15,
            "robustness": 10,
        },
        "difficulty": {"easy": 40, "medium": 55, "hard": 25},
        "destination": {"灵山胜境": 102, "拈花湾": 18},
    }


def test_every_answerable_case_has_reference_evidence_and_safe_offline_response():
    dataset = load_dataset(DATASET_PATH)

    for case in dataset.cases:
        assert case.expected["reference_answer"].strip()
        if case.expected["answerable"]:
            assert case.truth["local_evidence"]
        serialized = json.dumps(case.offline_response, ensure_ascii=False).lower()
        for forbidden_key in ("visitor_id", "tourist_id", "user_nickname", "api_key", "redis_url"):
            assert forbidden_key not in serialized


def test_fixed_offline_responses_produce_a_stable_full_score():
    dataset = load_dataset(DATASET_PATH)

    first = [score_case(case, case.offline_response).to_dict() for case in dataset.cases]
    second = [score_case(case, case.offline_response).to_dict() for case in dataset.cases]

    assert first == second
    assert all(item["passed"] for item in first)
    assert all(item["deterministic_score"] == 100.0 for item in first)


def test_scorer_flags_forbidden_fact_missing_source_and_wrong_tool():
    dataset = load_dataset(DATASET_PATH)
    case = next(case for case in dataset.cases if case.case_id == "qa_tool_003")
    response = {
        **case.offline_response,
        "answer": "固定为13:30、15:00，驾车约42.0公里。",
        "sources": [],
        "tool_trace": [{"tool_name": "amap_weather"}],
    }
    case = replace(
        case,
        expected={**case.expected, "forbidden_claims": ["13:30、15:00"]},
    )

    result = score_case(case, response)

    assert result.passed is False
    assert result.critical_failure is True
    assert result.metrics["retrieval_hit"] is False
    assert result.metrics["tool_correct"] is False
    assert result.metrics["forbidden_fact_hit"] is True


def test_scorer_accepts_refusal_and_clarification_as_separate_behaviors():
    dataset = load_dataset(DATASET_PATH)
    refusal = next(case for case in dataset.cases if case.case_id == "qa_refusal_safety_006")
    clarification = next(case for case in dataset.cases if case.case_id == "qa_multi_turn_006")

    assert score_case(refusal, refusal.offline_response).passed is True
    clarification_score = score_case(clarification, clarification.offline_response)
    assert clarification_score.passed is True
    assert clarification_score.metrics["answerability_correct"] is True


def test_expired_dynamic_fact_has_no_freshness_score():
    dataset = load_dataset(DATASET_PATH)
    case = next(case for case in dataset.cases if case.case_id == "qa_factual_016")

    current = score_case(case, case.offline_response, today=date(2026, 7, 20))
    expired = score_case(case, case.offline_response, today=date(2026, 9, 1))

    assert current.freshness_score == 100.0
    assert expired.freshness_score is None


def test_optional_llm_judge_returns_separate_expression_score():
    dataset = load_dataset(DATASET_PATH)
    case = dataset.cases[0]

    result = OptionalLlmJudge(FakeJudgeClient()).evaluate(case, case.expected["reference_answer"])

    assert result["score"] == 92.0
    assert result["reason"] == "答案完整且表达自然。"


def test_report_groups_failures_and_redacts_sensitive_values(tmp_path: Path):
    dataset = load_dataset(DATASET_PATH)
    selected = dataset.cases[:2]
    scores = [score_case(case, case.offline_response) for case in selected]

    report = build_report(
        dataset,
        scores,
        mode="offline",
        runtime={"note": "password=secret api_key=hidden", "redis_url": "redis://secret"},
    )
    json_path, markdown_path = write_report(report, tmp_path)
    serialized = json_path.read_text(encoding="utf-8")

    assert report["summary"]["deterministic_score"] == 100.0
    assert "redis_url" not in report["runtime"]
    assert "secret" not in serialized
    assert json_path.is_file()
    assert markdown_path.is_file()
