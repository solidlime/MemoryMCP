"""EmotionDecay: 時間経過による感情の自然な変化ロジック。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memory_mcp.domain.persona.entities import PersonaState
    from memory_mcp.domain.persona.service import PersonaService

logger = logging.getLogger(__name__)

# 感情ごとの減衰設定: decay_hours で neutral へ。None = 減衰なし
_EMOTION_DECAY: dict[str, dict | None] = {
    "anger": {"decay_hours": 3.0, "to": "neutral"},
    "fear": {"decay_hours": 6.0, "to": "neutral"},
    "joy": {"decay_hours": 24.0, "to": "neutral"},
    "love": {"decay_hours": 12.0, "to": "neutral"},
    "sadness": {"decay_hours": 48.0, "to": "neutral"},
    "excitement": {"decay_hours": 8.0, "to": "neutral"},
    "frustration": {"decay_hours": 4.0, "to": "neutral"},
    "anxiety": {"decay_hours": 12.0, "to": "neutral"},
    "neutral": None,
    "loneliness": None,  # loneliness は会話で自然消滅 (別途処理)
}

# 24時間以上放置されると loneliness が生じる
_LONELINESS_THRESHOLD_HOURS = 24.0
_LONELINESS_INTENSITY_PER_HOUR = 0.02
_LONELINESS_MAX_INTENSITY = 0.9


def compute_emotion_decay(state: PersonaState, elapsed_hours: float) -> dict | None:
    """
    経過時間に基づいて感情の変化を計算する。
    変化がある場合は {"emotion": ..., "intensity": ...} を返す。
    変化なしは None を返す。
    """
    if elapsed_hours <= 0:
        return None

    current_emotion = (state.emotion or "neutral").lower()
    current_intensity = float(state.emotion_intensity or 0.0)

    # loneliness 生成チェック (放置時間が閾値超え)
    if elapsed_hours >= _LONELINESS_THRESHOLD_HOURS:
        loneliness_intensity = min(
            _LONELINESS_MAX_INTENSITY,
            (elapsed_hours - _LONELINESS_THRESHOLD_HOURS) * _LONELINESS_INTENSITY_PER_HOUR + 0.3,
        )
        # 現在の感情が loneliness より弱い場合のみ上書き
        if current_emotion != "loneliness" and current_intensity < loneliness_intensity:
            return {"emotion": "loneliness", "intensity": loneliness_intensity}

    # 通常の感情減衰
    decay_cfg = _EMOTION_DECAY.get(current_emotion)
    if decay_cfg is None:
        return None  # neutral や loneliness は減衰設定なし

    decay_hours: float = decay_cfg["decay_hours"]
    target_emotion: str = decay_cfg["to"]

    if elapsed_hours >= decay_hours:
        # 完全に target へ移行
        if current_emotion != target_emotion:
            return {"emotion": target_emotion, "intensity": 0.0}
    else:
        # 部分的に intensity を下げる
        ratio = elapsed_hours / decay_hours
        new_intensity = max(0.0, current_intensity * (1.0 - ratio))
        if abs(new_intensity - current_intensity) > 0.05:
            return {"emotion": current_emotion, "intensity": new_intensity}

    return None


async def apply_emotion_decay_if_needed(
    persona_service: PersonaService,
    persona: str,
    state: PersonaState,
) -> bool:
    """
    PersonaState の last_conversation_time から経過時間を計算し、
    必要であれば感情を更新して SQLite に永続化する。
    変化があった場合は True を返す。

    チャット PrepareStep と MCP get_context() の両方から呼ばれる。
    """
    from memory_mcp.domain.shared.time_utils import get_now

    last_conv = state.last_conversation_time
    if last_conv is None:
        return False

    now = get_now()
    elapsed_hours = (now - last_conv).total_seconds() / 3600.0

    updates = compute_emotion_decay(state, elapsed_hours)
    if updates is None:
        return False

    try:
        result = persona_service.update_emotion(
            persona,
            updates["emotion"],
            updates["intensity"],
            context=f"emotion_decay: elapsed={elapsed_hours:.1f}h",
        )
        if result.is_ok:
            logger.info(
                "EmotionDecay: %s → %s (intensity=%.2f, elapsed=%.1fh)",
                state.emotion,
                updates["emotion"],
                updates["intensity"],
                elapsed_hours,
            )
            return True
        logger.warning("EmotionDecay: update_emotion failed: %s", result.error)
    except Exception as e:
        logger.warning("EmotionDecay: unexpected error: %s", e)
    return False
