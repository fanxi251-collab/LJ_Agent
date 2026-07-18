from __future__ import annotations

import math
from typing import Any


KEY_STEP_WORDS = ("转", "进入", "驶入", "出口", "匝道", "靠左", "靠右", "掉头", "到达")
MIN_KEY_STEPS = 8
MAX_KEY_STEPS = 12
MAX_POLYLINE_POINTS = 500


def select_key_route_steps(
    raw_steps: list[dict[str, Any]],
    min_steps: int = MIN_KEY_STEPS,
    max_steps: int = MAX_KEY_STEPS,
) -> list[dict[str, str | int]]:
    """Select an ordered route digest so the UI is useful without persisting Amap's full payload."""
    steps = _compact_steps(raw_steps)
    if len(steps) <= max_steps:
        return steps

    required = {0, len(steps) - 1}
    required.update(
        index
        for index, step in enumerate(steps)
        if any(word in str(step["instruction"]) for word in KEY_STEP_WORDS)
    )
    if len(required) > max_steps:
        middle = _evenly_pick(sorted(required - {0, len(steps) - 1}), max_steps - 2)
        required = {0, len(steps) - 1, *middle}

    if len(required) < min_steps:
        available = [index for index in range(len(steps)) if index not in required]
        required.update(_evenly_pick(available, min_steps - len(required)))

    return [steps[index] for index in sorted(required)[:max_steps]]


def simplify_route_polyline(
    points: list[str],
    max_points: int = MAX_POLYLINE_POINTS,
) -> list[str]:
    """Use RDP before a hard cap because shape-preserving reduction produces a clearer route than slicing."""
    deduped = _dedupe_adjacent(points)
    if len(deduped) <= max_points:
        return deduped

    coordinates = [_parse_point(point) for point in deduped]
    if any(point is None for point in coordinates):
        return _uniform_downsample(deduped, max_points)

    valid_coordinates = [point for point in coordinates if point is not None]
    longitude_span = max(point[0] for point in valid_coordinates) - min(
        point[0] for point in valid_coordinates
    )
    latitude_span = max(point[1] for point in valid_coordinates) - min(
        point[1] for point in valid_coordinates
    )
    # Scale tolerance to the route extent so RDP runs once; the explicit hard cap handles complex remnants.
    epsilon = max(longitude_span, latitude_span) / max_points
    simplified_indexes = _rdp_indexes(valid_coordinates, max(epsilon, 0.000001))
    simplified = [deduped[index] for index in simplified_indexes]
    if len(simplified) > max_points:
        simplified = _uniform_downsample(simplified, max_points)
    return simplified


def build_route_summary(
    path: dict[str, Any],
    *,
    origin: str,
    destination: str,
    origin_location: str,
    destination_location: str,
    mode: str,
) -> dict[str, Any]:
    """Build the V2 route contract once so APIs, sources, maps and answer validation share one truth."""
    raw_steps = list(path.get("steps") or [])
    raw_points = _route_points(raw_steps, origin_location, destination_location)
    polyline = simplify_route_polyline(raw_points)
    return {
        "schema_version": 2,
        "origin": origin,
        "destination": destination,
        "origin_location": origin_location,
        "destination_location": destination_location,
        "mode": mode,
        "mode_text": "步行" if mode == "walking" else "驾车",
        "distance_text": _format_distance(path.get("distance")),
        "duration_text": _format_duration(path.get("duration")),
        "steps": select_key_route_steps(raw_steps),
        "total_step_count": len(_compact_steps(raw_steps)),
        "polyline": polyline,
        "original_polyline_point_count": len(raw_points),
        "polyline_simplified": len(polyline) < len(raw_points),
    }


def _compact_steps(raw_steps: list[dict[str, Any]]) -> list[dict[str, str | int]]:
    compact = []
    for original_index, step in enumerate(raw_steps, start=1):
        instruction = str(step.get("instruction", "")).strip()
        if not instruction:
            continue
        compact.append(
            {
                "index": original_index,
                "instruction": instruction,
                "distance": str(step.get("distance", "")).strip(),
                "duration": str(step.get("duration", "")).strip(),
            }
        )
    return compact


def _route_points(raw_steps: list[dict[str, Any]], origin: str, destination: str) -> list[str]:
    points = []
    for step in raw_steps:
        points.extend(point for point in str(step.get("polyline", "")).split(";") if point)
    return _dedupe_adjacent(points or [origin, destination])


def _evenly_pick(indexes: list[int], count: int) -> list[int]:
    if count <= 0 or not indexes:
        return []
    if count >= len(indexes):
        return indexes
    if count == 1:
        return [indexes[len(indexes) // 2]]
    positions = [round(index * (len(indexes) - 1) / (count - 1)) for index in range(count)]
    return [indexes[position] for position in positions]


def _parse_point(point: str) -> tuple[float, float] | None:
    try:
        longitude, latitude = point.split(",", maxsplit=1)
        return float(longitude), float(latitude)
    except (TypeError, ValueError):
        return None


def _rdp_indexes(points: list[tuple[float, float]], epsilon: float) -> list[int]:
    keep = {0, len(points) - 1}
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        if end <= start + 1:
            continue
        maximum = 0.0
        farthest = -1
        for index in range(start + 1, end):
            distance = _perpendicular_distance(points[index], points[start], points[end])
            if distance > maximum:
                maximum = distance
                farthest = index
        if farthest >= 0 and maximum > epsilon:
            keep.add(farthest)
            stack.append((start, farthest))
            stack.append((farthest, end))
    return sorted(keep)


def _perpendicular_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    if start == end:
        return math.dist(point, start)
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    projection = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / (dx * dx + dy * dy)
    closest = (start[0] + projection * dx, start[1] + projection * dy)
    return math.dist(point, closest)


def _uniform_downsample(points: list[str], max_points: int) -> list[str]:
    if len(points) <= max_points:
        return points
    indexes = [round(index * (len(points) - 1) / (max_points - 1)) for index in range(max_points)]
    return [points[index] for index in indexes]


def _dedupe_adjacent(points: list[str]) -> list[str]:
    deduped = []
    for point in points:
        if point and (not deduped or deduped[-1] != point):
            deduped.append(point)
    return deduped


def _format_distance(distance: str | int | float | None) -> str:
    try:
        meters = float(distance or 0)
    except (TypeError, ValueError):
        return "未知距离"
    return f"约{meters / 1000:.1f}公里" if meters >= 1000 else f"约{int(round(meters))}米"


def _format_duration(duration: str | int | float | None) -> str:
    try:
        seconds = float(duration or 0)
    except (TypeError, ValueError):
        return "未知时间"
    return f"约{max(1, int(round(seconds / 60)))}分钟"
