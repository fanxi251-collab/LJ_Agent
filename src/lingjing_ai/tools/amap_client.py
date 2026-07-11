from typing import Any

import httpx


class AmapApiError(RuntimeError):
    pass


class AmapClient:
    def __init__(self, api_key: str, base_url: str = "https://restapi.amap.com", timeout_seconds: int = 10) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def weather(self, city: str, extensions: str = "base") -> dict[str, Any]:
        return self._get(
            "/v3/weather/weatherInfo",
            {
                "city": city,
                "extensions": extensions,
            },
        )

    def place_search(self, keywords: str, city: str = "", offset: int = 5) -> dict[str, Any]:
        params = {
            "keywords": keywords,
            "offset": str(offset),
        }
        if city:
            params["city"] = city
        return self._get("/v3/place/text", params)

    def geocode(self, address: str, city: str = "") -> dict[str, Any]:
        params = {"address": address}
        if city:
            params["city"] = city
        return self._get("/v3/geocode/geo", params)

    def walking_route(self, origin: str, destination: str) -> dict[str, Any]:
        return self._get(
            "/v3/direction/walking",
            {
                "origin": origin,
                "destination": destination,
            },
        )

    def driving_route(self, origin: str, destination: str) -> dict[str, Any]:
        return self._get(
            "/v3/direction/driving",
            {
                "origin": origin,
                "destination": destination,
            },
        )

    def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        request_params = {"key": self.api_key, **params}
        try:
            response = httpx.get(f"{self.base_url}{path}", params=request_params, timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AmapApiError(f"高德地图 API 调用失败：{exc}") from exc

        if str(payload.get("status")) != "1":
            message = payload.get("info") or payload.get("infocode") or "未知错误"
            raise AmapApiError(f"高德地图 API 返回错误：{message}")
        return payload
