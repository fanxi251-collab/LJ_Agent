from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "tourism_analytics_v1"
REQUIRED_SECTIONS = {
    "metadata": dict,
    "kpis": dict,
    "monthly_trend": list,
    "demographics": dict,
    "attraction_types": list,
    "attraction_rankings": dict,
    "consumption": dict,
    "satisfaction": dict,
    "insights": list,
    "quality": dict,
}


class AnalyticsSnapshotError(RuntimeError):
    """Represent an unavailable snapshot so the API can degrade without blocking startup."""


class AnalyticsSnapshotStore:
    def __init__(self, snapshot_path: str | Path):
        self.snapshot_path = Path(snapshot_path)

    def load(self) -> dict[str, Any]:
        if not self.snapshot_path.is_file():
            raise AnalyticsSnapshotError(f"游客分析快照不存在：{self.snapshot_path}")
        try:
            payload = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AnalyticsSnapshotError(f"游客分析快照无法读取：{exc}") from exc
        self._validate(payload)
        return payload

    @staticmethod
    def _validate(payload: Any) -> None:
        if not isinstance(payload, dict):
            raise AnalyticsSnapshotError("游客分析快照顶层结构必须是对象。")
        for name, expected_type in REQUIRED_SECTIONS.items():
            if name not in payload or not isinstance(payload[name], expected_type):
                raise AnalyticsSnapshotError(f"游客分析快照缺少或损坏字段：{name}")
        if payload["metadata"].get("schema_version") != SCHEMA_VERSION:
            raise AnalyticsSnapshotError("游客分析快照版本不兼容，请重新生成。")
