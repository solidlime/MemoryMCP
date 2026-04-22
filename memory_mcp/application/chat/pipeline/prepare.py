"""PrepareStep: ターン開始時の準備（感情減衰 + コンテキスト取得 + 記憶検索）。"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from memory_mcp.domain.persona.emotion_decay import apply_emotion_decay_if_needed
from memory_mcp.domain.search.engine import SearchQuery
from memory_mcp.domain.shared.time_utils import relative_time_str
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from memory_mcp.application.chat.pipeline.context import ChatTurnContext
    from memory_mcp.application.chat.session_store import SessionWindow
    from memory_mcp.application.use_cases import AppContext

logger = get_logger(__name__)


async def _search_memories(
    ctx: AppContext, user_message: str, last_assistant: str | None, top_k: int = 8
) -> tuple[str, dict]:
    """2クエリ並行検索 + RRF風マージ。Returns (formatted_str, debug_info)。"""
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

    seen: set[str] = set()
    merged: list = []
    rank_scores: dict[str, float] = {}
    for _rank_idx, result_list in enumerate(results):
        for pos, item in enumerate(result_list):
            if isinstance(item, tuple):
                mem = item[0]
            elif hasattr(item, "memory"):
                mem = item.memory
            else:
                mem = item
            content = getattr(mem, "content", str(mem))
            score = 1.0 / (60 + pos + 1)
            if content in seen:
                rank_scores[content] = rank_scores.get(content, 0.0) + score
            else:
                seen.add(content)
                merged.append((mem, score))
                rank_scores[content] = rank_scores.get(content, 0.0) + score

    merged.sort(key=lambda x: rank_scores.get(getattr(x[0], "content", str(x[0])), 0.0), reverse=True)
    top = merged[:top_k]

    if not top:
        return "", {"queries": queries, "results": []}
    lines = [f"- [{getattr(m, 'importance', 0.5):.1f}] {getattr(m, 'content', str(m))}" for m, _ in top]
    debug_results = [
        {
            "content": getattr(m, "content", str(m)),
            "importance": round(float(getattr(m, "importance", 0.5)), 2),
            "score": round(rank_scores.get(getattr(m, "content", str(m)), 0.0), 4),
        }
        for m, _ in top
    ]
    return "\n".join(lines), {"queries": queries, "results": debug_results}


async def _build_context_section(ctx: AppContext, state) -> str:
    """get_context() 同等の充実したコンテキストサマリーを構築する。"""
    parts: list[str] = []

    last_conv = getattr(state, "last_conversation_time", None)
    if last_conv:
        time_since = relative_time_str(last_conv)
        parts.append(f"前回の会話: {time_since}")

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
    ) -> None:
        """
        1. 前ターンのMemoryLLMを待機
        2. EmotionDecay適用
        3. get_context() + 記憶検索を並行実行
        4. ChatTurnContextに結果を格納
        """
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
                _search_memories(ctx, turn_ctx.user_message, last_assistant, top_k=8)
            )
            turn_ctx.context_section, (turn_ctx.related_memories, debug) = await asyncio.gather(
                context_task, memory_task
            )
            turn_ctx.memory_debug = debug
            turn_ctx.memories_raw = debug.get("results", [])
        else:
            logger.warning("PrepareStep: get_context failed: %s", state_result.error)
            # contextなしで継続
            last_assistant = session.get_last_assistant_content()
            try:
                turn_ctx.related_memories, debug = await _search_memories(
                    ctx, turn_ctx.user_message, last_assistant, top_k=8
                )
                turn_ctx.memory_debug = debug
                turn_ctx.memories_raw = debug.get("results", [])
            except Exception as e:
                logger.warning("PrepareStep: memory search failed: %s", e)
