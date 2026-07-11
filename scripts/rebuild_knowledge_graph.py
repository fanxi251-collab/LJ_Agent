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
from lingjing_ai.kg.factory import build_knowledge_graph_store
from lingjing_ai.rag.chunker import TextChunker
from lingjing_ai.services.document_manifest import DocumentManifestStore


@dataclass(frozen=True)
class RebuildKnowledgeGraphResult:
    document_count: int
    indexed_chunks: int
    enabled: bool
    node_count: int
    relationship_count: int
    message: str


def rebuild_knowledge_graph(workspace_dir: Path) -> RebuildKnowledgeGraphResult:
    settings = AppSettings.for_workspace(workspace_dir)
    store = build_knowledge_graph_store(settings)
    manifest = DocumentManifestStore(
        manifest_path=settings.data_dir / "document_manifest.json",
        uploaded_dir=settings.data_dir / "uploaded",
    )
    chunker = TextChunker(settings.chunk_size, settings.chunk_overlap)
    indexed_chunks = 0
    records = manifest.list_records()

    for record in records:
        source_path = Path(record.saved_path)
        if not source_path.is_file():
            continue
        text = source_path.read_text(encoding="utf-8")
        chunks = chunker.split(record.document_id, record.document_name, text)
        store.clear_document(record.document_id)
        store.index_chunks(chunks)
        indexed_chunks += len(chunks)

    status = store.status()
    return RebuildKnowledgeGraphResult(
        document_count=len(records),
        indexed_chunks=indexed_chunks,
        enabled=bool(status.get("enabled")),
        node_count=int(status.get("node_count", 0)),
        relationship_count=int(status.get("relationship_count", 0)),
        message=str(status.get("message", "")),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="根据资料清单重建 Neo4j 知识图谱。")
    parser.add_argument("--workspace", default=".", help="项目工作目录，默认使用当前目录。")
    args = parser.parse_args(argv)

    result = rebuild_knowledge_graph(Path(args.workspace).expanduser().resolve())
    print("知识图谱重建完成" if result.enabled else "知识图谱未启用")
    print(f"资料数量：{result.document_count}")
    print(f"处理切片：{result.indexed_chunks}")
    print(f"节点数量：{result.node_count}")
    print(f"关系数量：{result.relationship_count}")
    print(f"状态信息：{result.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
