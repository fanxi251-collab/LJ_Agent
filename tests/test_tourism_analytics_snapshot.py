import json
from pathlib import Path

import pytest
from openpyxl import Workbook

from scripts.build_tourism_analytics_snapshot import AnalyticsDataError, build_snapshot


HEADERS = [
    "tourist_id",
    "user_nickname",
    "age",
    "gender",
    "attraction_name",
    "attraction_content",
    "attraction_type",
    "visit_date",
    "stay_duration",
    "ticket_cost",
    "food_cost",
    "shopping_cost",
    "transport_cost",
    "entertainment_cost",
    "total_cost",
    "group_size",
    "satisfaction",
]


def visit_row(
    tourist_id: str,
    attraction_name: str,
    *,
    nickname: str = "需要脱敏的昵称",
    attraction_content: str = "不应进入快照的景点正文",
    age: int = 30,
    gender: str = "女",
    attraction_type: str = "博物馆与展馆",
    visit_date: str = "2025-01-15",
    stay_duration: float = 3.0,
    ticket_cost: float = 20.0,
    food_cost: float = 30.0,
    shopping_cost: float = 40.0,
    transport_cost: float = 10.0,
    entertainment_cost: float = 0.0,
    total_cost: float = 100.0,
    group_size: int = 2,
    satisfaction: int = 5,
) -> list:
    return [
        tourist_id,
        nickname,
        age,
        gender,
        attraction_name,
        attraction_content,
        attraction_type,
        visit_date,
        stay_duration,
        ticket_cost,
        food_cost,
        shopping_cost,
        transport_cost,
        entertainment_cost,
        total_cost,
        group_size,
        satisfaction,
    ]


def write_workbook(path: Path, rows: list[list], headers: list[str] | None = None) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "景点景区旅游数据行为分析数据"
    sheet.append(headers or HEADERS)
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def test_build_snapshot_calculates_dashboard_and_excludes_private_fields(tmp_path: Path):
    source = tmp_path / "tourism.xlsx"
    output = tmp_path / "snapshot.json"
    write_workbook(
        source,
        [
            visit_row("U1", "上海博物馆"),
            visit_row(
                "U1",
                "上海博物馆",
                visit_date="2025-02-01",
                age=30,
                total_cost=150,
                food_cost=80,
                satisfaction=4,
            ),
            visit_row(
                "U2",
                "宁波方特",
                age=42,
                gender="男",
                attraction_type="主题乐园",
                visit_date="2025-02-02",
                stay_duration=9,
                ticket_cost=300,
                food_cost=200,
                shopping_cost=200,
                entertainment_cost=100,
                total_cost=810,
                group_size=4,
                satisfaction=2,
            ),
        ],
    )

    snapshot = build_snapshot(source, output, min_rank_visits=2)

    assert snapshot["metadata"]["schema_version"] == "tourism_analytics_v1"
    assert snapshot["metadata"]["row_count"] == 3
    assert snapshot["metadata"]["period_start"] == "2025-01-15"
    assert snapshot["metadata"]["period_end"] == "2025-02-02"
    assert len(snapshot["metadata"]["source_sha256"]) == 64
    assert snapshot["kpis"] == {
        "visit_count": 3,
        "tourist_count": 2,
        "attraction_count": 2,
        "average_stay_hours": 5.0,
        "average_total_cost": 353.33,
        "average_satisfaction": 3.67,
    }
    assert snapshot["demographics"]["repeat_visitor_rate"] == 0.5
    assert snapshot["monthly_trend"] == [
        {"month": "2025-01", "visit_count": 1},
        {"month": "2025-02", "visit_count": 2},
    ]
    assert snapshot["attraction_rankings"]["popular"][0]["name"] == "上海博物馆"
    assert [item["name"] for item in snapshot["attraction_rankings"]["high_spend"]] == [
        "上海博物馆"
    ]
    assert snapshot["satisfaction"]["distribution"] == [
        {"score": 1, "count": 0},
        {"score": 2, "count": 1},
        {"score": 3, "count": 0},
        {"score": 4, "count": 1},
        {"score": 5, "count": 1},
    ]
    assert snapshot["quality"]["total_cost_mismatch_rows"] == 0
    serialized = json.dumps(snapshot, ensure_ascii=False)
    assert "需要脱敏的昵称" not in serialized
    assert "不应进入快照的景点正文" not in serialized
    assert '"U1"' not in serialized
    assert json.loads(output.read_text(encoding="utf-8")) == snapshot


def test_rankings_apply_sample_threshold_and_stable_name_tiebreak(tmp_path: Path):
    source = tmp_path / "rankings.xlsx"
    rows = []
    for index in range(100):
        rows.append(visit_row(f"A{index}", "A景点", total_cost=200, satisfaction=4))
        rows.append(visit_row(f"B{index}", "B景点", total_cost=200, satisfaction=4))
    for index in range(99):
        rows.append(visit_row(f"C{index}", "小样本景点", total_cost=9999, satisfaction=1))
    write_workbook(source, rows)

    snapshot = build_snapshot(source, min_rank_visits=100)

    assert [item["name"] for item in snapshot["attraction_rankings"]["popular"][:2]] == [
        "A景点",
        "B景点",
    ]
    for ranking_name in ("high_spend", "long_stay", "high_satisfaction", "low_satisfaction"):
        names = [item["name"] for item in snapshot["attraction_rankings"][ranking_name]]
        assert names == ["A景点", "B景点"]
        assert "小样本景点" not in names


def test_missing_required_header_reports_field_name(tmp_path: Path):
    source = tmp_path / "missing-header.xlsx"
    write_workbook(source, [visit_row("U1", "景点")], headers=HEADERS[:-1])

    with pytest.raises(AnalyticsDataError, match="satisfaction"):
        build_snapshot(source)


@pytest.mark.parametrize(
    ("column_index", "invalid_value", "message"),
    [(7, "不是日期", "第 2 行.*visit_date"), (14, "不是金额", "第 2 行.*total_cost")],
)
def test_invalid_required_value_reports_excel_row(
    tmp_path: Path,
    column_index: int,
    invalid_value: str,
    message: str,
):
    source = tmp_path / "invalid.xlsx"
    row = visit_row("U1", "景点")
    row[column_index] = invalid_value
    write_workbook(source, [row])

    with pytest.raises(AnalyticsDataError, match=message):
        build_snapshot(source)


def test_corrupted_workbook_is_rejected_without_overwriting_previous_snapshot(tmp_path: Path):
    source = tmp_path / "corrupted.xlsx"
    output = tmp_path / "snapshot.json"
    source.write_bytes(b"not an xlsx workbook")
    output.write_text('{"previous": true}', encoding="utf-8")

    with pytest.raises(AnalyticsDataError, match="无法读取 Excel"):
        build_snapshot(source, output)

    assert json.loads(output.read_text(encoding="utf-8")) == {"previous": True}
