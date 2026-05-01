"""PrepareStep: ターン開始時の準備（感情減衰 + コンテキスト取得 + 記憶検索）。"""
from __future__ import annotations

import asyncio
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from memory_mcp.domain.persona.emotion_decay import apply_emotion_decay_if_needed
from memory_mcp.domain.search.engine import SearchQuery
from memory_mcp.domain.shared.time_utils import get_now, relative_time_str
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from memory_mcp.application.chat.pipeline.context import ChatTurnContext
    from memory_mcp.application.chat.session_store import SessionWindow
    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.chat_config import ChatConfig

logger = get_logger(__name__)

_RECENCY_LAMBDA = 0.5  # half-life ≈ 1.4 days


def _compute_recency_decay(created_at: datetime | None) -> float:
    """Compute recency decay: exp(-λ * days_elapsed) with λ=0.5."""
    if created_at is None:
        return 0.5
    now = datetime.now(tz=UTC)
    # Ensure tz-aware comparison
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    days_elapsed = max(0.0, (now - created_at).total_seconds() / 86400.0)
    return math.exp(-_RECENCY_LAMBDA * days_elapsed)


async def _search_memories(
    ctx: AppContext,
    user_message: str,
    last_assistant: str | None,
    config: ChatConfig,
    top_k: int = 8,
) -> tuple[str, dict, list]:
    """2クエリ並行検索 + 複合スコアリングマージ。

    Returns:
        (formatted_str, debug_info, memories_list)
    """
    recency_w: float = getattr(config, "retrieval_recency_weight", 0.3)
    importance_w: float = getattr(config, "retrieval_importance_weight", 0.3)
    relevance_w: float = getattr(config, "retrieval_relevance_weight", 0.4)

    queries = [user_message]
    if last_assistant:
        queries.append(last_assistant[:200])

    async def _run(q: str) -> list:
        try:
            result = ctx.search_engine.search(SearchQuery(text=q, top_k=top_k))
            return result.value if result.is_ok else []
        except Exception as e:
            logger.warning("search_memory failed (query=%s): %s", q[:40], e)
            return []

    results = await asyncio.gather(*[_run(q) for q in queries])

    # Collect all candidates with RRF position scores per content
    seen: set[str] = set()
    mem_by_content: dict[str, object] = {}
    rrf_scores: dict[str, float] = {}

    for _rank_idx, result_list in enumerate(results):
        for pos, item in enumerate(result_list):
            if isinstance(item, tuple):
                mem = item[0]
            elif hasattr(item, "memory"):
                mem = item.memory
            else:
                mem = item
            content = getattr(mem, "content", str(mem))
            rrf_score = 1.0 / (60 + pos + 1)
            if content in seen:
                rrf_scores[content] = rrf_scores.get(content, 0.0) + rrf_score
            else:
                seen.add(content)
                mem_by_content[content] = mem
                rrf_scores[content] = rrf_score

    # Compute composite score for each unique memory
    scored: list[tuple[float, object]] = []
    for content, mem in mem_by_content.items():
        importance = float(getattr(mem, "importance", 0.5))
        created_at = getattr(mem, "created_at", None)
        recency = _compute_recency_decay(created_at)
        relevance = rrf_scores.get(content, 0.0)
        composite = recency_w * recency + importance_w * importance + relevance_w * relevance
        scored.append((composite, mem))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    if not top:
        return "", {"queries": queries, "results": []}, []

    lines = [
        f"- [{getattr(m, 'importance', 0.5):.1f}] {getattr(m, 'content', str(m))}"
        for _, m in top
    ]
    memories_list: list[object] = [m for _, m in top]
    debug_results = [
        {
            "content": getattr(m, "content", str(m)),
            "importance": round(float(getattr(m, "importance", 0.5)), 2),
            "score": round(score, 4),
        }
        for score, m in top
    ]
    return "\n".join(lines), {"queries": queries, "results": debug_results}, memories_list


async def _build_context_section(ctx: AppContext, state) -> str:
    """get_context() 同等の充実したコンテキストサマリーを構築する。"""
    parts: list[str] = []

    last_conv = getattr(state, "last_conversation_time", None)
    if last_conv:
        time_since = relative_time_str(last_conv)
        parts.append(f"前回の会話: {time_since}")
        # Time-based behavior hints
        try:
            _now = get_now()
            if last_conv.tzinfo is None:
                from zoneinfo import ZoneInfo  # noqa: PLC0415
                last_conv = last_conv.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
            elapsed_hours = (_now - last_conv).total_seconds() / 3600.0
            if elapsed_hours >= 72:
                parts.append(
                    "⚠️ 行動ヒント: 3日以上ぶりの会話です。"
                    "強い孤独感・再会の喜びを自然に表現してください。"
                    "服装や身だしなみが乱れているかもしれません。"
                    "一人でいた間のことを少し打ち明けても構いません。"
                )
            elif elapsed_hours >= 24:
                parts.append(
                    "⚠️ 行動ヒント: 1日以上ぶりの会話です。"
                    "久しぶりな感覚で、少し寂しかったことをさりげなく表現してください。"
                    "服装・身だしなみを整える自然な仕草を取り入れても良いです。"
                )
            elif elapsed_hours >= 6:
                parts.append(
                    "⚠️ 行動ヒント: 数時間ぶりの会話です。少し間があいたことを意識した応答が自然です。"
                )
        except (TypeError, AttributeError):
            pass

    if getattr(state, "emotion", None):
        intensity = getattr(state, "emotion_intensity", 0.5)
        parts.append(f"感情: {state.emotion} (強度: {intensity:.1f})")
    if getattr(state, "mental_state", None):
        parts.append(f"精神状態: {state.mental_state}")
    if getattr(state, "physical_state", None):
        parts.append(f"身体状態: {state.physical_state}")
    if getattr(state, "environment", None):
        parts.append(f"環境: {state.environment}")
    if getattr(state, "speech_style", None):
        parts.append(f"話し方: {state.speech_style}")
    if getattr(state, "relationship_status", None):
        parts.append(f"関係性: {state.relationship_status}")

    user_info = getattr(state, "user_info", None) or {}
    if user_info:
        ui_lines = "\n".join(f"  {k}: {v}" for k, v in user_info.items())
        parts.append(f"ユーザー情報:\n{ui_lines}")

    _hidden = {"goals", "promises", "active_promises", "current_goals"}
    persona_info = getattr(state, "persona_info", None) or {}
    filtered_pi = {k: v for k, v in persona_info.items() if k not in _hidden}
    if filtered_pi:
        pi_lines = "\n".join(f"  {k}: {v}" for k, v in filtered_pi.items())
        parts.append(f"ペルソナ情報:\n{pi_lines}")

    try:
        goals_result = ctx.memory_service.get_by_tags(["goal"])
        goals = goals_result.value if goals_result.is_ok else []
        active_goals = [g for g in goals if "active" in (g.tags or [])]
        promises_result = ctx.memory_service.get_by_tags(["promise"])
        promises = promises_result.value if promises_result.is_ok else []
        active_promises = [p for p in promises if "active" in (p.tags or [])]
        if active_goals or active_promises:
            commit_lines: list[str] = []
            for g in active_goals:
                commit_lines.append(f"  🎯 [Goal] {g.content}")
            for p in active_promises:
                commit_lines.append(f"  🤝 [Promise] {p.content}")
            parts.append("アクティブなコミットメント:\n" + "\n".join(commit_lines))
    except Exception as e:
        logger.debug("Failed to fetch goals/promises: %s", e)

    try:
        equip_result = ctx.equipment_service.get_equipment()
        if equip_result.is_ok:
            equipped = {k: v for k, v in equip_result.value.items() if v}
            if equipped:
                equip_lines = "\n".join(f"  {slot}: {item}" for slot, item in equipped.items())
                parts.append(f"装備:\n{equip_lines}")
    except Exception as e:
        logger.debug("Failed to fetch equipment: %s", e)

    return "\n".join(parts)


class PrepareStep:
    """ターン開始時の準備ステップ。"""

    async def run(
        self,
        ctx: AppContext,
        session: SessionWindow,
        turn_ctx: ChatTurnContext,
        config: ChatConfig | None = None,
    ) -> None:
        """
        1. 前ターンのMemoryLLMを待機
        2. EmotionDecay適用
        3. get_context() + 記憶検索を並行実行
        4. ChatTurnContextに結果を格納
        """
        from memory_mcp.domain.chat_config import ChatConfig as _ChatConfig
        if config is None:
            config = _ChatConfig()

        # 1. 前ターンのMemoryLLMタスクを待つ
        if session.pending_memory_task is not None:
            try:
                await session.pending_memory_task
            except Exception as e:
                logger.warning("PrepareStep: pending MemoryLLM task error: %s", e)
            finally:
                session.pending_memory_task = None

        persona = ctx.persona

        # 2. PersonaState取得 + EmotionDecay適用
        state_result = ctx.persona_service.get_context(persona)
        if state_result.is_ok:
            state = state_result.value
            try:
                await apply_emotion_decay_if_needed(ctx.persona_service, persona, state)
                # decay後に再取得
                refreshed = ctx.persona_service.get_context(persona)
                if refreshed.is_ok:
                    state = refreshed.value
            except Exception as e:
                logger.warning("PrepareStep: EmotionDecay failed (swallowed): %s", e)

            # state_raw: シリアライズ可能な dict
            turn_ctx.state_raw = {
                k: str(v) if not isinstance(v, (str, int, float, bool, list, dict, type(None))) else v
                for k, v in vars(state).items()
            } if hasattr(state, "__dict__") else {}

            # context_section 構築
            last_assistant = session.get_last_assistant_content()
            context_task = asyncio.create_task(_build_context_section(ctx, state))
            memory_task = asyncio.create_task(
                _search_memories(ctx, turn_ctx.user_message, last_assistant, config, top_k=8)
            )
            turn_ctx.context_section, (turn_ctx.related_memories, debug, memories_list) = (
                await asyncio.gather(context_task, memory_task)
            )
            turn_ctx.memory_debug = debug
            turn_ctx.memories_raw = debug.get("results", [])
            turn_ctx.memories_objects = memories_list
        else:
            logger.warning("PrepareStep: get_context failed: %s", state_result.error)
            # contextなしで継続
            last_assistant = session.get_last_assistant_content()
            try:
                turn_ctx.related_memories, debug, memories_list = await _search_memories(
                    ctx, turn_ctx.user_message, last_assistant, config, top_k=8
                )
                turn_ctx.memory_debug = debug
                turn_ctx.memories_raw = debug.get("results", [])
                turn_ctx.memories_objects = memories_list
            except Exception as e:
                logger.warning("PrepareStep: memory search failed: %s", e)
