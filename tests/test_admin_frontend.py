import asyncio
from pathlib import Path

import httpx

from lingjing_ai.api.app import create_app
from lingjing_ai.config.settings import AppSettings
from lingjing_ai.rag.embeddings import HashingEmbeddingProvider
from lingjing_ai.rag.generator import ExtractiveAnswerGenerator
from lingjing_ai.rag.pipeline import RagPipeline
from lingjing_ai.storage.vector_store import JsonVectorStore


def build_pipeline(tmp_path: Path) -> RagPipeline:
    settings = AppSettings.for_workspace(tmp_path)
    return RagPipeline(
        settings=settings,
        embedding_provider=HashingEmbeddingProvider(dimensions=64),
        vector_store=JsonVectorStore(tmp_path / "vectors.json"),
        answer_generator=ExtractiveAnswerGenerator(),
    )


def request_path(app, path: str) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)

    return asyncio.run(send())


def test_admin_documents_page_and_assets_are_served(tmp_path: Path):
    app = create_app(build_pipeline(tmp_path))

    page = request_path(app, "/admin/documents")
    script = request_path(app, "/static/admin_documents.js")

    assert page.status_code == 200
    assert "原始资料管理" in page.text
    assert "/static/admin_documents.js" in page.text
    assert script.status_code == 200
    assert 'fetch("/api/admin/documents"' in script.text
    assert 'fetch(`/api/admin/documents/${documentId}/content`' in script.text
    assert 'fetch(`/api/admin/documents/${documentId}/reindex`' in script.text
    assert 'fetch(`/api/admin/documents/${documentId}`' in script.text
    assert "confirm(" in script.text
