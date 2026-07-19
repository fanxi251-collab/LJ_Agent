from __future__ import annotations

from dataclasses import dataclass

from lingjing_ai.config.settings import AppSettings


DEFAULT_AVATAR_ID = "mao_pro"
_AVATAR_IDS = (DEFAULT_AVATAR_ID, "chitose", "haruto")


@dataclass(frozen=True)
class RealtimeAvatarProfile:
    avatar_id: str
    voice: str
    style_instruction: str


def avatar_ids() -> tuple[str, ...]:
    """Expose the fixed IDs so clients cannot select arbitrary voices or prompts."""
    return _AVATAR_IDS


def resolve_avatar_profile(
    settings: AppSettings,
    avatar_id: str,
) -> RealtimeAvatarProfile | None:
    """Resolve server-owned voice and style data because client values are untrusted."""
    profiles = {
        "mao_pro": RealtimeAvatarProfile(
            avatar_id="mao_pro",
            voice=settings.realtime_voice_mao_pro,
            style_instruction="保持亲切、自然、耐心的景区导游表达。",
        ),
        "chitose": RealtimeAvatarProfile(
            avatar_id="chitose",
            voice=settings.realtime_voice_chitose,
            style_instruction="使用沉稳、清晰的表达，涉及路线时明确说明方向和关键步骤。",
        ),
        "haruto": RealtimeAvatarProfile(
            avatar_id="haruto",
            voice=settings.realtime_voice_haruto,
            style_instruction=(
                "使用活泼易懂的短句，但不得省略路线数据、限制条件或证据支持的事实。"
            ),
        ),
    }
    return profiles.get(str(avatar_id or "").strip())
