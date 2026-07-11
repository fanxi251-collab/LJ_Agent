from pathlib import Path
import asyncio

import httpx

from lingjing_ai.api.app import create_app
from lingjing_ai.config.settings import AppSettings
from lingjing_ai.rag.embeddings import HashingEmbeddingProvider
from lingjing_ai.rag.generator import ExtractiveAnswerGenerator
from lingjing_ai.rag.pipeline import RagPipeline
from lingjing_ai.storage.vector_store import JsonVectorStore


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def build_pipeline(tmp_path: Path) -> RagPipeline:
    settings = AppSettings.for_workspace(tmp_path)
    return RagPipeline(
        settings=settings,
        embedding_provider=HashingEmbeddingProvider(dimensions=64),
        vector_store=JsonVectorStore(tmp_path / "vectors.json"),
        answer_generator=ExtractiveAnswerGenerator(),
    )


def test_map_config_api_returns_frontend_map_settings(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MAP_JS_API", "js-map-key")
    app = create_app(build_pipeline(tmp_path))

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/api/tools/map/config")

    response = asyncio.run(request())
    body = response.json()

    assert response.status_code == 200
    assert body["enabled"] is True
    assert body["js_api_key"] == "js-map-key"
    assert body["default_route_mode"] == "driving"


def test_weather_api_returns_amap_weather(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MAP_API", "map-key")

    def fake_get(url, params, timeout):
        return FakeResponse(
            {
                "status": "1",
                "infocode": "10000",
                "lives": [
                    {
                        "city": params["city"],
                        "weather": "晴",
                        "temperature": "29",
                        "winddirection": "东",
                        "windpower": "3",
                        "humidity": "58",
                        "reporttime": "2026-07-07 12:00:00",
                    }
                ],
            }
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    app = create_app(build_pipeline(tmp_path))

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/api/tools/weather", params={"city": "无锡"})

    response = asyncio.run(request())
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "ok"
    assert "无锡当前天气晴" in body["content"]


def test_map_search_api_returns_amap_place_results(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MAP_API", "map-key")

    def fake_get(url, params, timeout):
        return FakeResponse(
            {
                "status": "1",
                "infocode": "10000",
                "pois": [
                    {
                        "name": params["keywords"],
                        "type": "风景名胜",
                        "address": "马山镇",
                        "location": "120.100,31.500",
                    }
                ],
            }
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    app = create_app(build_pipeline(tmp_path))

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/api/tools/map/search", params={"keywords": "灵山胜境", "city": "无锡"})

    response = asyncio.run(request())
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "ok"
    assert "灵山胜境" in body["content"]


def test_map_route_api_returns_amap_route_result(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MAP_API", "map-key")

    def fake_get(url, params, timeout):
        if url.endswith("/v3/geocode/geo"):
            locations = {
                "无锡站": "120.305,31.590",
                "灵山胜境": "120.100,31.500",
            }
            return FakeResponse(
                {
                    "status": "1",
                    "infocode": "10000",
                    "geocodes": [{"formatted_address": params["address"], "location": locations[params["address"]]}],
                }
            )
        return FakeResponse(
            {
                "status": "1",
                "infocode": "10000",
                "route": {
                    "paths": [
                        {
                            "distance": "42000",
                            "duration": "3600",
                            "steps": [
                                {"instruction": "从无锡站出发", "polyline": "120.305,31.590;120.200,31.550"},
                                {"instruction": "到达灵山胜境", "polyline": "120.200,31.550;120.100,31.500"},
                            ],
                        }
                    ]
                },
            }
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    app = create_app(build_pipeline(tmp_path))

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(
                "/api/tools/map/route",
                params={"origin": "无锡站", "destination": "灵山胜境", "mode": "driving"},
            )

    response = asyncio.run(request())
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "ok"
    assert "从无锡站到灵山胜境" in body["content"]
    assert "约42.0公里" in body["content"]
    assert body["data"]["route_summary"]["mode"] == "driving"
    assert body["data"]["route_summary"]["polyline"] == ["120.305,31.590", "120.200,31.550", "120.100,31.500"]


def test_map_route_api_uses_structured_locations_without_geocoding(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MAP_API", "map-key")
    requested_paths = []

    def fake_get(url, params, timeout):
        requested_paths.append(url)
        assert params["origin"] == "120.102248,31.421749"
        assert params["destination"] == "120.096477,31.430194"
        return FakeResponse(
            {
                "status": "1",
                "route": {
                    "paths": [
                        {
                            "distance": "1200",
                            "duration": "900",
                            "steps": [{"instruction": "沿景区步道前行", "polyline": "120.102248,31.421749;120.096477,31.430194"}],
                        }
                    ]
                },
            }
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    app = create_app(build_pipeline(tmp_path))

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(
                "/api/tools/map/route",
                params={
                    "origin": "五明桥",
                    "destination": "灵山大佛",
                    "origin_location": "120.102248,31.421749",
                    "destination_location": "120.096477,31.430194",
                    "mode": "walking",
                },
            )

    response = asyncio.run(request())

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert all("/v3/geocode/geo" not in path for path in requested_paths)
