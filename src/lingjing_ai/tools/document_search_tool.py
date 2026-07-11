from collections import Counter
import re

from lingjing_ai.agent.models import ToolResult
from lingjing_ai.models.rag import SourceChunk
from lingjing_ai.rag.pipeline import RagPipeline


class DocumentSearchTool:
    name = "document_search"

    def __init__(self, pipeline: RagPipeline) -> None:
        self.pipeline = pipeline

    def run(self, query: str) -> ToolResult:
        query_tokens = _tokens(query)
        sources: list[SourceChunk] = []
        for record in self.pipeline.list_documents():
            content = self.pipeline.get_document_content(record.document_id)
            if not content:
                continue
            score = _score(query_tokens, f"{record.document_name} {content}")
            if score <= 0:
                continue
            snippet = _snippet(content, query_tokens)
            sources.append(
                SourceChunk(
                    chunk_id=f"{record.document_id}_document_match",
                    document_id=record.document_id,
                    document_name=record.document_name,
                    content=snippet,
                    score=min(0.92, 0.55 + score),
                    metadata={"source_type": "document"},
                )
            )
        sources.sort(key=lambda source: source.score, reverse=True)
        status = "ok" if sources else "empty"
        message = "已检索原始资料" if sources else "原始资料未命中相关内容"
        return ToolResult(status=status, message=message, sources=sources[: self.pipeline.settings.top_k])


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9_\u4e00-\u9fff]+", text.lower())
    tokens: list[str] = []
    for word in words:
        tokens.append(word)
        if len(word) > 2 and any("\u4e00" <= char <= "\u9fff" for char in word):
            tokens.extend(word[index : index + 2] for index in range(len(word) - 1))
    return tokens


def _score(query_tokens: list[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    text_tokens = Counter(_tokens(text))
    hits = sum(1 for token in set(query_tokens) if token in text_tokens)
    return hits / max(1, len(set(query_tokens)))


def _snippet(content: str, query_tokens: list[str]) -> str:
    compact = re.sub(r"\s+", " ", content).strip()
    if len(compact) <= 300:
        return compact
    positions = [compact.find(token) for token in query_tokens if token and compact.find(token) >= 0]
    start = max(0, min(positions) - 80) if positions else 0
    return compact[start : start + 300].strip()
