from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lingjing_ai.config.settings import AppSettings
from lingjing_ai.rag.embedding_factory import build_embedding_provider
from lingjing_ai.rag.generator import ExtractiveAnswerGenerator
from lingjing_ai.rag.pipeline import RagPipeline
from lingjing_ai.services.document_manifest import DocumentManifestStore
from lingjing_ai.storage.qdrant_vector_store import QdrantVectorStore


@dataclass(frozen=True)
class RebuildResult:
    document_count: int
    indexed_chunks: int
    collection_name: str
    embedding_dimensions: int
    vector_store_path: Path


def rebuild_vector_store(workspace_dir: Path) -> RebuildResult:
    settings = AppSettings.for_workspace(workspace_dir)
    manifest = DocumentManifestStore(
        manifest_path=settings.data_dir / "document_manifest.json",
        uploaded_dir=settings.data_dir / "uploaded",
    )
    records = manifest.list_records()
    if not records:
        return RebuildResult(
            document_count=0,
            indexed_chunks=0,
            collection_name=settings.vector_collection_name,
            embedding_dimensions=settings.embedding_dimensions,
            vector_store_path=settings.qdrant_db_dir,
        )

    vector_store = QdrantVectorStore(
        path=settings.qdrant_db_dir,
        collection_name=settings.vector_collection_name,
        vector_size=settings.embedding_dimensions,
        recreate=True,
    )
    pipeline = RagPipeline(
        settings=settings,
        embedding_provider=build_embedding_provider(settings),
        vector_store=vector_store,
        answer_generator=ExtractiveAnswerGenerator(),
    )

    indexed_chunks = 0
    for record in records:
        source_path = Path(record.saved_path)
        if not source_path.is_file():
            continue
        text = source_path.read_text(encoding="utf-8")
        indexed_chunks += pipeline._index_text(  # noqa: SLF001
            record.document_id,
            record.document_name,
            text,
            {"file_md5": record.file_md5},
        )

    pipeline.invalidate_answer_cache()
    return RebuildResult(
        document_count=len(records),
        indexed_chunks=indexed_chunks,
        collection_name=vector_store.collection_name,
        embedding_dimensions=settings.embedding_dimensions,
        vector_store_path=settings.qdrant_db_dir,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="根据资料清单重建 RAG 向量库。")
    parser.add_argument("--workspace", default=".", help="项目工作目录，默认使用当前目录。")
    args = parser.parse_args(argv)

    workspace_dir = Path(args.workspace).expanduser().resolve()
    result = rebuild_vector_store(workspace_dir)
    if result.document_count == 0:
        print("没有可重建的资料，请先上传或导入资料。")
        return 0

    print("向量库重建完成")
    print(f"资料数量：{result.document_count}")
    print(f"写入切片：{result.indexed_chunks}")
    print(f"Collection：{result.collection_name}")
    print(f"Embedding 维度：{result.embedding_dimensions}")
    print(f"向量库路径：{result.vector_store_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
