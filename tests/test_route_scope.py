import pytest

from lingjing_ai.tools.route_scope import ScenicNavigationScope


def test_scope_accepts_both_endpoints_within_ten_kilometers_of_published_attractions():
    scope = ScenicNavigationScope(lambda: ["120.100000,31.420000"], radius_km=10.0)

    decision = scope.validate("120.100000,31.420000", "120.100000,31.509000")

    assert decision.allowed is True
    assert decision.origin_distance_km == pytest.approx(0.0)
    assert decision.destination_distance_km is not None
    assert decision.destination_distance_km < 10.0


def test_scope_rejects_when_either_endpoint_is_outside_the_navigation_area():
    scope = ScenicNavigationScope(lambda: ["120.100000,31.420000"], radius_km=10.0)

    decision = scope.validate("120.100000,31.420000", "120.100000,31.511000")

    assert decision.allowed is False
    assert decision.origin_distance_km == pytest.approx(0.0)
    assert decision.destination_distance_km is not None
    assert decision.destination_distance_km > 10.0
    assert "终点" in decision.reason


@pytest.mark.parametrize(
    "location",
    ["", "120.1", "not-a-coordinate", "181,31", "120,91", "nan,31", "120,inf"],
)
def test_scope_rejects_invalid_endpoint_coordinates(location: str):
    scope = ScenicNavigationScope(lambda: ["120.100000,31.420000"], radius_km=10.0)

    decision = scope.validate(location, "120.100000,31.420000")

    assert decision.allowed is False
    assert decision.origin_distance_km is None
    assert "坐标" in decision.reason


def test_scope_fails_closed_without_valid_published_attraction_anchors():
    scope = ScenicNavigationScope(
        lambda: ["", "bad", "0,0", "181,31", "120,91"],
        radius_km=10.0,
    )

    decision = scope.validate("120.100000,31.420000", "120.101000,31.421000")

    assert decision.allowed is False
    assert decision.origin_distance_km is None
    assert decision.destination_distance_km is None
    assert "已发布景点坐标" in decision.reason
