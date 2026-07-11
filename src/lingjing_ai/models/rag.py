from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Document:
    id: str
    name: str
    path: str


@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    document_name: str
    saved_path: str
    file_md5: str
    file_size: int
    indexed_chunks: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class SourceChunk:
    chunk_id: str
    document_id: str
    document_name: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    sources: list[SourceChunk]
    confidence: float
    is_answered: bool
    trace_id: str
    needs_clarification: bool = False
    clarifying_question: str = ""
