from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import json

from lingjing_ai.models.rag import DocumentRecord


class DocumentManifestStore:
    def __init__(self, manifest_path: Path, uploaded_dir: Path) -> None:
        self.manifest_path = Path(manifest_path)
        self.uploaded_dir = Path(uploaded_dir)

    def list_records(self) -> list[DocumentRecord]:
        records = self._load()
        known_ids = {record.document_id for record in records}
        for path in self._uploaded_files():
            document_id = path.stem
            if document_id in known_ids:
                continue
            records.append(self._record_from_file(path))
        records.sort(key=lambda record: record.updated_at, reverse=True)
        return records

    def get(self, document_id: str) -> DocumentRecord | None:
        for record in self.list_records():
            if record.document_id == document_id:
                return record
        return None

    def upsert(self, record: DocumentRecord) -> None:
        records = [item for item in self._load() if item.document_id != record.document_id]
        records.append(record)
        records.sort(key=lambda item: item.updated_at, reverse=True)
        self._save(records)

    def remove(self, document_id: str) -> None:
        records = [record for record in self._load() if record.document_id != document_id]
        self._save(records)

    def _load(self) -> list[DocumentRecord]:
        if not self.manifest_path.exists():
            return []
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return [DocumentRecord(**item) for item in data]

    def _save(self, records: list[DocumentRecord]) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(record) for record in records]
        self.manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _uploaded_files(self) -> list[Path]:
        if not self.uploaded_dir.exists():
            return []
        return [
            path
            for path in self.uploaded_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".txt", ".md"}
        ]

    def _record_from_file(self, path: Path) -> DocumentRecord:
        stat = path.stat()
        created_at = datetime.fromtimestamp(stat.st_ctime, timezone.utc).isoformat()
        updated_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
        return DocumentRecord(
            document_id=path.stem,
            document_name=path.name,
            saved_path=str(path),
            file_md5="",
            file_size=stat.st_size,
            indexed_chunks=0,
            created_at=created_at,
            updated_at=updated_at,
        )
