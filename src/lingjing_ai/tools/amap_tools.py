import re

from collections.abc import Callable

from lingjing_ai.agent.models import ToolResult
from lingjing_ai.config.settings import AppSettings
from lingjing_ai.models.rag import SourceChunk
from lingjing_ai.services.redis_cache import RedisJsonCache
from lingjing_ai.tools.amap_client import AmapApiError, AmapClient
from lingjing_ai.tools.route_summary import build_route_summary
from lingjing_ai.tools.route_scope import RouteScopeDecision


SCENIC_CITY_MAP = {
    "灵山胜境": "无锡",
    "灵山大佛": "无锡",
    "拈花湾": "无锡",
    "鼋头渚": "无锡",
}


class AmapWeatherTool:
    name = "amap_weather"

    def __init__(
        self,
        settings: AppSettings,
        client: AmapClient | None = None,
        cache: RedisJsonCache | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or _build_client(settings)
        self.cache = cache or _build_cache(settings)

    def run(self, question: str) -> ToolResult:
        if self.client is None:
            return ToolResult(status="disabled", message="高德地图 API 未配置，请设置 MAP_API。")
        city = _extract_city(question)
        cache_key = f"amap:weather:{city}"
        cached = _get_cached_tool_result(self.cache, cache_key)
        if cached is not None:
            return cached
        try:
            data = self.client.weather(city)
        except AmapApiError as exc:
            return ToolResult(status="error", message=str(exc), data={"city": city})
        lives = data.get("lives") or []
        if not lives:
            return ToolResult(status="empty", message="未查到天气信息", data={"city": city})

        live = lives[0]
        content = (
            f"{live.get('city', city)}当前天气{live.get('weather', '未知')}，"
            f"气温{live.get('temperature', '未知')}℃，"
            f"{live.get('winddirection', '未知')}风{live.get('windpower', '未知')}级，"
            f"湿度{live.get('humidity', '未知')}%，"
            f"发布时间{live.get('reporttime', '未知')}。"
        )
        result = ToolResult(
            status="ok",
            message="已查询高德天气",
            data={"city": city, "weather": live},
            sources=[
                SourceChunk(
                    chunk_id=f"amap_weather_{city}",
                    document_id="amap_weather",
                    document_name="高德天气",
                    content=content,
                    score=1.0,
                    metadata={
                        "source_type": "amap_weather",
                        "city": live.get("city", city),
                        "weather": live.get("weather", ""),
                        "temperature": live.get("temperature", ""),
                        "winddirection": live.get("winddirection", ""),
                        "windpower": live.get("windpower", ""),
                        "humidity": live.get("humidity", ""),
                        "reporttime": live.get("reporttime", ""),
                    },
                )
            ],
        )
        _set_cached_tool_result(self.cache, cache_key, result, self.settings.redis_weather_cache_ttl_seconds)
        return result


class AmapPlaceSearchTool:
    name = "amap_place_search"

    def __init__(
        self,
        settings: AppSettings,
        client: AmapClient | None = None,
        cache: RedisJsonCache | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or _build_client(settings)
        self.cache = cache or _build_cache(settings)

    def run(self, question: str) -> ToolResult:
        if self.client is None:
            return ToolResult(status="disabled", message="高德地图 API 未配置，请设置 MAP_API。")
        keywords = _extract_place_keywords(question)
        city = _extract_city(question, default="")
        cache_key = f"amap:place:{city}:{keywords}"
        cached = _get_cached_tool_result(self.cache, cache_key)
        if cached is not None:
            return cached
        try:
            data = self.client.place_search(keywords, city=city)
        except AmapApiError as exc:
            return ToolResult(status="error", message=str(exc), data={"keywords": keywords, "city": city})

        pois = data.get("pois") or []
        if not pois:
            return ToolResult(status="empty", message="未查到地点信息", data={"keywords": keywords, "city": city})

        lines = []
        for index, poi in enumerate(pois[:5], start=1):
            lines.append(
                f"{index}. {poi.get('name', '未知地点')}，类型：{poi.get('type', '未知')}，"
                f"地址：{poi.get('address', '未知')}，坐标：{poi.get('location', '未知')}"
            )
        content = "高德地图地点查询结果：" + "；".join(lines)
        result = ToolResult(
            status="ok",
            message="已查询高德地点",
            data={"keywords": keywords, "city": city, "pois": pois[:5]},
            sources=[
                SourceChunk(
                    chunk_id=f"amap_place_{keywords}",
                    document_id="amap_place",
                    document_name="高德地图地点查询",
                    content=content,
                    score=1.0,
                    metadata={"source_type": "amap_place", "keywords": keywords, "city": city},
                )
            ],
        )
        _set_cached_tool_result(self.cache, cache_key, result, self.settings.redis_place_cache_ttl_seconds)
        return result


class AmapRouteTool:
    name = "amap_route"

    def __init__(
        self,
        settings: AppSettings,
        client: AmapClient | None = None,
        cache: RedisJsonCache | None = None,
        location_resolver: Callable[[str], str | None] | None = None,
        scope_validator: Callable[[str, str], RouteScopeDecision] | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or _build_client(settings)
        self.cache = cache or _build_cache(settings)
        self.location_resolver = location_resolver
        self.scope_validator = scope_validator

    def run(
        self,
        question: str,
        mode: str | None = None,
        origin_location: str = "",
        destination_location: str = "",
    ) -> ToolResult:
        if self.client is None:
            return ToolResult(status="disabled", message="高德地图 API 未配置，请设置 MAP_API。")

        route_points = _extract_route_points(question)
        if route_points is None:
            return ToolResult(
                status="empty",
                message="请提供明确的起点和终点，例如：从无锡站到灵山胜境怎么走？",
            )
        origin, destination = route_points

        resolved_origin = (
            self.location_resolver(origin)
            if self.location_resolver and not origin_location
            else None
        )
        resolved_destination = (
            self.location_resolver(destination)
            if self.location_resolver and not destination_location
            else None
        )
        both_internal = bool(resolved_origin and resolved_destination)
        origin_location = origin_location or resolved_origin or ""
        destination_location = destination_location or resolved_destination or ""
        explicit_mode = mode or _extract_route_mode(question, "")
        route_mode = _normalize_route_mode(
            explicit_mode
            or ("walking" if both_internal else self.settings.amap_route_default_mode)
        )
        try:
            if not origin_location:
                origin_geo = self.client.geocode(origin)
                origin_location = _first_geocode_location(origin_geo)
            if not destination_location:
                destination_geo = self.client.geocode(destination)
                destination_location = _first_geocode_location(destination_geo)
            if not origin_location or not destination_location:
                return ToolResult(status="empty", message="未查到起点或终点坐标。")
            if self.scope_validator is not None:
                scope = self.scope_validator(origin_location, destination_location)
                if not scope.allowed:
                    return ToolResult(
                        status="error",
                        message=scope.reason,
                        data={
                            "origin": origin,
                            "destination": destination,
                            "mode": route_mode,
                            "origin_distance_km": scope.origin_distance_km,
                            "destination_distance_km": scope.destination_distance_km,
                        },
                    )
            cache_key = (
                f"amap:route:v3:{route_mode}:{origin}:{destination}:"
                f"{origin_location}:{destination_location}"
            )
            cached = _get_cached_tool_result(self.cache, cache_key)
            if cached is not None:
                return cached
            if route_mode == "walking":
                data = self.client.walking_route(origin_location, destination_location)
            else:
                data = self.client.driving_route(origin_location, destination_location)
        except AmapApiError as exc:
            return ToolResult(
                status="error",
                message=str(exc),
                data={"origin": origin, "destination": destination},
            )

        paths = ((data.get("route") or {}).get("paths")) or []
        if not paths:
            return ToolResult(status="empty", message="未查到路线信息。", data=data)

        path = paths[0]
        route_summary = build_route_summary(
            path,
            origin=origin,
            destination=destination,
            origin_location=origin_location,
            destination_location=destination_location,
            mode=route_mode,
        )
        distance_text = route_summary["distance_text"]
        duration_text = route_summary["duration_text"]
        route_steps = route_summary["steps"]
        instructions = [step["instruction"] for step in route_steps]
        step_text = "；".join(instructions) if instructions else "高德未返回详细步骤"
        mode_text = "步行" if route_mode == "walking" else "驾车"
        content = (
            f"高德地图路线查询结果：从{origin}到{destination}，{mode_text}距离{distance_text}，"
            f"预计{duration_text}。主要步骤：{step_text}。"
        )
        result = ToolResult(
            status="ok",
            message="已查询高德路线",
            data={
                "origin": origin,
                "destination": destination,
                "origin_location": origin_location,
                "destination_location": destination_location,
                "mode": route_mode,
                "route": {
                    "distance": str(path.get("distance", "")),
                    "duration": str(path.get("duration", "")),
                    "steps": route_steps,
                },
                "route_summary": route_summary,
            },
            sources=[
                SourceChunk(
                    chunk_id=f"amap_route_{origin}_{destination}",
                    document_id="amap_route",
                    document_name="高德路线规划",
                    content=content,
                    score=1.0,
                    metadata={"source_type": "amap_route", "route_summary": route_summary},
                )
            ],
        )
        _set_cached_tool_result(self.cache, cache_key, result, self.settings.redis_route_cache_ttl_seconds)
        return result


def _build_client(settings: AppSettings) -> AmapClient | None:
    if not settings.map_api_key:
        return None
    return AmapClient(
        api_key=settings.map_api_key,
        base_url=settings.amap_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def _build_cache(settings: AppSettings) -> RedisJsonCache | None:
    return RedisJsonCache.from_url(
        enabled=settings.redis_enabled,
        redis_url=settings.redis_url,
        prefix=settings.redis_cache_prefix,
    )


def _get_cached_tool_result(cache: RedisJsonCache | None, key: str) -> ToolResult | None:
    if cache is None:
        return None
    payload = cache.get_json(key)
    if payload is None:
        return None
    return _tool_result_from_payload(payload)


def _set_cached_tool_result(cache: RedisJsonCache | None, key: str, result: ToolResult, ttl_seconds: int) -> None:
    if cache is None:
        return
    cache.set_json(key, _tool_result_to_payload(result), ttl_seconds)


def _tool_result_to_payload(result: ToolResult) -> dict:
    return {
        "status": result.status,
        "message": result.message,
        "data": result.data,
        "sources": [
            {
                "chunk_id": source.chunk_id,
                "document_id": source.document_id,
                "document_name": source.document_name,
                "content": source.content,
                "score": source.score,
                "metadata": source.metadata,
            }
            for source in result.sources
        ],
    }


def _tool_result_from_payload(payload: dict) -> ToolResult | None:
    try:
        return ToolResult(
            status=str(payload.get("status", "")),
            message=str(payload.get("message", "")),
            data=dict(payload.get("data") or {}),
            sources=[
                SourceChunk(
                    chunk_id=str(source.get("chunk_id", "")),
                    document_id=str(source.get("document_id", "")),
                    document_name=str(source.get("document_name", "")),
                    content=str(source.get("content", "")),
                    score=float(source.get("score", 0.0)),
                    metadata=dict(source.get("metadata") or {}),
                )
                for source in payload.get("sources", [])
                if isinstance(source, dict)
            ],
        )
    except (TypeError, ValueError):
        return None


def _extract_city(text: str, default: str = "无锡") -> str:
    for scenic_name, city in SCENIC_CITY_MAP.items():
        if scenic_name in text:
            return city
    match = re.search(r"([\u4e00-\u9fff]{2,8})(?:市)?(?:今天天气|天气|气温|下雨|温度)", text)
    if match:
        return _clean_city(match.group(1))
    if "无锡" in text:
        return "无锡"
    return default


def _extract_place_keywords(text: str) -> str:
    cleaned = re.sub(r"(帮我|请|查询|查一下|在哪里|怎么走|地图|导航|位置|附近|高德)", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ？?。.")
    return cleaned or text.strip()


def _extract_route_points(text: str) -> tuple[str, str] | None:
    cleaned = re.sub(r"\s+", "", text)
    match = re.search(r"从(.+?)到(.*)$", cleaned)
    if not match:
        return None
    origin = _clean_route_endpoint(match.group(1))
    destination = _clean_route_endpoint(match.group(2), strip_route_suffix=True)
    if not origin or not destination:
        return None
    return origin, destination


def _clean_route_endpoint(text: str, strip_route_suffix: bool = False) -> str:
    cleaned = text.strip(" ，,。.?？")
    if not strip_route_suffix:
        return cleaned

    suffix_patterns = (
        r"(?:怎么走|如何走|怎么去|如何去)$",
        r"(?:的)?(?:步行|走路|步走|开车|驾车|自驾|打车)?(?:路线规划|线路规划|路径规划|路线|线路|路径|导航)$",
        r"(?:的)?(?:步行|走路|步走|开车|驾车|自驾|打车)$",
    )
    while cleaned:
        previous = cleaned
        for pattern in suffix_patterns:
            cleaned = re.sub(pattern, "", cleaned).strip(" ，,。.?？")
        if cleaned == previous:
            break
    return cleaned


def _extract_route_mode(text: str, default_mode: str) -> str:
    if any(keyword in text for keyword in ("步行", "走路", "步走")):
        return "walking"
    if any(keyword in text for keyword in ("开车", "驾车", "自驾", "打车")):
        return "driving"
    return default_mode


def _normalize_route_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized in {"walk", "walking", "步行"}:
        return "walking"
    return "driving"


def _route_steps(raw_steps: list[dict]) -> list[dict]:
    steps = []
    for index, step in enumerate(raw_steps, start=1):
        instruction = str(step.get("instruction", "")).strip()
        if not instruction:
            continue
        steps.append(
            {
                "index": index,
                "instruction": instruction,
                "distance": str(step.get("distance", "")).strip(),
                "duration": str(step.get("duration", "")).strip(),
                "polyline": _split_polyline(str(step.get("polyline", "")).strip()),
            }
        )
    return steps


def _route_polyline(steps: list[dict], origin_location: str, destination_location: str) -> list[str]:
    points = []
    for step in steps:
        points.extend(step.get("polyline") or [])
    if not points:
        points = [origin_location, destination_location]
    return _dedupe_adjacent_points(points)


def _split_polyline(polyline: str) -> list[str]:
    return [point for point in polyline.split(";") if point]


def _dedupe_adjacent_points(points: list[str]) -> list[str]:
    deduped = []
    for point in points:
        if point and (not deduped or deduped[-1] != point):
            deduped.append(point)
    return deduped


def _first_geocode_location(payload: dict) -> str:
    geocodes = payload.get("geocodes") or []
    if not geocodes:
        return ""
    return str(geocodes[0].get("location", "")).strip()


def _format_distance(distance: str | int | float | None) -> str:
    try:
        meters = float(distance or 0)
    except (TypeError, ValueError):
        return "未知距离"
    if meters >= 1000:
        return f"约{meters / 1000:.1f}公里"
    return f"约{int(round(meters))}米"


def _format_duration(duration: str | int | float | None) -> str:
    try:
        seconds = float(duration or 0)
    except (TypeError, ValueError):
        return "未知时间"
    minutes = max(1, int(round(seconds / 60)))
    return f"约{minutes}分钟"


def _clean_city(city: str) -> str:
    return re.sub(r"(今天|明天|后天|现在|当前)$", "", city) or city
