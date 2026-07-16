from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OfficialSource:
    source_id: str
    title: str
    url: str
    verified_at: str
    valid_until: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OfficialSource":
        return cls(
            source_id=str(payload.get("source_id", "")),
            title=str(payload.get("title", "")),
            url=str(payload.get("url", "")),
            verified_at=str(payload.get("verified_at", "")),
            valid_until=str(payload.get("valid_until", "")),
        )


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    destination: str
    category: str
    difficulty: str
    interaction: str
    question: str
    history: list[dict[str, str]]
    tags: list[str]
    paraphrase_group: str
    expected: dict[str, Any]
    truth: dict[str, Any]
    fixture_ref: str
    offline_response: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvaluationCase":
        return cls(
            case_id=str(payload.get("id", "")),
            destination=str(payload.get("destination", "")),
            category=str(payload.get("category", "")),
            difficulty=str(payload.get("difficulty", "")),
            interaction=str(payload.get("interaction", "")),
            question=str(payload.get("question", "")),
            history=[dict(item) for item in payload.get("history", []) if isinstance(item, dict)],
            tags=[str(item) for item in payload.get("tags", [])],
            paraphrase_group=str(payload.get("paraphrase_group", "")),
            expected=dict(payload.get("expected") or {}),
            truth=dict(payload.get("truth") or {}),
            fixture_ref=str(payload.get("fixture_ref", "")),
            offline_response=dict(payload.get("offline_response") or {}),
        )


@dataclass(frozen=True)
class EvaluationDataset:
    schema_version: str
    dataset_version: str
    metadata: dict[str, Any]
    official_sources: dict[str, OfficialSource]
    tool_fixtures: dict[str, dict[str, Any]]
    cases: list[EvaluationCase]


@dataclass(frozen=True)
class DimensionScore:
    name: str
    score: float
    applicable: bool = True
    details: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    deterministic_score: float
    groundedness_score: float
    freshness_score: float | None
    passed: bool
    critical_failure: bool
    failures: list[str]
    dimensions: dict[str, DimensionScore]
    metrics: dict[str, bool | float | None]
    response: dict[str, Any]
    llm_judge: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "deterministic_score": self.deterministic_score,
            "groundedness_score": self.groundedness_score,
            "freshness_score": self.freshness_score,
            "passed": self.passed,
            "critical_failure": self.critical_failure,
            "failures": self.failures,
            "dimensions": {
                name: {
                    "score": dimension.score,
                    "applicable": dimension.applicable,
                    "details": dimension.details,
                }
                for name, dimension in self.dimensions.items()
            },
            "metrics": self.metrics,
            "response": self.response,
            "llm_judge": self.llm_judge,
        }
