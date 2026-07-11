import json
import math
from pathlib import Path
from typing import Any, Protocol


class VectorStore(Protocol):
    path: Path

    def upsert(self, records: list[dict[str, Any]]) -> None:
        ...

    def search(self, query_embedding: list[float], top_k: int) -> list[dict[str, Any]]:
        ...

    def list_records(self) -> list[dict[str, Any]]:
        ...

    def delete_document(self, document_id: str) -> None:
        ...

    def count(self) -> int:
        ...


class JsonVectorStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def upsert(self, records: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._load()
        by_id = {record["chunk_id"]: record for record in existing}
        for record in records:
            by_id[record["chunk_id"]] = record
        self.path.write_text(
            json.dumps(list(by_id.values()), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def search(self, query_embedding: list[float], top_k: int) -> list[dict[str, Any]]:
        scored = []
        for record in self._load():
            score = self._cosine(query_embedding, record.get("embedding", []))
            scored.append({**record, "score": score})
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]

    def count(self) -> int:
        return len(self._load())

    def list_records(self) -> list[dict[str, Any]]:
        return self._load()

    def delete_document(self, document_id: str) -> None:
        records = [record for record in self._load() if record.get("document_id") != document_id]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _cosine(self, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)
