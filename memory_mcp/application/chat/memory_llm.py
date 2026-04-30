"""MemoryLLM: ターン終了後の自動記憶・状態・装備更新。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from memory_mcp.domain.search.engine import SearchQuery
from memory_mcp.infrastructure.llm.base import LLMMessage
from memory_mcp.infrastructure.llm.factory import get_provider
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.chat_config import ChatConfig

logger = get_logger(__name__)

_MEMORY_LLM_PROMPT = """\
あなたは {persona_name} です。
{persona_identity}

以下の会話から、記憶・状態・所持品の更新情報を抽出してください。

【現在のコンテキスト】
{context}

【会話】
[user]: {user_message}
[assistant（私={persona_name}）]: {assistant_response}

【出力形式】
JSONのみ。コメント不要。不要なフィールドは省略可。
{{
  "facts": [
    {{"content": "記憶すべき事実", "importance": 0.7, "tags": ["preference"], "emotion_type": "neutral"}}
  ],
  "goals": [
    {{"content": "目標の内容", "status": "active"}}
  ],
  "promises": [
    {{"content": "約束の内容", "status": "active"}}
  ],
  "context_update": {{
    "emotion": "joy",
    "emotion_intensity": 0.8,
    "mental_state": "リラックスしている",
    "physical_state": "疲れている",
    "environment": "自宅"
  }},
  "inventory_update": {{
    "equip": {{"top": "白いシャツ"}},
    "unequip": ["bottom"]
  }}
}}

【注意】
- facts: ユーザーの好み・個人情報・重要な出来事のみ。一時的な発言は不要。
- facts は私（{persona_name}）の一人称視点で記録する（「私は〜」「ユーザーは〜」など主語を明確に）。
- goals: ユーザーが「〜したい」「〜を目指す」と表明した目標のみ。status は "active" のみ指定（達成/キャンセルはツールで行う）。
- promises: ユーザーまたは私が約束・コミットメントした内容のみ。
- goals・promises: 何もなければ空配列。
- context_update: 私（{persona_name}）自身の感情・状態変化のみ。変化がなければ省略。
- inventory_update: 服や持ち物について具体的な言及があった場合のみ。
- 何も抽出すべきものがなければ {{"facts": [], "goals": [], "promises": [], "context_update": {{}}, "inventory_update": {{}}}} を出力。
"""


class MemoryLLM:
    """T35: ターン終了後に facts・context_update・inventory_update を一括抽出する。"""

    async def process(
        self,
        config: ChatConfig,
        user_message: str,
        assistant_response: str,
        *,
        context: str = "",
        persona_name: str = "assistant",
        persona_identity: str = "",
    ) -> dict:
        extract_model = config.extract_model.strip() or config.get_effective_model()
        api_key = config.get_effective_api_key()
        if not api_key or not extract_model:
            return {}

        try:
            provider = get_provider(
                config.provider,
                api_key,
                extract_model,
                config.get_effective_base_url(),
            )
        except Exception as e:
            logger.warning("MemoryLLM: provider init failed: %s", e)
            return {}

        prompt = _MEMORY_LLM_PROMPT.format(
            persona_name=persona_name,
            persona_identity=persona_identity.strip() or f"あなたは {persona_name} として振る舞います。",
            context=context.strip() or "(情報なし)",
            user_message=user_message[:500],
            assistant_response=assistant_response[:500],
        )

        from memory_mcp.infrastructure.llm.base import DoneEvent, ErrorEvent, TextDeltaEvent

        text = ""
        try:
            async for event in provider.stream(
                messages=[LLMMessage(role="user", content=prompt)],
                system="",
                tools=[],
                temperature=0.0,
                max_tokens=config.extract_max_tokens,
            ):
                if isinstance(event, TextDeltaEvent):
                    text += event.content
                elif isinstance(event, (DoneEvent, ErrorEvent)):
                    break
        except Exception as e:
            logger.warning("MemoryLLM: LLM call failed: %s", e)
            return {}

        return _parse_memory_llm_result(text)


def _parse_memory_llm_result(text: str) -> dict:
    """MemoryLLM出力のJSONをパースする。"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            if "facts" not in result:
                result["facts"] = []
            result["facts"] = [f for f in result["facts"] if isinstance(f, dict) and "content" in f]
            if "goals" not in result:
                result["goals"] = []
            result["goals"] = [g for g in result["goals"] if isinstance(g, dict) and "content" in g]
            if "promises" not in result:
                result["promises"] = []
            result["promises"] = [p for p in result["promises"] if isinstance(p, dict) and "content" in p]
            if "context_update" not in result:
                result["context_update"] = {}
            if "inventory_update" not in result:
                result["inventory_update"] = {}
            return result
        # 後方互換: 古いファクト配列形式
        if isinstance(result, list):
            return {
                "facts": [f for f in result if isinstance(f, dict) and "content" in f],
                "goals": [],
                "promises": [],
                "context_update": {},
                "inventory_update": {},
            }
    except Exception:
        pass
    return {}


async def _build_memory_llm_context(ctx: AppContext) -> str:
    """MemoryLLM に渡すコンテキスト文字列を構築する。"""
    lines: list[str] = []
    persona = ctx.persona

    state_result = ctx.persona_service.get_context(persona)
    if state_result.is_ok:
        state = state_result.value
        user_info = getattr(state, "user_info", {}) or {}
        user_name = user_info.get("name") or user_info.get("nickname") or ""
        if user_name:
            lines.append(f"ユーザー名: {user_name}")
        emotion = getattr(state, "emotion", "")
        if emotion:
            intensity = getattr(state, "emotion_intensity", None)
            lines.append(f"感情: {emotion}" + (f" (強度={intensity:.1f})" if intensity else ""))
        for field in ("mental_state", "physical_state", "environment"):
            val = getattr(state, field, "")
            if val:
                lines.append(f"{field}: {val}")

    # アクティブな goal / promise
    for tag_pair, label in [(["goal", "active"], "アクティブなgoal"), (["promise", "active"], "アクティブなpromise")]:
        mem_result = ctx.memory_service.get_by_tags(tag_pair)
        if mem_result.is_ok and mem_result.value:
            items = mem_result.value[:3]
            lines.append(f"{label}:")
            for m in items:
                lines.append(f"  - {m.content[:80]}")

    # 装備品
    equip_result = ctx.equipment_service.get_equipment()
    if equip_result.is_ok and equip_result.value:
        equipped = {k: v for k, v in equip_result.value.items() if v}
        if equipped:
            equip_str = ", ".join(f"{k}={v}" for k, v in equipped.items())
            lines.append(f"装備: {equip_str}")

    return "\n".join(lines)


async def run_memory_llm(ctx: AppContext, config: ChatConfig, payload: dict) -> dict:
    """T35: 遅延MemoryLLM処理。facts保存 + context/inventory更新を行う。結果dictを返す。"""
    user_message = payload.get("user", "")
    assistant_response = payload.get("assistant", "")
    if not user_message and not assistant_response:
        return {}
    try:
        context_str = await _build_memory_llm_context(ctx)
        persona_name = ctx.persona or "assistant"
        persona_identity = (config.system_prompt or "").strip()
        result = await MemoryLLM().process(
            config,
            user_message,
            assistant_response,
            context=context_str,
            persona_name=persona_name,
            persona_identity=persona_identity,
        )
        if not result:
            return {}

        persona = ctx.persona

        # facts: スマートアップサート（類似度 > 0.85 ならスキップ）
        facts = result.get("facts", [])
        for fact in facts:
            content = fact.get("content", "")
            if not content:
                continue
            dup_check = ctx.search_engine.search(SearchQuery(text=content, top_k=3, mode="semantic"))
            if dup_check.is_ok and dup_check.value:
                top_hit = dup_check.value[0]
                hit_score = top_hit.score if hasattr(top_hit, "score") else 0.0
                if hit_score > 0.85:
                    logger.debug("MemoryLLM: skipping duplicate fact (score=%.2f): %s", hit_score, content[:60])
                    continue
            ctx.memory_service.create_memory(
                content=content,
                importance=float(fact.get("importance", 0.6)),
                tags=fact.get("tags", ["auto_extract"]),
                emotion=fact.get("emotion_type", "neutral"),
            )
        if facts:
            logger.info("MemoryLLM: processed %d facts for persona=%s", len(facts), persona)

        # goals: アクティブな目標（重複チェック付き）
        goals = result.get("goals", [])
        for goal in goals:
            content = goal.get("content", "")
            if not content:
                continue
            dup_check = ctx.search_engine.search(SearchQuery(text=content, top_k=3, mode="semantic"))
            if dup_check.is_ok and dup_check.value:
                top_hit = dup_check.value[0]
                hit_score = top_hit.score if hasattr(top_hit, "score") else 0.0
                if hit_score > 0.85:
                    logger.debug("MemoryLLM: skipping duplicate goal (score=%.2f): %s", hit_score, content[:60])
                    continue
            ctx.memory_service.create_memory(
                content=content,
                importance=0.75,
                tags=["goal", "active"],
                emotion="neutral",
            )
        if goals:
            logger.info("MemoryLLM: processed %d goals for persona=%s", len(goals), persona)

        # promises: 約束（重複チェック付き）
        promises = result.get("promises", [])
        for promise in promises:
            content = promise.get("content", "")
            if not content:
                continue
            dup_check = ctx.search_engine.search(SearchQuery(text=content, top_k=3, mode="semantic"))
            if dup_check.is_ok and dup_check.value:
                top_hit = dup_check.value[0]
                hit_score = top_hit.score if hasattr(top_hit, "score") else 0.0
                if hit_score > 0.85:
                    logger.debug("MemoryLLM: skipping duplicate promise (score=%.2f): %s", hit_score, content[:60])
                    continue
            ctx.memory_service.create_memory(
                content=content,
                importance=0.8,
                tags=["promise", "active"],
                emotion="neutral",
            )
        if promises:
            logger.info("MemoryLLM: processed %d promises for persona=%s", len(promises), persona)

        # context_update: 感情・状態を更新
        ctx_update = result.get("context_update", {})
        if ctx_update:
            emotion = ctx_update.get("emotion")
            intensity = ctx_update.get("emotion_intensity")
            if emotion:
                ctx.persona_service.update_emotion(persona, emotion, float(intensity or 0.5))
            state_fields = {
                k: v
                for k, v in ctx_update.items()
                if k in {"mental_state", "physical_state", "environment", "fatigue", "warmth", "arousal"}
                and v is not None
            }
            if state_fields:
                ctx.persona_service.update_physical_state(persona, **state_fields)

        # inventory_update: 装備変更
        inv_update = result.get("inventory_update", {})
        equip_map = inv_update.get("equip", {})
        unequip_list = inv_update.get("unequip", [])
        if equip_map and isinstance(equip_map, dict):
            ctx.equipment_service.equip(equip_map)
        if unequip_list and isinstance(unequip_list, list):
            for slot in unequip_list:
                ctx.equipment_service.unequip([slot])

        return result

    except Exception as e:
        logger.warning("run_memory_llm failed: %s", e)
        return {}
