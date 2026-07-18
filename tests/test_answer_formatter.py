from lingjing_ai.rag.answer_formatter import clean_evidence_text, format_extract_answer, normalize_model_answer


from lingjing_ai.rag.answer_formatter import clean_inline_markdown


def test_clean_inline_markdown_removes_wrappers_but_preserves_block_structure():
    raw = (
        "### **游览建议**\n"
        "- 建议提前查看`开放时间`，参考[景区公告](https://example.com/notice_(v1))。\n"
        "- *合理安排体力*，不要承诺~~永不取消~~。"
    )

    cleaned = clean_inline_markdown(raw)

    assert cleaned == (
        "### 游览建议\n"
        "- 建议提前查看开放时间，参考景区公告。\n"
        "- 合理安排体力，不要承诺永不取消。"
    )


def test_clean_inline_markdown_preserves_plain_operators_and_identifiers():
    raw = (
        "面积估算使用 2 * 3 * 4 或 5*6*7，字段名为 source_type、"
        "MAP_JS_API、A_B_C 和 __init__。"
    )

    assert clean_inline_markdown(raw) == raw


def test_clean_evidence_text_removes_markdown_table_and_heading_noise():
    raw = """
    ## 3. 餐饮与住宿推荐
    | 网购联票 | 225元 | 门票+观光车 |
    • **表演时间**：九龙灌浴每日4-5场。
    --- 
    """

    cleaned = clean_evidence_text(raw)

    assert "##" not in cleaned
    assert "|" not in cleaned
    assert "**" not in cleaned
    assert "•" not in cleaned
    assert "表演时间：九龙灌浴每日4-5场。" in cleaned


def test_format_extract_answer_uses_clean_structured_template():
    answer = format_extract_answer(
        document_name="灵山胜境游览指南.md",
        evidence="## 2. 最佳游览时间\n| 网购联票 | 225元 |\n**九龙灌浴**每日4-5场。",
    )

    assert answer.startswith("### 简要回答")
    assert "### 详细说明" in answer
    assert "### 温馨提示" in answer
    assert "依据：灵山胜境游览指南.md" in answer
    assert "\n## " not in answer
    assert "|" not in answer
    assert "**" not in answer


def test_normalize_model_answer_keeps_only_one_structured_answer():
    answer = normalize_model_answer(
        "### 简要回答\n第一版回答。\n\n"
        "### 详细说明\n- 要点一。\n\n"
        "### 温馨提示\n提示一。\n\n"
        "依据：灵山胜境游览指南.md"
        "### 简要回答\n根据景区资料，## 原始标题\n| 表格 | 残片 |"
    )

    assert answer.count("### 简要回答") == 1
    assert "原始标题" not in answer
    assert "|" not in answer
    assert answer.endswith("依据：灵山胜境游览指南.md")


def test_normalize_model_answer_wraps_plain_text_in_template():
    answer = normalize_model_answer("灵山胜境以灵山大佛和梵宫文化体验闻名。", "灵山胜境游览指南.md")

    assert answer.startswith("### 简要回答")
    assert "### 详细说明" in answer
    assert "### 温馨提示" in answer
    assert "依据：灵山胜境游览指南.md" in answer
