from lingjing_ai.agent.models import AgentEvidence, ToolTrace
from lingjing_ai.models.rag import SourceChunk
from lingjing_ai.realtime.answer_contract import build_answer_contract, finalize_answer


def _source(name: str, content: str, *, route_summary: dict | None = None) -> SourceChunk:
    metadata = {"section_path": "游览信息"}
    document_id = name
    if route_summary is not None:
        metadata = {"source_type": "amap_route", "route_summary": route_summary}
        document_id = "amap_route"
    return SourceChunk(
        chunk_id=f"chunk_{name}",
        document_id=document_id,
        document_name=name,
        content=content,
        score=0.9,
        metadata=metadata,
    )


def _evidence(*sources: SourceChunk, trace: list[ToolTrace] | None = None) -> AgentEvidence:
    return AgentEvidence(
        question="请介绍灵山胜境",
        sources=list(sources),
        confidence=0.9,
        is_answered=True,
        trace_id="trace_1",
        tool_trace=trace or [],
    )


def _route_summary() -> dict:
    return {
        "schema_version": 2,
        "origin": "无锡站",
        "destination": "灵山胜境",
        "mode": "driving",
        "mode_text": "驾车",
        "distance_text": "约42.0公里",
        "duration_text": "约60分钟",
        "steps": [
            {"index": index, "instruction": f"第{index}步进入道路"}
            for index in range(1, 9)
        ],
        "total_step_count": 108,
        "polyline": ["120.305,31.590", "120.100,31.500"],
    }


def test_finalizer_removes_inline_markdown_before_returning_model_answer():
    evidence = _evidence(_source("景区介绍.md", "灵山胜境适合文化深度游。"))
    contract = build_answer_contract(evidence, "avatar")

    finalized = finalize_answer(
        evidence,
        contract,
        "**游览建议**：建议提前通过官方渠道确认当日开放时间。",
    )

    assert finalized.text == "游览建议：建议提前通过官方渠道确认当日开放时间。"
    assert "**" not in finalized.text


def test_regular_and_avatar_contracts_have_distinct_length_requirements():
    evidence = _evidence(_source("景区介绍.md", "灵山胜境以灵山大佛和佛教文化景观闻名。"))

    regular = build_answer_contract(evidence, "text")
    avatar = build_answer_contract(evidence, "avatar")

    assert regular.profile == "text_detailed"
    assert "300—600字" in regular.instructions
    assert "3—5个" in regular.instructions
    assert avatar.profile == "avatar_summary"
    assert "3—6句" in avatar.instructions


def test_route_contract_requires_complete_text_but_short_avatar_summary():
    evidence = _evidence(
        _source("高德路线规划", "高德路线结果", route_summary=_route_summary()),
        trace=[ToolTrace("amap_route", "从无锡站到灵山胜境", "ok", "已查询", 1)],
    )

    regular = build_answer_contract(evidence, "text")
    avatar = build_answer_contract(evidence, "avatar")

    assert regular.profile == "route_text"
    assert "8—12条" in regular.instructions
    assert avatar.profile == "route_avatar"
    assert "完整步骤由路线面板展示" in avatar.instructions


def test_short_reliable_regular_answer_appends_distinct_source_facts():
    evidence = _evidence(
        _source("景区介绍.md", "灵山胜境以灵山大佛闻名。景区还有九龙灌浴表演。"),
        _source("游览指南.md", "建议预留半天游览，并穿着便于步行的鞋。"),
    )
    contract = build_answer_contract(evidence, "text")

    finalized = finalize_answer(evidence, contract, "灵山胜境值得游览。")

    assert "### 资料要点" in finalized.appended_text
    assert "景区介绍.md" in finalized.text
    assert "游览指南.md" in finalized.text
    assert len(finalized.appended_text) <= 450


def test_short_answer_is_not_padded_when_evidence_is_insufficient_or_avatar():
    insufficient = AgentEvidence(
        question="介绍一下",
        sources=[_source("资料.md", "资料内容")],
        confidence=0.1,
        is_answered=False,
        trace_id="trace_2",
        tool_trace=[],
    )
    text_result = finalize_answer(insufficient, build_answer_contract(insufficient, "text"), "资料不足。")
    avatar_evidence = _evidence(_source("资料.md", "可靠资料内容。"))
    avatar_result = finalize_answer(
        avatar_evidence,
        build_answer_contract(avatar_evidence, "avatar"),
        "这是简短口播。",
    )

    assert text_result.appended_text == ""
    assert avatar_result.appended_text == ""


def test_route_finalizer_appends_exact_overview_and_all_key_steps_when_model_omits_fields():
    summary = _route_summary()
    evidence = _evidence(
        _source("高德路线规划", "高德路线结果", route_summary=summary),
        trace=[ToolTrace("amap_route", "路线", "ok", "已查询", 1)],
    )
    contract = build_answer_contract(evidence, "text")

    finalized = finalize_answer(evidence, contract, "建议从无锡站出发前往灵山胜境。")

    assert "驾车" in finalized.appended_text
    assert "约42.0公里" in finalized.appended_text
    assert "约60分钟" in finalized.appended_text
    assert "第8步进入道路" in finalized.appended_text
    assert finalized.text.endswith(finalized.appended_text)


def test_route_finalizer_does_not_append_long_block_in_avatar_mode():
    evidence = _evidence(_source("高德路线规划", "高德路线结果", route_summary=_route_summary()))

    finalized = finalize_answer(
        evidence,
        build_answer_contract(evidence, "avatar"),
        "从无锡站驾车到灵山胜境约需60分钟，详情请看路线面板。",
    )

    assert finalized.appended_text == ""


def test_route_tool_failure_returns_specific_error_without_invented_steps():
    evidence = _evidence(
        trace=[ToolTrace("amap_route", "从无锡站到灵山胜境", "error", "高德请求超时", 0)]
    )
    contract = build_answer_contract(evidence, "text")

    finalized = finalize_answer(evidence, contract, "可以沿太湖大道行驶。")

    assert finalized.text == "路线查询失败：高德请求超时。请稍后重试或核对起点和终点。"
    assert "太湖大道" not in finalized.text


def test_clarification_contract_replaces_model_guess_with_exact_question():
    evidence = AgentEvidence(
        question="到灵山胜境怎么走？",
        sources=[],
        confidence=0.0,
        is_answered=False,
        trace_id="trace_clarify",
        tool_trace=[],
        needs_clarification=True,
        clarifying_question="请补充明确的起点。",
    )

    finalized = finalize_answer(
        evidence,
        build_answer_contract(evidence, "text"),
        "可以从无锡站出发。",
    )

    assert finalized.text == "请补充明确的起点。"
