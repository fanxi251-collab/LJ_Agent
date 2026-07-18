from pathlib import Path

import httpx
import json

from lingjing_ai.agent.planner import AgentPlanner
from lingjing_ai.config.settings import AppSettings
from lingjing_ai.tools.amap_client import AmapApiError, AmapClient
from lingjing_ai.tools.amap_tools import AmapPlaceSearchTool, AmapRouteTool, AmapWeatherTool


class FakeJsonCache:
    def __init__(self) -> None:
        self.values: dict[str, dict] = {}

    def get_json(self, key: str):
        return self.values.get(key)

    def set_json(self, key: str, value: dict, ttl_seconds: int) -> None:
        self.values[key] = value


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "bad response",
                request=httpx.Request("GET", "https://restapi.amap.com"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> dict:
        return self.payload


def test_amap_client_calls_weather_api_with_map_api_key(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append({"url": url, "params": params, "timeout": timeout})
        return FakeResponse(
            {
                "status": "1",
                "infocode": "10000",
                "lives": [
                    {
                        "province": "江苏",
                        "city": "无锡市",
                        "weather": "晴",
                        "temperature": "28",
                        "winddirection": "东南",
                        "windpower": "≤3",
                        "humidity": "60",
                        "reporttime": "2026-07-07 10:00:00",
                    }
                ],
            }
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    client = AmapClient(api_key="map-key")

    data = client.weather("无锡")

    assert data["lives"][0]["city"] == "无锡市"
    assert calls[0]["url"].endswith("/v3/weather/weatherInfo")
    assert calls[0]["params"]["key"] == "map-key"
    assert calls[0]["params"]["city"] == "无锡"
    assert calls[0]["params"]["extensions"] == "base"


def test_amap_client_calls_walking_route_api(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append({"url": url, "params": params, "timeout": timeout})
        return FakeResponse(
            {
                "status": "1",
                "route": {
                    "paths": [
                        {
                            "distance": "1200",
                            "duration": "900",
                            "steps": [
                                {"instruction": "向东步行"},
                                {"instruction": "到达目的地"},
                            ],
                        }
                    ]
                },
            }
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    client = AmapClient(api_key="map-key")

    data = client.walking_route("120.1,31.5", "120.2,31.6")

    assert data["route"]["paths"][0]["distance"] == "1200"
    assert calls[0]["url"].endswith("/v3/direction/walking")
    assert calls[0]["params"]["origin"] == "120.1,31.5"
    assert calls[0]["params"]["destination"] == "120.2,31.6"


def test_amap_client_calls_driving_route_api(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append({"url": url, "params": params, "timeout": timeout})
        return FakeResponse(
            {
                "status": "1",
                "route": {
                    "paths": [
                        {
                            "distance": "42000",
                            "duration": "3600",
                            "steps": [
                                {"instruction": "沿太湖大道行驶", "polyline": "120.1,31.5;120.2,31.6"},
                            ],
                        }
                    ]
                },
            }
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    client = AmapClient(api_key="map-key")

    data = client.driving_route("120.1,31.5", "120.2,31.6")

    assert data["route"]["paths"][0]["distance"] == "42000"
    assert calls[0]["url"].endswith("/v3/direction/driving")
    assert calls[0]["params"]["origin"] == "120.1,31.5"
    assert calls[0]["params"]["destination"] == "120.2,31.6"


def test_amap_client_raises_clear_error_when_api_fails(monkeypatch):
    def fake_get(url, params, timeout):
        return FakeResponse({"status": "0", "info": "INVALID_USER_KEY", "infocode": "10001"})

    monkeypatch.setattr(httpx, "get", fake_get)
    client = AmapClient(api_key="bad-key")

    try:
        client.weather("无锡")
    except AmapApiError as exc:
        assert "INVALID_USER_KEY" in str(exc)
    else:
        raise AssertionError("AmapApiError was not raised")


def test_amap_weather_tool_returns_readable_source(monkeypatch, tmp_path: Path):
    def fake_weather(city: str, extensions: str = "base") -> dict:
        return {
            "lives": [
                {
                    "city": city,
                    "weather": "多云",
                    "temperature": "30",
                    "winddirection": "东",
                    "windpower": "3",
                    "humidity": "55",
                    "reporttime": "2026-07-07 11:00:00",
                }
            ]
        }

    settings = AppSettings.for_workspace(tmp_path)
    client = AmapClient(api_key="map-key")
    client.weather = fake_weather

    result = AmapWeatherTool(settings=settings, client=client).run("无锡今天天气怎么样？")

    assert result.status == "ok"
    assert "无锡当前天气多云" in result.sources[0].content
    assert result.sources[0].metadata["source_type"] == "amap_weather"


def test_amap_weather_tool_maps_scenic_spot_to_city(tmp_path: Path):
    requested_cities = []

    def fake_weather(city: str, extensions: str = "base") -> dict:
        requested_cities.append(city)
        return {
            "lives": [
                {
                    "city": city,
                    "weather": "阴",
                    "temperature": "27",
                    "winddirection": "东南",
                    "windpower": "3",
                    "humidity": "70",
                    "reporttime": "2026-07-08 09:00:00",
                }
            ]
        }

    settings = AppSettings.for_workspace(tmp_path)
    client = AmapClient(api_key="map-key")
    client.weather = fake_weather

    result = AmapWeatherTool(settings=settings, client=client).run("灵山胜境今日的天气如何？")

    assert requested_cities == ["无锡"]
    assert result.status == "ok"
    assert "无锡当前天气阴" in result.sources[0].content


def test_amap_weather_tool_reuses_redis_cache(tmp_path: Path):
    calls = []

    def fake_weather(city: str, extensions: str = "base") -> dict:
        calls.append(city)
        return {
            "lives": [
                {
                    "city": city,
                    "weather": "阴",
                    "temperature": "27",
                    "winddirection": "东南",
                    "windpower": "3",
                    "humidity": "70",
                    "reporttime": "2026-07-08 09:00:00",
                }
            ]
        }

    settings = AppSettings.for_workspace(tmp_path)
    client = AmapClient(api_key="map-key")
    client.weather = fake_weather
    cache = FakeJsonCache()
    tool = AmapWeatherTool(settings=settings, client=client, cache=cache)

    first = tool.run("灵山胜境今日的天气如何？")
    second = tool.run("灵山胜境今日的天气如何？")

    assert calls == ["无锡"]
    assert first.sources[0].content == second.sources[0].content
    assert second.sources[0].metadata["source_type"] == "amap_weather"


def test_amap_place_search_tool_returns_readable_source(tmp_path: Path):
    def fake_place_search(keywords: str, city: str = "", offset: int = 5) -> dict:
        return {
            "pois": [
                {
                    "name": "灵山胜境停车场",
                    "type": "交通设施服务",
                    "address": "马山镇",
                    "location": "120.100,31.500",
                }
            ]
        }

    settings = AppSettings.for_workspace(tmp_path)
    client = AmapClient(api_key="map-key")
    client.place_search = fake_place_search

    result = AmapPlaceSearchTool(settings=settings, client=client).run("查一下灵山胜境停车场")

    assert result.status == "ok"
    assert "灵山胜境停车场" in result.sources[0].content
    assert result.sources[0].metadata["source_type"] == "amap_place"


def test_amap_place_search_tool_reuses_redis_cache(tmp_path: Path):
    calls = []

    def fake_place_search(keywords: str, city: str = "", offset: int = 5) -> dict:
        calls.append((keywords, city))
        return {
            "pois": [
                {
                    "name": "灵山胜境停车场",
                    "type": "交通设施服务",
                    "address": "马山镇",
                    "location": "120.100,31.500",
                }
            ]
        }

    settings = AppSettings.for_workspace(tmp_path)
    client = AmapClient(api_key="map-key")
    client.place_search = fake_place_search
    tool = AmapPlaceSearchTool(settings=settings, client=client, cache=FakeJsonCache())

    first = tool.run("查一下灵山胜境停车场")
    second = tool.run("查一下灵山胜境停车场")

    assert calls == [("灵山胜境停车场", "无锡")]
    assert first.sources[0].content == second.sources[0].content


def test_amap_route_tool_geocodes_and_returns_route_source(tmp_path: Path):
    def fake_geocode(address: str, city: str = "") -> dict:
        locations = {
            "无锡站": "120.305,31.590",
            "灵山胜境": "120.100,31.500",
        }
        return {"geocodes": [{"formatted_address": address, "location": locations[address]}]}

    def fake_walking_route(origin: str, destination: str) -> dict:
        return {
            "route": {
                "paths": [
                    {
                        "distance": "1200",
                        "duration": "900",
                        "steps": [
                            {"instruction": "从无锡站出发"},
                            {"instruction": "步行至灵山胜境"},
                        ],
                    }
                ]
            }
        }

    settings = AppSettings.for_workspace(tmp_path)
    client = AmapClient(api_key="map-key")
    client.geocode = fake_geocode
    client.walking_route = fake_walking_route

    result = AmapRouteTool(settings=settings, client=client).run("从无锡站到灵山胜境步行怎么走？")

    assert result.status == "ok"
    assert "从无锡站到灵山胜境" in result.sources[0].content
    assert "约1.2公里" in result.sources[0].content
    assert "约15分钟" in result.sources[0].content
    assert result.sources[0].metadata["source_type"] == "amap_route"


def test_amap_route_tool_defaults_to_driving_and_returns_map_metadata(tmp_path: Path):
    requested_modes = []

    def fake_geocode(address: str, city: str = "") -> dict:
        locations = {
            "无锡站": "120.305,31.590",
            "灵山胜境": "120.100,31.500",
        }
        return {"geocodes": [{"formatted_address": address, "location": locations[address]}]}

    def fake_driving_route(origin: str, destination: str) -> dict:
        requested_modes.append("driving")
        return {
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
            }
        }

    settings = AppSettings.for_workspace(tmp_path)
    client = AmapClient(api_key="map-key")
    client.geocode = fake_geocode
    client.driving_route = fake_driving_route

    result = AmapRouteTool(settings=settings, client=client).run("从无锡站到灵山胜境怎么走？")
    metadata = result.sources[0].metadata

    assert requested_modes == ["driving"]
    assert result.status == "ok"
    assert "驾车距离约42.0公里" in result.sources[0].content
    assert metadata["source_type"] == "amap_route"
    summary = metadata["route_summary"]
    assert summary["schema_version"] == 2
    assert summary["mode"] == "driving"
    assert summary["distance_text"] == "约42.0公里"
    assert summary["duration_text"] == "约60分钟"
    assert summary["polyline"] == ["120.305,31.590", "120.200,31.550", "120.100,31.500"]
    assert summary["steps"][0]["instruction"] == "从无锡站出发"


def test_amap_route_tool_uses_published_internal_locations_and_defaults_to_walking(tmp_path: Path):
    requested = []
    locations = {
        "五明桥": "120.102248,31.421749",
        "五智门": "120.101292,31.423055",
    }

    def forbidden_geocode(address: str, city: str = "") -> dict:
        raise AssertionError(f"内部景点不应调用地理编码：{address}")

    def fake_walking_route(origin: str, destination: str) -> dict:
        requested.append(("walking", origin, destination))
        return {
            "route": {
                "paths": [{
                    "distance": "210",
                    "duration": "180",
                    "steps": [{
                        "instruction": "从五明桥沿景区步道向北步行至五智门",
                        "polyline": f"{origin};{destination}",
                    }],
                }]
            }
        }

    settings = AppSettings.for_workspace(tmp_path)
    client = AmapClient(api_key="map-key")
    client.geocode = forbidden_geocode
    client.walking_route = fake_walking_route
    tool = AmapRouteTool(settings=settings, client=client, location_resolver=locations.get)

    result = tool.run("从五明桥到五智门怎么走")

    assert requested == [("walking", locations["五明桥"], locations["五智门"])]
    assert result.data["route_summary"]["mode"] == "walking"
    assert result.data["route_summary"]["origin"] == "五明桥"
    assert result.data["route_summary"]["destination"] == "五智门"


def test_explicit_driving_overrides_internal_walking_default(tmp_path: Path):
    requested = []
    locations = {"五明桥": "120.102248,31.421749", "五智门": "120.101292,31.423055"}

    def fake_driving_route(origin: str, destination: str) -> dict:
        requested.append((origin, destination))
        return {
            "route": {
                "paths": [{
                    "distance": "300",
                    "duration": "120",
                    "steps": [{"instruction": "驾车到达", "polyline": f"{origin};{destination}"}],
                }]
            }
        }

    settings = AppSettings.for_workspace(tmp_path)
    client = AmapClient(api_key="map-key")
    client.driving_route = fake_driving_route
    tool = AmapRouteTool(settings=settings, client=client, location_resolver=locations.get)

    result = tool.run("从五明桥到五智门驾车怎么走")

    assert requested == [(locations["五明桥"], locations["五智门"])]
    assert result.data["route_summary"]["mode"] == "driving"


def test_internal_location_is_not_overwritten_when_other_endpoint_needs_geocoding(tmp_path: Path):
    geocoded = []
    requested = []

    def fake_geocode(address: str, city: str = "") -> dict:
        geocoded.append(address)
        return {"geocodes": [{"location": "120.305,31.590"}]}

    def fake_driving_route(origin: str, destination: str) -> dict:
        requested.append((origin, destination))
        return {
            "route": {
                "paths": [{
                    "distance": "42000",
                    "duration": "3600",
                    "steps": [{"instruction": "驾车到达", "polyline": f"{origin};{destination}"}],
                }]
            }
        }

    settings = AppSettings.for_workspace(tmp_path)
    client = AmapClient(api_key="map-key")
    client.geocode = fake_geocode
    client.driving_route = fake_driving_route
    resolver = lambda name: "120.101292,31.423055" if name == "五智门" else None
    tool = AmapRouteTool(settings=settings, client=client, location_resolver=resolver)

    result = tool.run("从无锡站到五智门怎么走")

    assert geocoded == ["无锡站"]
    assert requested == [("120.305,31.590", "120.101292,31.423055")]
    assert result.data["route_summary"]["mode"] == "driving"


def test_amap_route_tool_reuses_redis_cache_and_separates_modes(tmp_path: Path):
    calls = []

    def fake_geocode(address: str, city: str = "") -> dict:
        locations = {
            "无锡站": "120.305,31.590",
            "灵山胜境": "120.100,31.500",
        }
        return {"geocodes": [{"formatted_address": address, "location": locations[address]}]}

    def fake_driving_route(origin: str, destination: str) -> dict:
        calls.append("driving")
        return {
            "route": {
                "paths": [
                    {
                        "distance": "42000",
                        "duration": "3600",
                        "steps": [{"instruction": "驾车到达", "polyline": "120.305,31.590;120.100,31.500"}],
                    }
                ]
            }
        }

    def fake_walking_route(origin: str, destination: str) -> dict:
        calls.append("walking")
        return {
            "route": {
                "paths": [
                    {
                        "distance": "1200",
                        "duration": "900",
                        "steps": [{"instruction": "步行到达", "polyline": "120.305,31.590;120.100,31.500"}],
                    }
                ]
            }
        }

    settings = AppSettings.for_workspace(tmp_path)
    client = AmapClient(api_key="map-key")
    client.geocode = fake_geocode
    client.driving_route = fake_driving_route
    client.walking_route = fake_walking_route
    tool = AmapRouteTool(settings=settings, client=client, cache=FakeJsonCache())

    driving_first = tool.run("从无锡站到灵山胜境怎么走？")
    driving_second = tool.run("从无锡站到灵山胜境怎么走？")
    walking = tool.run("从无锡站到灵山胜境步行怎么走？")

    assert calls == ["driving", "walking"]
    assert driving_first.sources[0].content == driving_second.sources[0].content
    assert driving_second.sources[0].metadata["route_summary"]["mode"] == "driving"
    assert walking.sources[0].metadata["route_summary"]["mode"] == "walking"
    assert all(key.startswith("amap:route:v2:") for key in tool.cache.values)


def test_amap_route_tool_returns_compact_v2_payload_without_raw_route(tmp_path: Path):
    def fake_geocode(address: str, city: str = "") -> dict:
        locations = {"无锡站": "120.305,31.590", "灵山胜境": "120.100,31.500"}
        return {"geocodes": [{"location": locations[address]}]}

    def fake_driving_route(origin: str, destination: str) -> dict:
        return {
            "route": {
                "paths": [
                    {
                        "distance": "42000",
                        "duration": "3600",
                        "steps": [
                            {
                                "instruction": f"第{index + 1}步进入道路",
                                "distance": "100",
                                "duration": "10",
                                "polyline": f"120.{index:03d},31.500;120.{index + 1:03d},31.501",
                            }
                            for index in range(20)
                        ],
                    }
                ]
            }
        }

    settings = AppSettings.for_workspace(tmp_path)
    client = AmapClient(api_key="map-key")
    client.geocode = fake_geocode
    client.driving_route = fake_driving_route

    result = AmapRouteTool(settings=settings, client=client).run("从无锡站到灵山胜境怎么走？")
    summary = result.data["route_summary"]
    metadata = result.sources[0].metadata

    assert summary["schema_version"] == 2
    assert 8 <= len(summary["steps"]) <= 12
    assert result.data["route"] == {
        "distance": "42000",
        "duration": "3600",
        "steps": summary["steps"],
    }
    assert set(metadata) == {"source_type", "route_summary"}
    assert len(json.dumps(metadata, ensure_ascii=False).encode("utf-8")) < 100_000


def test_agent_planner_adds_amap_tools_for_weather_and_map_questions(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MAP_API", "map-key")
    settings = AppSettings.for_workspace(tmp_path)
    planner = AgentPlanner(settings)

    weather_plan = planner.plan("无锡今天天气怎么样？")
    map_plan = planner.plan("帮我查一下灵山胜境停车场在哪里")
    route_plan = planner.plan("从无锡站到灵山胜境怎么走？")

    assert "amap_weather" in [step.tool_name for step in weather_plan.steps]
    assert "amap_place_search" in [step.tool_name for step in map_plan.steps]
    assert "amap_route" in [step.tool_name for step in route_plan.steps]
