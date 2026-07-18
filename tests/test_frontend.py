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
    chat_composable = Path("frontend/src/composables/useRealtimeChat.js").read_text(encoding="utf-8")
    transcript_confirmation_source = Path(
        "frontend/src/features/digital-human/components/TranscriptConfirmation.vue"
    ).read_text(encoding="utf-8")
    session_composable = Path("frontend/src/composables/useSessions.js").read_text(encoding="utf-8")
    styles = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "visitor-layout" in app_source
    assert "chat-main" in chat_source
    assert "session-sidebar" in session_source
    assert "history-side" in app_source
    assert "给 LingJing AI 发送消息" in chat_source
    assert "常规模式" in chat_source
    assert "数字人模式" in chat_source
    assert "text.submit" in chat_composable
    assert "audio.start" in chat_composable
    assert "response.cancel" in chat_composable
    assert "user.transcript.confirmation_required" in chat_composable
    assert "transcript.confirm" in chat_composable
    assert "转写结果需要确认" in transcript_confirmation_source
    assert "buildRealtimeUrl" in chat_composable
    assert "retryQuestion" in chat_composable
    assert '@retry="emit(\'ask\', $event)"' in chat_source
    assert 'mode.value = nextMode' not in chat_source
    assert 'event.type === "assistant.text.done"' in chat_composable
    assert 'event.turn_id !== activeTurnId.value' in chat_composable
    assert '"/api/visitor/sessions?visitor_id="' in session_composable
    assert "`/api/visitor/sessions/${currentSessionId.value}?" in session_composable
    assert ".history-side" in styles
    assert ".composer-card" in styles


def test_digital_human_frontend_uses_local_pcm_and_replaceable_stage():
    feature_root = Path("frontend/src/features/digital-human")
    stage_source = (feature_root / "components/DigitalHumanStage.vue").read_text(
        encoding="utf-8"
    )
    audio_source = (feature_root / "composables/usePcmAudio.js").read_text(
        encoding="utf-8"
    )
    chat_source = Path("frontend/src/composables/useRealtimeChat.js").read_text(encoding="utf-8")
    guide_source = Path("frontend/src/views/GuideView.vue").read_text(encoding="utf-8")
    voice_controls_source = (feature_root / "components/DigitalHumanVoiceControls.vue").read_text(
        encoding="utf-8"
    )
    worklet_source = Path(
        "frontend/public/digital-human/pcm-capture-worklet.js"
    ).read_text(encoding="utf-8")

    assert "audioLevel" in stage_source
    assert "speaking" in stage_source
    assert "AudioWorkletNode" in audio_source
    assert "sampleRate: 24000" in audio_source
    assert "preparePlayback" in audio_source
    assert "await audio.preparePlayback()" not in chat_source
    assert "stopRecordingRequested" in chat_source
    assert "capturedAudioChunks" in chat_source
    assert "['starting', 'recording'].includes(microphoneState)" in voice_controls_source
    recording_block = chat_source.split("async function startRecording()", 1)[1].split(
        "async function stopRecording()", 1
    )[0]
    assert recording_block.index("audio.preparePlayback()") < recording_block.index(
        "ensureConnected()"
    )
    assert 'event.type === "session.ready"' in chat_source
    assert "buildModeSetEvent(mode.value)" in chat_source
    assert "assistantTranscript" in chat_source
    assert "avatarCaption" in guide_source
    assert "registerProcessor" in worklet_source
    assert "16000" in worklet_source


def test_digital_human_frontend_isolated_behind_feature_entrypoint():
    feature_root = Path("frontend/src/features/digital-human")
    expected_files = (
        feature_root / "index.js",
        feature_root / "components/DigitalHumanStage.vue",
        feature_root / "components/DigitalHumanVoiceControls.vue",
        feature_root / "components/TranscriptConfirmation.vue",
        feature_root / "renderers/Live2DAvatarRenderer.vue",
        feature_root / "composables/usePcmAudio.js",
        feature_root / "lib/audioCaptureQuality.js",
        feature_root / "lib/live2dExpression.js",
        feature_root / "lib/live2dMotion.js",
        feature_root / "lib/pcmAudio.js",
    )

    assert all(path.is_file() for path in expected_files)
    feature_entrypoint = (feature_root / "index.js").read_text(encoding="utf-8")
    chat_main = Path("frontend/src/components/ChatMain.vue").read_text(encoding="utf-8")
    realtime_chat = Path("frontend/src/composables/useRealtimeChat.js").read_text(
        encoding="utf-8"
    )

    assert 'from "../features/digital-human"' in chat_main
    assert 'from "../features/digital-human"' in realtime_chat
    assert "<svg" not in chat_main
    assert "../lib/audioCaptureQuality.js" not in realtime_chat
    assert 'from "./usePcmAudio"' not in realtime_chat
    for exported_name in (
        "DigitalHumanStage",
        "DigitalHumanVoiceControls",
        "TranscriptConfirmation",
        "usePcmAudio",
        "createTailProtection",
        "createCaptureQualityTracker",
        "TAIL_PROTECTION_MS",
        "float32Metrics",
        "float32ToInt16",
        "pcmRms",
    ):
        assert exported_name in feature_entrypoint


def test_digital_human_live2d_renderer_replaces_svg_with_stable_contract():
    feature_root = Path("frontend/src/features/digital-human")
    renderer_path = feature_root / "renderers/Live2DAvatarRenderer.vue"
    svg_path = feature_root / "renderers/SvgAvatarRenderer.vue"

    assert renderer_path.is_file()
    assert not svg_path.exists()
    renderer_source = renderer_path.read_text(encoding="utf-8")
    assert "state:" in renderer_source
    assert "audioLevel:" in renderer_source
    assert "expression:" in renderer_source
    assert "transcript:" not in renderer_source
    assert "beforeModelUpdate" in renderer_source
    assert "ResizeObserver" in renderer_source
    assert 'import * as PIXI from "pixi.js"' not in renderer_source
    motion_source = (feature_root / "lib/live2dMotion.js").read_text(encoding="utf-8")
    assert "lipSyncIds" in motion_source
    assert "applyLipSyncValue" in renderer_source
    loader_source = (feature_root / "lib/live2dLoader.js").read_text(encoding="utf-8")
    assert 'import("pixi.js")' in loader_source

    stage_source = (feature_root / "components/DigitalHumanStage.vue").read_text(
        encoding="utf-8"
    )
    assert "Live2DAvatarRenderer" in stage_source
    assert "SvgAvatarRenderer" not in stage_source
    assert "emotionText" in stage_source
    assert "数字人形象加载失败" in stage_source


def test_live2d_dependencies_and_local_mao_pro_assets_are_complete():
    package = Path("frontend/package.json").read_text(encoding="utf-8")
    live2d_root = Path("frontend/public/digital-human/live2d")
    model_root = live2d_root / "mao_pro"
    model_json = model_root / "mao_pro.model3.json"

    assert '"pixi.js": "6.5.10"' in package
    assert '"pixi-live2d-display": "0.4.0"' in package
    assert (live2d_root / "live2dcubismcore.min.js").is_file()
    assert (live2d_root / "NOTICE.md").is_file()
    assert (live2d_root / "LICENSE-Live2D-Cubism-SDK.txt").is_file()
    assert (model_root / "README.md").is_file()
    assert model_json.is_file()

    model_source = model_json.read_text(encoding="utf-8")
    assert "http://" not in model_source
    assert "https://" not in model_source
    for expected_asset in (
        "mao_pro.moc3",
        "mao_pro.4096/texture_00.png",
        "mao_pro.physics3.json",
        "mao_pro.pose3.json",
        "expressions/exp_01.exp3.json",
        "expressions/exp_02.exp3.json",
        "expressions/exp_04.exp3.json",
        "expressions/exp_05.exp3.json",
    ):
        assert (model_root / expected_asset).is_file(), expected_asset


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


def test_route_views_use_v2_summary_and_show_all_key_steps():
    guide_source = Path("frontend/src/views/GuideView.vue").read_text(encoding="utf-8")
    route_panel = Path("frontend/src/components/RoutePanel.vue").read_text(encoding="utf-8")
    map_source = Path("frontend/src/views/MapView.vue").read_text(encoding="utf-8")

    assert "watch(chatApi.hasRouteSource" in guide_source
    assert 'activeToolPanel.value = "route"' in guide_source
    assert "resolveRouteSummary" in route_panel
    assert "高德原始步骤共" in route_panel
    assert "total_step_count" in route_panel
    assert ".slice(0, 8)" not in route_panel
    assert ".slice(0, 8)" not in map_source


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


def test_fastapi_serves_pcm_capture_worklet(tmp_path: Path):
    app = create_app(build_pipeline(tmp_path))

    canonical_response = request_path(app, "/digital-human/pcm-capture-worklet.js")
    compatibility_response = request_path(app, "/pcm-capture-worklet.js")

    assert canonical_response.status_code == 200
    assert compatibility_response.status_code == 200
    assert canonical_response.text == compatibility_response.text
    assert "registerProcessor" in canonical_response.text


def test_fastapi_serves_local_live2d_assets(tmp_path: Path):
    app = create_app(build_pipeline(tmp_path))

    model = request_path(app, "/digital-human/live2d/mao_pro/mao_pro.model3.json")
    moc = request_path(app, "/digital-human/live2d/mao_pro/mao_pro.moc3")
    texture = request_path(
        app, "/digital-human/live2d/mao_pro/mao_pro.4096/texture_00.png"
    )
    core = request_path(app, "/digital-human/live2d/live2dcubismcore.min.js")

    assert model.status_code == 200
    assert moc.status_code == 200
    assert texture.status_code == 200
    assert core.status_code == 200
    assert model.json()["Version"] == 3


def test_legacy_admin_assets_are_still_served(tmp_path: Path):
    app = create_app(build_pipeline(tmp_path))

    script_response = request_path(app, "/static/admin_documents.js")
    style_response = request_path(app, "/static/app.css")

    assert script_response.status_code == 200
    assert 'fetch("/api/admin/documents"' in script_response.text
    assert style_response.status_code == 200
    assert ".source-meta" in style_response.text
