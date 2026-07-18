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
    assert "知识库资料管理" in page.text
    assert "/static/admin_documents.js" in page.text
    assert script.status_code == 200
    assert 'fetch("/api/admin/documents"' in script.text
    assert 'fetch(`/api/admin/documents/${documentId}/content`' in script.text
    assert 'fetch(`/api/admin/documents/${documentId}/reindex`' in script.text
    assert 'fetch(`/api/admin/documents/${documentId}`' in script.text
    assert "confirm(" in script.text


def test_admin_attractions_page_and_crud_assets_are_served(tmp_path: Path):
    app = create_app(build_pipeline(tmp_path))

    page = request_path(app, "/admin/attractions")
    script = request_path(app, "/static/admin_attractions.js")

    assert page.status_code == 200
    assert "景点资料管理" in page.text
    assert "/admin/documents" in page.text
    assert "/static/admin_attractions.js" in page.text
    assert script.status_code == 200
    assert 'fetch("/api/admin/attractions"' in script.text
    assert 'fetch(`/api/admin/attractions/${attractionId}/images?' in script.text
    assert 'fetch("/api/tools/map/search?' in script.text
    assert "景点已归档" in script.text


def test_all_admin_pages_share_sidebar_navigation(tmp_path: Path):
    app = create_app(build_pipeline(tmp_path))

    for path in ("/admin/analytics", "/admin/attractions", "/admin/documents"):
        page = request_path(app, path)

        assert page.status_code == 200
        assert "LingJing AI" in page.text
        assert 'class="admin-sidebar"' in page.text
        assert 'href="/admin/analytics"' in page.text
        assert 'href="/admin/attractions"' in page.text
        assert 'href="/admin/documents"' in page.text
        assert f'class="admin-nav-item active" href="{path}"' in page.text
        assert "/static/admin.css" in page.text


def test_admin_analytics_page_and_local_chart_assets_are_served(tmp_path: Path):
    app = create_app(build_pipeline(tmp_path))

    page = request_path(app, "/admin/analytics")
    script = request_path(app, "/static/admin_analytics.js")
    charts = request_path(app, "/static/vendor/echarts.min.js")

    assert page.status_code == 200
    assert "游客数据分析" in page.text
    assert "/static/vendor/echarts.min.js" in page.text
    assert "/static/admin_analytics.js" in page.text
    assert script.status_code == 200
    assert 'fetch("/api/admin/analytics/dashboard")' in script.text
    assert "response.status === 503" in script.text
    assert "retryButton" in script.text
    assert "window.echarts" in script.text
    assert charts.status_code == 200


def test_admin_analytics_reveals_dashboard_before_initializing_charts(tmp_path: Path):
    app = create_app(build_pipeline(tmp_path))
    script = request_path(app, "/static/admin_analytics.js")

    success_sequence = "dashboard = data;\n    showDashboard();\n    renderDashboard(data);"
    normalized_script = script.text.replace("\r\n", "\n")
    assert success_sequence in normalized_script
