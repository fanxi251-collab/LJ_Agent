import json

from lingjing_ai.tools.route_summary import (
    build_route_summary,
    select_key_route_steps,
    simplify_route_polyline,
)


def _large_route_steps() -> list[dict]:
    steps = []
    keyword_instructions = {
        7: "向右转进入太湖大道",
        36: "靠左驶入快速路匝道",
        72: "从出口驶出",
        99: "掉头后进入景区道路",
    }
    for index in range(108):
        instruction = keyword_instructions.get(index, f"沿道路继续行驶第{index + 1}段")
        steps.append(
            {
                "instruction": instruction,
                "distance": "100",
                "duration": "10",
                "polyline": f"120.{index:03d},31.500;120.{index + 1:03d},31.501",
            }
        )
    steps[0]["instruction"] = "从无锡站出发"
    steps[-1]["instruction"] = "到达灵山胜境"
    return steps


def test_select_key_route_steps_keeps_order_endpoints_and_turns():
    selected = select_key_route_steps(_large_route_steps())

    assert 8 <= len(selected) <= 12
    assert selected[0]["instruction"] == "从无锡站出发"
    assert selected[-1]["instruction"] == "到达灵山胜境"
    assert "向右转进入太湖大道" in [step["instruction"] for step in selected]
    assert "靠左驶入快速路匝道" in [step["instruction"] for step in selected]
    assert "从出口驶出" in [step["instruction"] for step in selected]
    assert "掉头后进入景区道路" in [step["instruction"] for step in selected]
    assert [step["index"] for step in selected] == sorted(step["index"] for step in selected)


def test_select_key_route_steps_keeps_all_when_route_has_at_most_twelve_steps():
    selected = select_key_route_steps(_large_route_steps()[:12])

    assert len(selected) == 12
    assert [step["index"] for step in selected] == list(range(1, 13))


def test_simplify_route_polyline_caps_points_and_keeps_endpoints():
    points = [f"{120 + index / 100000:.5f},{31.5 + (index % 17) / 100000:.5f}" for index in range(12052)]

    simplified = simplify_route_polyline(points)

    assert len(simplified) <= 500
    assert simplified[0] == points[0]
    assert simplified[-1] == points[-1]


def test_build_route_summary_v2_is_compact_and_reports_original_counts():
    steps = _large_route_steps()
    dense_points = [f"{120 + index / 100000:.5f},{31.5 + (index % 17) / 100000:.5f}" for index in range(12052)]
    for index, step in enumerate(steps):
        start = index * len(dense_points) // len(steps)
        end = (index + 1) * len(dense_points) // len(steps)
        step["polyline"] = ";".join(dense_points[start:end])

    summary = build_route_summary(
        {"distance": "42000", "duration": "3600", "steps": steps},
        origin="无锡站",
        destination="灵山胜境",
        origin_location="120.00000,31.50000",
        destination_location="120.12051,31.50008",
        mode="driving",
    )

    assert summary["schema_version"] == 2
    assert summary["total_step_count"] == 108
    assert summary["original_polyline_point_count"] == 12052
    assert summary["polyline_simplified"] is True
    assert len(summary["steps"]) <= 12
    assert len(summary["polyline"]) <= 500
    assert len(json.dumps(summary, ensure_ascii=False).encode("utf-8")) < 100_000
