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


def test_visitor_page_is_served_by_fastapi(tmp_path: Path):
    app = create_app(build_pipeline(tmp_path))

    response = request_path(app, "/visitor")

    assert response.status_code == 200
    assert 'id="app"' in response.text
    assert "Vue 游客端尚未构建" in response.text or "/assets/" in response.text


def test_vue_source_contains_required_visitor_layout_and_api_calls():
    app_source = Path("frontend/src/App.vue").read_text(encoding="utf-8")
    chat_source = Path("frontend/src/components/ChatMain.vue").read_text(encoding="utf-8")
    session_source = Path("frontend/src/components/SessionSidebar.vue").read_text(encoding="utf-8")
    chat_composable = Path("frontend/src/composables/useChat.js").read_text(encoding="utf-8")
    session_composable = Path("frontend/src/composables/useSessions.js").read_text(encoding="utf-8")
    styles = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "visitor-layout" in app_source
    assert "chat-main" in chat_source
    assert "session-sidebar" in session_source
    assert "history-side" in app_source
    assert "给 LingJing AI 发送消息" in chat_source
    assert '"/api/agent/chat/stream"' in chat_composable
    assert '"/api/rag/chat/stream"' in chat_composable
    assert "visitor_id: visitorId" in chat_composable
    assert "session_id: currentSessionId.value" in chat_composable
    assert '"/api/visitor/sessions?visitor_id="' in session_composable
    assert "`/api/visitor/sessions/${currentSessionId.value}?" in session_composable
    assert ".history-side" in styles
    assert ".composer-card" in styles


def test_legacy_admin_assets_are_still_served(tmp_path: Path):
    app = create_app(build_pipeline(tmp_path))

    script_response = request_path(app, "/static/admin_documents.js")
    style_response = request_path(app, "/static/app.css")

    assert script_response.status_code == 200
    assert 'fetch("/api/admin/documents"' in script_response.text
    assert style_response.status_code == 200
    assert ".source-meta" in style_response.text
