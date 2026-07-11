from pathlib import Path


DEFAULT_SYSTEM_PROMPT = (
    "你是景区 AI 导游。只能依据提供的景区资料回答；"
    "如果资料中没有可靠依据，必须说明当前资料无法确认，禁止编造。"
)


def load_system_prompt(prompt_path: Path) -> str:
    path = Path(prompt_path)
    if not path.exists():
        return DEFAULT_SYSTEM_PROMPT
    content = path.read_text(encoding="utf-8").strip()
    return content or DEFAULT_SYSTEM_PROMPT
