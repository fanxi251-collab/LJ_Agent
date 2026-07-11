from pathlib import Path
from typing import Any
import hashlib

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointIdsList,
    PointStruct,
    VectorParams,
)


class QdrantVectorStore:
    def __init__(self, path: Path, collection_name: str, vector_size: int, recreate: bool = False) -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.base_collection_name = collection_name
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.was_recreated = False
        self.client = QdrantClient(path=str(self.path))
        self._resolve_collection_name()
        if recreate and self.client.collection_exists(self.collection_name):
            self._clear_collection()
            self.was_recreated = True
            return
        if not self.client.collection_exists(self.collection_name):
            self._create_collection()
            self.was_recreated = self.collection_name != self.base_collection_name

    def upsert(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        points = [
            PointStruct(
                id=self._point_id(record["chunk_id"]),
                vector=record["embedding"],
                payload={
                    "chunk_id": record["chunk_id"],
                    "document_id": record["document_id"],
                    "document_name": record["document_name"],
                    "content": record["content"],
                    "metadata": record.get("metadata", {}),
                },
            )
            for record in records
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)

    def search(self, query_embedding: list[float], top_k: int) -> list[dict[str, Any]]:
        if self.count() == 0:
            return []
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=top_k,
        )
        matches = []
        for point in response.points:
            payload = point.payload or {}
            matches.append(
                {
                    "chunk_id": str(payload.get("chunk_id", "")),
                    "document_id": str(payload.get("document_id", "")),
                    "document_name": str(payload.get("document_name", "")),
                    "content": str(payload.get("content", "")),
                    "metadata": payload.get("metadata", {}),
                    "score": float(point.score),
                }
            )
        return matches

    def count(self) -> int:
        return self.client.count(collection_name=self.collection_name, exact=True).count

    def list_records(self) -> list[dict[str, Any]]:
        records = []
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                records.append(
                    {
                        "chunk_id": str(payload.get("chunk_id", "")),
                        "document_id": str(payload.get("document_id", "")),
                        "document_name": str(payload.get("document_name", "")),
                        "content": str(payload.get("content", "")),
                        "metadata": payload.get("metadata", {}),
                    }
                )
            if offset is None:
                break
        return records

    def delete_document(self, document_id: str) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )

    def close(self) -> None:
        self.client.close()

    def _point_id(self, chunk_id: str) -> int:
        digest = hashlib.sha256(chunk_id.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big", signed=False)

    def _create_collection(self) -> None:
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
        )

    def _clear_collection(self) -> None:
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=256,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            point_ids = [point.id for point in points]
            if point_ids:
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=PointIdsList(points=point_ids),
                )
            if offset is None:
                break

    def _collection_vector_size(self) -> int | None:
        info = self.client.get_collection(collection_name=self.collection_name)
        vectors = info.config.params.vectors
        if hasattr(vectors, "size"):
            return int(vectors.size)
        if isinstance(vectors, dict):
            first_vector = next(iter(vectors.values()), None)
            if first_vector is not None and hasattr(first_vector, "size"):
                return int(first_vector.size)
        return None

    def _resolve_collection_name(self) -> None:
        if not self.client.collection_exists(self.collection_name):
            return
        if self._collection_vector_size() == self.vector_size and self._stored_vector_size() in (None, self.vector_size):
            return
        # 旧 collection 维度不匹配时改用维度专属 collection，避免删除本地库文件或旧 collection。
        self.collection_name = f"{self.base_collection_name}_dim_{self.vector_size}"
        self.was_recreated = not self.client.collection_exists(self.collection_name)
        if self.client.collection_exists(self.collection_name) and (
            self._collection_vector_size() != self.vector_size
            or self._stored_vector_size() not in (None, self.vector_size)
        ):
            raise ValueError(f"Qdrant collection {self.collection_name} 的向量维度与配置不一致。")

    def _stored_vector_size(self) -> int | None:
        points, _ = self.client.scroll(
            collection_name=self.collection_name,
            limit=1,
            with_payload=False,
            with_vectors=True,
        )
        if not points:
            return None
        vector = points[0].vector
        if isinstance(vector, list):
            return len(vector)
        if isinstance(vector, dict):
            first_vector = next(iter(vector.values()), None)
            if isinstance(first_vector, list):
                return len(first_vector)
        return None
