import json

from lingjing_ai.storage.qdrant_vector_store import QdrantVectorStore


def test_qdrant_vector_store_persists_records_between_instances(tmp_path):
    first_store = QdrantVectorStore(
        path=tmp_path / "qdrant_db",
        collection_name="lingjing_scenic_knowledge_test",
        vector_size=3,
    )
    first_store.upsert(
        [
            {
                "chunk_id": "doc_1_chunk_0",
                "document_id": "doc_1",
                "document_name": "灵境山资料.md",
                "content": "灵境山以云海日出和古栈道闻名。",
                "metadata": {"file_md5": "abc", "chunk_index": "0"},
                "embedding": [1.0, 0.0, 0.0],
            }
        ]
    )
    first_store.close()

    second_store = QdrantVectorStore(
        path=tmp_path / "qdrant_db",
        collection_name="lingjing_scenic_knowledge_test",
        vector_size=3,
    )
    results = second_store.search([1.0, 0.0, 0.0], top_k=1)

    assert second_store.count() == 1
    assert results[0]["chunk_id"] == "doc_1_chunk_0"
    assert results[0]["document_name"] == "灵境山资料.md"
    assert results[0]["content"] == "灵境山以云海日出和古栈道闻名。"
    assert results[0]["score"] > 0.99
    records = second_store.list_records()
    assert records[0]["chunk_id"] == "doc_1_chunk_0"
    assert records[0]["document_name"] == "灵境山资料.md"
    second_store.delete_document("doc_1")
    assert second_store.count() == 0
    second_store.close()


def test_qdrant_vector_store_recreates_collection_when_vector_size_changes(tmp_path):
    old_store = QdrantVectorStore(
        path=tmp_path / "qdrant_db",
        collection_name="lingjing_scenic_knowledge_test",
        vector_size=3,
    )
    old_store.upsert(
        [
            {
                "chunk_id": "doc_1_chunk_0",
                "document_id": "doc_1",
                "document_name": "旧资料.md",
                "content": "旧向量资料。",
                "metadata": {},
                "embedding": [1.0, 0.0, 0.0],
            }
        ]
    )
    old_store.close()

    new_store = QdrantVectorStore(
        path=tmp_path / "qdrant_db",
        collection_name="lingjing_scenic_knowledge_test",
        vector_size=5,
    )

    assert new_store.was_recreated is True
    assert new_store.count() == 0
    new_store.upsert(
        [
            {
                "chunk_id": "doc_1_chunk_0",
                "document_id": "doc_1",
                "document_name": "新资料.md",
                "content": "新向量资料。",
                "metadata": {},
                "embedding": [1.0, 0.0, 0.0, 0.0, 0.0],
            }
        ]
    )
    assert new_store.search([1.0, 0.0, 0.0, 0.0, 0.0], top_k=1)[0]["document_name"] == "新资料.md"
    new_store.close()


def test_qdrant_vector_store_switches_collection_when_meta_size_masks_old_vectors(tmp_path):
    old_store = QdrantVectorStore(
        path=tmp_path / "qdrant_db",
        collection_name="lingjing_scenic_knowledge_test",
        vector_size=3,
    )
    old_store.upsert(
        [
            {
                "chunk_id": "doc_1_chunk_0",
                "document_id": "doc_1",
                "document_name": "旧资料.md",
                "content": "旧向量资料。",
                "metadata": {},
                "embedding": [1.0, 0.0, 0.0],
            }
        ]
    )
    old_store.close()

    meta_path = tmp_path / "qdrant_db" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["collections"]["lingjing_scenic_knowledge_test"]["vectors"]["size"] = 5
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    new_store = QdrantVectorStore(
        path=tmp_path / "qdrant_db",
        collection_name="lingjing_scenic_knowledge_test",
        vector_size=5,
    )

    assert new_store.collection_name == "lingjing_scenic_knowledge_test_dim_5"
    assert new_store.was_recreated is True
    assert new_store.count() == 0
    new_store.close()


def test_qdrant_vector_store_recreate_clears_matching_collection(tmp_path):
    old_store = QdrantVectorStore(
        path=tmp_path / "qdrant_db",
        collection_name="lingjing_scenic_knowledge_test",
        vector_size=3,
    )
    old_store.upsert(
        [
            {
                "chunk_id": "old_chunk",
                "document_id": "old_doc",
                "document_name": "旧资料.md",
                "content": "旧向量资料。",
                "metadata": {},
                "embedding": [1.0, 0.0, 0.0],
            }
        ]
    )
    old_store.close()

    recreated_store = QdrantVectorStore(
        path=tmp_path / "qdrant_db",
        collection_name="lingjing_scenic_knowledge_test",
        vector_size=3,
        recreate=True,
    )

    assert recreated_store.was_recreated is True
    assert recreated_store.collection_name == "lingjing_scenic_knowledge_test"
    assert recreated_store.count() == 0
    recreated_store.close()
