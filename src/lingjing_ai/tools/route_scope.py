from collections.abc import Callable, Iterable
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class RouteScopeDecision:
    allowed: bool
    origin_distance_km: float | None
    destination_distance_km: float | None
    reason: str = ""


class ScenicNavigationScope:
    def __init__(
        self,
        anchor_provider: Callable[[], Iterable[str]],
        radius_km: float = 10.0,
    ) -> None:
        self.anchor_provider = anchor_provider
        self.radius_km = float(radius_km)
        if not math.isfinite(self.radius_km) or self.radius_km <= 0:
            raise ValueError("景区导航半径必须是正数")

    def validate(self, origin_location: str, destination_location: str) -> RouteScopeDecision:
        origin = _parse_coordinate(origin_location)
        destination = _parse_coordinate(destination_location)
        if origin is None or destination is None:
            invalid_names = []
            if origin is None:
                invalid_names.append("起点")
            if destination is None:
                invalid_names.append("终点")
            return RouteScopeDecision(
                False,
                None,
                None,
                f"{'和'.join(invalid_names)}坐标无效，请核对地点。",
            )

        anchors = [
            coordinate
            for raw_location in self.anchor_provider()
            if (coordinate := _parse_coordinate(raw_location)) is not None
            and coordinate[0] != 0
            and coordinate[1] != 0
        ]
        if not anchors:
            return RouteScopeDecision(
                False,
                None,
                None,
                "景区导航范围暂不可用：缺少有效的已发布景点坐标。",
            )

        origin_distance = min(_haversine_km(origin, anchor) for anchor in anchors)
        destination_distance = min(_haversine_km(destination, anchor) for anchor in anchors)
        outside_names = []
        if origin_distance > self.radius_km:
            outside_names.append("起点")
        if destination_distance > self.radius_km:
            outside_names.append("终点")
        if outside_names:
            # Include the configured radius so visitors can correct the place instead of retrying blindly.
            return RouteScopeDecision(
                False,
                origin_distance,
                destination_distance,
                (
                    f"{'和'.join(outside_names)}超出景区导航范围；本导游仅提供景区及外围"
                    f"{self.radius_km:g}公里内的导航。请核对起点和终点。"
                ),
            )
        return RouteScopeDecision(True, origin_distance, destination_distance)


def _parse_coordinate(location: str) -> tuple[float, float] | None:
    parts = str(location or "").split(",")
    if len(parts) != 2:
        return None
    try:
        longitude, latitude = (float(part.strip()) for part in parts)
    except ValueError:
        return None
    if not math.isfinite(longitude) or not math.isfinite(latitude):
        return None
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        return None
    return longitude, latitude


def _haversine_km(first: tuple[float, float], second: tuple[float, float]) -> float:
    first_lon, first_lat = map(math.radians, first)
    second_lon, second_lat = map(math.radians, second)
    delta_lon = second_lon - first_lon
    delta_lat = second_lat - first_lat
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(first_lat) * math.cos(second_lat) * math.sin(delta_lon / 2) ** 2
    )
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(haversine)))
