"""EmotionDecay: 時間経過による感情の自然な減衰ロジック。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memory_mcp.domain.persona.entities import PersonaState
    from memory_mcp.domain.persona.service import PersonaService

logger = logging.getLogger(__name__)

# 感情強度の半減期（時間）
_EMOTION_HALF_LIFE: float = 24.0


def compute_emotion_decay(intensity: float, elapsed_hours: float) -> float:
    """指数減衰で新しい感情強度を計算する。
    減衰係数 = 0.5^(経過時間/半減期)
    """
    if elapsed_hours <= 0 or intensity <= 0.0:
        return 0.0
    factor = 0.5 ** (elapsed_hours / _EMOTION_HALF_LIFE)
    return max(0.0, round(intensity * factor, 4))


async def apply_emotion_decay_if_needed(
    persona_service: PersonaService,
    persona: str,
    state: PersonaState,
) -> bool:
    """経過時間に基づいて感情強度を減衰、永続化する。"""
    from memory_mcp.domain.shared.time_utils import get_now

    last_conv = state.last_conversation_time
    if last_conv is None:
        return False

    now = get_now()
    elapsed_hours = (now - last_conv).total_seconds() / 3600.0

    current_intensity = state.emotion_intensity or 0.0
    if current_intensity <= 0.0:
        return False

    new_intensity = compute_emotion_decay(current_intensity, elapsed_hours)
    if abs(new_intensity - current_intensity) < 0.005:
        return False

    # 強度がほぼ0になったらニュートラルに戻す
    if new_intensity < 0.01:
        new_emotion = "neutral"
        new_intensity = 0.0
    else:
        new_emotion = state.emotion

    try:
        result = persona_service.update_emotion(persona, new_emotion, new_intensity)
        if result.is_ok:
            logger.info(
                "EmotionDecay: %s intensity %.3f→%.3f (elapsed=%.1fh)",
                state.emotion,
                current_intensity,
                new_intensity,
                elapsed_hours,
            )
            return True
        logger.warning("EmotionDecay: update_emotion failed: %s", result.error)
    except Exception as e:
        logger.warning("EmotionDecay: unexpected error: %s", e)
    return False
