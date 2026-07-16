from __future__ import annotations

import json
from pathlib import Path

from lingjing_ai.evaluation.models import EvaluationCase, EvaluationDataset, OfficialSource


def load_dataset(path: Path | str) -> EvaluationDataset:
    dataset_path = Path(path)
    try:
        payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取评测集 {dataset_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("评测集顶层必须是 JSON 对象。")

    sources = {
        str(item.get("source_id", "")): OfficialSource.from_dict(item)
        for item in payload.get("official_sources", [])
        if isinstance(item, dict)
    }
    return EvaluationDataset(
        schema_version=str(payload.get("schema_version", "")),
        dataset_version=str(payload.get("dataset_version", "")),
        metadata=dict(payload.get("metadata") or {}),
        official_sources=sources,
        tool_fixtures={
            str(key): dict(value)
            for key, value in (payload.get("tool_fixtures") or {}).items()
            if isinstance(value, dict)
        },
        cases=[EvaluationCase.from_dict(item) for item in payload.get("cases", []) if isinstance(item, dict)],
    )
