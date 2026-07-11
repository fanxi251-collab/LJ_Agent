from collections import Counter, defaultdict
import math
import re
from typing import Any

from lingjing_ai.rag.embeddings import HashingEmbeddingProvider
from lingjing_ai.rag.question_type import classify_question
from lingjing_ai.storage.vector_store import VectorStore


class HybridRetriever:
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_provider: HashingEmbeddingProvider,
        vector_top_k: int,
        keyword_top_k: int,
        rerank_top_k: int,
        rrf_k: int,
    ) -> None:
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.vector_top_k = vector_top_k
        self.keyword_top_k = keyword_top_k
        self.rerank_top_k = rerank_top_k
        self.rrf_k = rrf_k

    def retrieve(self, question: str, top_k: int, min_score: float) -> list[dict[str, Any]]:
        vector_results = self._vector_search(question)
        keyword_results = self._keyword_search(question)
        fused = self._fuse(vector_results, keyword_results)
        reranked = self._rerank(question, fused)
        return [record for record in reranked if record["score"] >= min_score][:top_k]

    def _vector_search(self, question: str) -> list[dict[str, Any]]:
        if self.vector_top_k <= 0:
            return []
        query_embedding = self.embedding_provider.embed(question)
        return self.vector_store.search(query_embedding, top_k=self.vector_top_k)

    def _keyword_search(self, question: str) -> list[dict[str, Any]]:
        if self.keyword_top_k <= 0:
            return []

        records = self.vector_store.list_records()
        query_tokens = _tokens(question)
        if not records or not query_tokens:
            return []

        document_tokens = [_tokens(f"{record.get('document_name', '')} {record.get('content', '')}") for record in records]
        document_frequency = Counter()
        for tokens in document_tokens:
            document_frequency.update(set(tokens))

        average_length = sum(len(tokens) for tokens in document_tokens) / max(1, len(document_tokens))
        scored = []
        for record, tokens in zip(records, document_tokens):
            score = _bm25_score(query_tokens, tokens, document_frequency, len(records), average_length)
            if score > 0:
                scored.append({**record, "score": score})
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[: self.keyword_top_k]

    def _fuse(self, vector_results: list[dict[str, Any]], keyword_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_chunk: dict[str, dict[str, Any]] = {}
        signals: dict[str, dict[str, float]] = defaultdict(lambda: {"rrf": 0.0, "vector": 0.0, "keyword": 0.0})

        for rank, record in enumerate(vector_results, start=1):
            chunk_id = str(record["chunk_id"])
            by_chunk[chunk_id] = record
            signals[chunk_id]["rrf"] += 1.0 / (self.rrf_k + rank)
            signals[chunk_id]["vector"] = max(signals[chunk_id]["vector"], float(record.get("score", 0.0)))

        for rank, record in enumerate(keyword_results, start=1):
            chunk_id = str(record["chunk_id"])
            by_chunk[chunk_id] = {**by_chunk.get(chunk_id, {}), **record}
            signals[chunk_id]["rrf"] += 1.0 / (self.rrf_k + rank)
            signals[chunk_id]["keyword"] = max(signals[chunk_id]["keyword"], float(record.get("score", 0.0)))

        fused = []
        for chunk_id, record in by_chunk.items():
            fused.append({**record, "retrieval_signals": signals[chunk_id]})
        fused.sort(key=lambda item: item["retrieval_signals"]["rrf"], reverse=True)
        return fused[: self.rerank_top_k]

    def _rerank(self, question: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        query_tokens = set(_tokens(question))
        if not query_tokens:
            return records

        question_category = classify_question(question).category
        max_keyword = max((record["retrieval_signals"]["keyword"] for record in records), default=0.0) or 1.0
        seen_documents: set[str] = set()
        reranked = []
        for record in records:
            text = f"{record.get('document_name', '')} {record.get('content', '')}"
            text_tokens = set(_tokens(text))
            name_tokens = set(_tokens(str(record.get("document_name", ""))))
            signals = record["retrieval_signals"]

            coverage = len(query_tokens & text_tokens) / max(1, len(query_tokens))
            title_match = len(query_tokens & name_tokens) / max(1, len(query_tokens))
            keyword_score = signals["keyword"] / max_keyword
            vector_score = max(0.0, min(1.0, signals["vector"]))
            fused_score = min(1.0, signals["rrf"] * 8.0)
            category_match = 1.0 if record.get("metadata", {}).get("category") == question_category else 0.0

            score = (
                (fused_score * 0.20)
                + (keyword_score * 0.22)
                + (coverage * 0.28)
                + (title_match * 0.08)
                + (vector_score * 0.10)
                + (category_match * 0.12)
            )
            document_id = str(record.get("document_id", ""))
            if document_id in seen_documents:
                score *= 0.92
            seen_documents.add(document_id)
            reranked.append({**record, "score": min(1.0, score)})

        reranked.sort(key=lambda item: item["score"], reverse=True)
        return reranked


def _tokens(text: str) -> list[str]:
    lowered = text.lower()
    words = re.findall(r"[a-z0-9]+", lowered)
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", lowered)
    chinese_bigrams = [
        "".join(chinese_chars[index : index + 2])
        for index in range(0, max(0, len(chinese_chars) - 1))
    ]
    return words + chinese_chars + chinese_bigrams


def _bm25_score(
    query_tokens: list[str],
    document_tokens: list[str],
    document_frequency: Counter,
    document_count: int,
    average_length: float,
) -> float:
    counts = Counter(document_tokens)
    score = 0.0
    k1 = 1.5
    b = 0.75
    document_length = len(document_tokens)
    for token in set(query_tokens):
        frequency = counts[token]
        if frequency == 0:
            continue
        idf = math.log(1 + (document_count - document_frequency[token] + 0.5) / (document_frequency[token] + 0.5))
        denominator = frequency + k1 * (1 - b + b * document_length / max(1.0, average_length))
        score += idf * (frequency * (k1 + 1)) / denominator
    return score
