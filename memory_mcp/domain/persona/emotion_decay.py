"""EmotionDecay: 時間経過による多次元感情の自然な変化ロジック。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memory_mcp.domain.persona.entities import PersonaState
    from memory_mcp.domain.persona.service import PersonaService

logger = logging.getLogger(__name__)

# 基本9感情ごとの半減期（時間）
# None = 減衰なし
_EMOTION_HALF_LIFE: dict[str, float | None] = {
    "joy": 24.0,
    "sadness": 48.0,
    "anger": 3.0,
    "fear": 6.0,
    "disgust": 4.0,
    "surprise": 2.0,
    "love": 12.0,
    "trust": 36.0,
    "anticipation": 8.0,
}

# 24時間以上放置で loneliness 生成
_LONELINESS_THRESHOLD_HOURS = 24.0


def compute_emotion_decay(emotions: dict[str, float], elapsed_hours: float) -> dict[str, float]:
    """各感情次元を独立に指数減衰。変化があった次元のみ含めたdictを返す。"""
    if elapsed_hours <= 0 or not emotions:
        return {}

    decayed: dict[str, float] = {}
    for name, current in emotions.items():
        half_life = _EMOTION_HALF_LIFE.get(name)
        if half_life is None:
            continue
        if current <= 0.0:
            continue
        # 指数減衰: 減衰係数 = 0.5^(経過時間/半減期)
        factor = 0.5 ** (elapsed_hours / half_life)
        new_val = round(current * factor, 4)
        if abs(new_val - current) > 0.005:
            decayed[name] = max(0.0, new_val)

    return decayed


async def apply_emotion_decay_if_needed(
    persona_service: PersonaService,
    persona: str,
    state: PersonaState,
) -> bool:
    """経過時間に基づいて多次元感情を減衰、永続化する。"""
    from memory_mcp.domain.shared.time_utils import get_now

    last_conv = state.last_conversation_time
    if last_conv is None:
        return False

    now = get_now()
    elapsed_hours = (now - last_conv).total_seconds() / 3600.0

    current_emotions = dict(state.emotions) if state.emotions else {}

    # 減衰計算
    decayed = compute_emotion_decay(current_emotions, elapsed_hours)

    # Loneliness 生成チェック
    if elapsed_hours >= _LONELINESS_THRESHOLD_HOURS:
        max_existing = max(current_emotions.values()) if current_emotions else 0.0
        loneliness_val = min(0.9, (elapsed_hours - _LONELINESS_THRESHOLD_HOURS) * 0.02 + 0.3)
        if loneliness_val > max_existing:
            decayed["loneliness"] = loneliness_val  # loneliness is NOT a basic emotion, it's added

    if not decayed:
        return False

    # Merge decayed values into current
    merged = dict(current_emotions)
    merged.update(decayed)

    try:
        result = persona_service.update_emotions(persona, merged)
        if result.is_ok:
            logger.info(
                "EmotionDecay: %d dims decayed (elapsed=%.1fh): %s",
                len(decayed),
                elapsed_hours,
                ", ".join(f"{k}={v:.2f}" for k, v in decayed.items()),
            )
            return True
        logger.warning("EmotionDecay: update_emotions failed: %s", result.error)
    except Exception as e:
        logger.warning("EmotionDecay: unexpected error: %s", e)
    return False
