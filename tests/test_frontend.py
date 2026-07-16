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
    app_source = Path("frontend/src/views/GuideView.vue").read_text(encoding="utf-8")
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


def test_visitor_router_exposes_guide_explore_and_map_views():
    package = Path("frontend/package.json").read_text(encoding="utf-8")
    main_source = Path("frontend/src/main.js").read_text(encoding="utf-8")
    app_source = Path("frontend/src/App.vue").read_text(encoding="utf-8")

    assert '"vue-router"' in package
    assert "createRouter" in main_source
    assert 'path: "/visitor/guide"' in main_source
    assert 'path: "/visitor/explore"' in main_source
    assert 'path: "/visitor/map"' in main_source
    assert "AI 智能导游" in app_source
    assert "景点探索" in app_source
    assert "互动地图" in app_source
    assert "RouterView" in app_source


def test_visitor_root_uses_shared_left_sidebar_navigation():
    app_source = Path("frontend/src/App.vue").read_text(encoding="utf-8")
    page_styles = Path("frontend/src/visitor-pages.css").read_text(encoding="utf-8")

    assert "visitor-sidebar" in app_source
    assert "visitor-content-shell" in app_source
    assert "visitor-global-header" not in app_source
    assert app_source.count("visitor-sidebar-icon") == 3
    assert "grid-template-columns: 232px minmax(0, 1fr)" in page_styles
    assert "overflow-y: auto" in page_styles
    assert "@media (max-width: 760px)" in page_styles


def test_explore_and_map_views_contain_expected_interactions():
    explore_source = Path("frontend/src/views/ExploreView.vue").read_text(encoding="utf-8")
    map_source = Path("frontend/src/views/MapView.vue").read_text(encoding="utf-8")
    drawer_source = Path("frontend/src/components/AttractionDetailDrawer.vue").read_text(encoding="utf-8")
    map_composable = Path("frontend/src/composables/useInteractiveMap.js").read_text(encoding="utf-8")

    assert 'fetch("/api/visitor/attractions")' in explore_source
    assert "推荐景点" in explore_source
    assert "在地图中查看" in drawer_source
    assert "询问 AI 导游" in drawer_source
    assert 'fetch("/api/visitor/attractions")' in map_source
    assert 'fetch(`/api/tools/map/route?' in map_source
    assert "起点和终点不能相同" in map_source
    assert "AMap.Marker" in map_composable
    assert "window._AMapSecurityConfig" in map_composable
    assert "security_js_code" in map_composable
    assert "destroy" in map_composable


def test_all_map_loaders_apply_amap_security_code_before_loading_script():
    loader_paths = (
        "frontend/src/composables/useInteractiveMap.js",
        "frontend/src/composables/useRouteMap.js",
        "frontend/static/app.js",
    )

    for loader_path in loader_paths:
        source = Path(loader_path).read_text(encoding="utf-8")
        security_index = source.index("window._AMapSecurityConfig")
        script_index = source.index("document.createElement(\"script\")", security_index)
        assert security_index < script_index
        assert "security_js_code" in source


def test_fastapi_serves_visitor_subroutes(tmp_path: Path):
    app = create_app(build_pipeline(tmp_path))

    explore = request_path(app, "/visitor/explore")
    map_page = request_path(app, "/visitor/map")

    assert explore.status_code == 200
    assert map_page.status_code == 200


def test_legacy_admin_assets_are_still_served(tmp_path: Path):
    app = create_app(build_pipeline(tmp_path))

    script_response = request_path(app, "/static/admin_documents.js")
    style_response = request_path(app, "/static/app.css")

    assert script_response.status_code == 200
    assert 'fetch("/api/admin/documents"' in script_response.text
    assert style_response.status_code == 200
    assert ".source-meta" in style_response.text
