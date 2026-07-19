from pathlib import Path

from lingjing_ai.config.settings import AppSettings
from lingjing_ai.realtime.avatar_profiles import (
    DEFAULT_AVATAR_ID,
    avatar_ids,
    resolve_avatar_profile,
)


def test_realtime_avatar_profiles_are_server_controlled(tmp_path: Path):
    settings = AppSettings.for_workspace(tmp_path)

    assert DEFAULT_AVATAR_ID == "mao_pro"
    assert avatar_ids() == ("mao_pro", "chitose", "haruto")
    assert resolve_avatar_profile(settings, "mao_pro").voice == "longanqian"
    assert resolve_avatar_profile(settings, "chitose").voice == "longanlufeng"
    assert resolve_avatar_profile(settings, "haruto").voice == "longanxiaoxin"
    assert "不得省略路线" in resolve_avatar_profile(settings, "haruto").style_instruction
    assert resolve_avatar_profile(settings, "remote-model") is None
