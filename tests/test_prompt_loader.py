from pathlib import Path

from lingjing_ai.rag.prompt_loader import load_system_prompt


def test_load_system_prompt_reads_custom_prompt_file(tmp_path: Path):
    prompt_file = tmp_path / "rag_system_prompt.md"
    prompt_file.write_text("自定义景区导游提示词", encoding="utf-8")

    assert load_system_prompt(prompt_file) == "自定义景区导游提示词"


def test_load_system_prompt_uses_default_when_file_missing(tmp_path: Path):
    prompt = load_system_prompt(tmp_path / "missing.md")

    assert "只能依据提供的景区资料回答" in prompt
    assert "禁止编造" in prompt


def test_project_system_prompt_defines_structured_answer_format():
    prompt = load_system_prompt(Path("prompt/rag_system_prompt.md"))

    assert "### 输出格式" in prompt
    assert "### 简要回答" in prompt
    assert "### 详细说明" in prompt
    assert "### 温馨提示" in prompt
    assert "禁止照搬资料中的 Markdown 标题、表格、分隔符" in prompt
