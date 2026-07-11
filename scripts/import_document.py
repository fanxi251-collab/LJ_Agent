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
from lingjing_ai.models.rag import Document
from lingjing_ai.rag.embedding_factory import build_embedding_provider
from lingjing_ai.rag.generator import ExtractiveAnswerGenerator, QwenAnswerGenerator
from lingjing_ai.rag.llm_client import AliyunQwenClient
from lingjing_ai.rag.pipeline import RagPipeline
from lingjing_ai.rag.prompt_loader import load_system_prompt
from lingjing_ai.storage.qdrant_vector_store import QdrantVectorStore


@dataclass(frozen=True)
class ImportResult:
    document: Document
    vector_store_path: Path
    indexed_chunks: int


def import_document(source_path: Path, workspace_dir: Path) -> ImportResult:
    settings = AppSettings.for_workspace(workspace_dir)
    vector_store_path = settings.qdrant_db_dir
    vector_store = QdrantVectorStore(
        path=vector_store_path,
        collection_name=settings.vector_collection_name,
        vector_size=settings.embedding_dimensions,
    )
    pipeline = RagPipeline(
        settings=settings,
        embedding_provider=build_embedding_provider(settings),
        vector_store=vector_store,
        answer_generator=_build_answer_generator(settings),
    )
    before_count = vector_store.count()
    document = pipeline.ingest_file(source_path)
    after_count = vector_store.count()
    return ImportResult(
        document=document,
        vector_store_path=vector_store_path,
        indexed_chunks=max(0, after_count - before_count),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导入单个景区资料文件并写入 RAG 向量库。")
    parser.add_argument("source", help="要导入的资料文件路径，建议使用 UTF-8 编码的 .md 或 .txt 文件。")
    parser.add_argument(
        "--workspace",
        default=".",
        help="项目工作目录，默认使用当前目录。",
    )
    args = parser.parse_args(argv)

    source_path = Path(args.source).expanduser().resolve()
    workspace_dir = Path(args.workspace).expanduser().resolve()
    if not source_path.is_file():
        print(f"资料文件不存在：{source_path}", file=sys.stderr)
        return 1

    result = import_document(source_path, workspace_dir)
    print("资料导入完成")
    print(f"文档名称：{result.document.name}")
    print(f"文档 ID：{result.document.id}")
    print(f"保存路径：{result.document.path}")
    print(f"新增切片：{result.indexed_chunks}")
    print(f"向量库：{result.vector_store_path}")
    return 0


def _build_answer_generator(settings: AppSettings) -> ExtractiveAnswerGenerator | QwenAnswerGenerator:
    if not settings.llm_api_key:
        return ExtractiveAnswerGenerator()
    return QwenAnswerGenerator(
        AliyunQwenClient(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        ),
        system_prompt=load_system_prompt(settings.prompt_dir / "rag_system_prompt.md"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
