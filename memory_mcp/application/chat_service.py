from __future__ import annotations

import asyncio
import json
from collections import OrderedDict, deque
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from memory_mcp.domain.search.engine import SearchQuery
from memory_mcp.domain.shared.time_utils import get_now, relative_time_str
from memory_mcp.infrastructure.llm.base import LLMMessage, ToolDefinition
from memory_mcp.infrastructure.llm.factory import get_provider
from memory_mcp.infrastructure.logging.structured import get_logger
from memory_mcp.infrastructure.mcp_client import MCPClientPool

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import AsyncIterator

    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.chat_config import ChatConfig

logger = get_logger(__name__)

_CHAT_SESSIONS_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS chat_sessions ("
    "persona TEXT NOT NULL, session_id TEXT NOT NULL, "
    "messages TEXT NOT NULL DEFAULT '[]', timestamps TEXT NOT NULL DEFAULT '[]', "
    "updated_at TEXT NOT NULL, PRIMARY KEY (persona, session_id))"
)


def _cleanup_expired_sessions(db: sqlite3.Connection, persona: str, ttl_days: int = 7) -> None:
    """TTLを超えた古いチャットセッションをSQLiteから削除する。"""
    try:
        cutoff = (datetime.now().astimezone() - timedelta(days=ttl_days)).isoformat()
        db.execute("DELETE FROM chat_sessions WHERE persona=? AND updated_at < ?", (persona, cutoff))
        db.commit()
    except Exception as e:
        logger.warning("_cleanup_expired_sessions failed: %s", e)


MEMORY_TOOLS = [
    ToolDefinition(
        name="memory_create",
        description="新しい記憶を作成する。重要な情報・感情・出来事を記録する際に使用。",
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "記憶の内容"},
                "importance": {"type": "number", "description": "重要度 0.0〜1.0", "default": 0.6},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "タグリスト"},
                "emotion_type": {
                    "type": "string",
                    "description": "感情タイプ（joy/sadness/anger/fear/neutral等）",
                    "default": "neutral",
                },
            },
            "required": ["content"],
        },
    ),
    ToolDefinition(
        name="memory_search",
        description="記憶を検索する。ユーザーについての情報・過去の出来事を調べる際に使用。",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "検索クエリ"},
                "top_k": {"type": "integer", "description": "取得件数（1〜10）", "default": 5},
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="context_update",
        description="ペルソナ自身の感情・状態を更新する。感情が変わった際に使用。",
        input_schema={
            "type": "object",
            "properties": {
                "emotion": {"type": "string", "description": "感情タイプ"},
                "emotion_intensity": {"type": "number", "description": "感情強度 0.0〜1.0"},
                "mental_state": {"type": "string", "description": "精神状態の説明"},
            },
        },
    ),
    ToolDefinition(
        name="invoke_skill",
        description="特定のスキルを専用コンテキストで実行する。複雑な専門タスクをメインの会話から切り離して処理する",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "スキル名"},
                "task": {"type": "string", "description": "スキルへの具体的な指示"},
            },
            "required": ["name", "task"],
        },
    ),
]

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
- facts: ユーザーの好み・個人情報・約束・重要な出来事のみ。一時的な発言は不要。
- facts は私（{persona_name}）の一人称視点で記録する（「私は〜」「ユーザーは〜」など主語を明確に）。
- context_update: 私（{persona_name}）自身の感情・状態変化のみ。変化がなければ省略。
- inventory_update: 服や持ち物について具体的な言及があった場合のみ。
- 何も抽出すべきものがなければ {{"facts": [], "context_update": {{}}, "inventory_update": {{}}}} を出力。
"""


class SessionWindow:
    def __init__(self, max_turns: int = 3) -> None:
        max_messages = max_turns * 2
        self._messages: deque[dict] = deque(maxlen=max_messages)
        self._timestamps: deque[datetime] = deque(maxlen=max_messages)
        self._db: sqlite3.Connection | None = None
        self._persona: str = ""
        self._session_id: str = ""

    def attach_db(self, db: sqlite3.Connection, persona: str, session_id: str) -> None:
        """SQLite接続とセッション識別子を紐付ける。"""
        self._db = db
        self._persona = persona
        self._session_id = session_id

    def add(self, role: str, content: str, ts: datetime | None = None) -> None:
        self._messages.append({"role": role, "content": content})
        self._timestamps.append(ts or get_now())
        self._persist()

    def _persist(self) -> None:
        """現在のウィンドウ状態をSQLiteにupsertする。"""
        if self._db is None or not self._persona or not self._session_id:
            return
        try:
            messages_json = json.dumps(list(self._messages), ensure_ascii=False)
            timestamps_json = json.dumps([t.isoformat() for t in self._timestamps], ensure_ascii=False)
            now_str = get_now().isoformat()
            self._db.execute(
                "INSERT OR REPLACE INTO chat_sessions"
                " (persona, session_id, messages, timestamps, updated_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (self._persona, self._session_id, messages_json, timestamps_json, now_str),
            )
            self._db.commit()
        except Exception as e:
            logger.warning("SessionWindow._persist failed: %s", e)

    @classmethod
    def from_db(cls, db: sqlite3.Connection, persona: str, session_id: str, max_turns: int = 3) -> SessionWindow | None:
        """SQLiteから既存セッションをロードする。存在しなければNoneを返す。"""
        try:
            row = db.execute(
                "SELECT messages, timestamps FROM chat_sessions WHERE persona=? AND session_id=?",
                (persona, session_id),
            ).fetchone()
            if row is None:
                return None
            window = cls(max_turns=max_turns)
            window.attach_db(db, persona, session_id)
            messages: list[dict] = json.loads(row["messages"] if hasattr(row, "keys") else row[0])
            timestamps_raw: list[str] = json.loads(row["timestamps"] if hasattr(row, "keys") else row[1])
            for msg, ts_str in zip(messages, timestamps_raw, strict=False):
                window._messages.append(msg)
                window._timestamps.append(datetime.fromisoformat(ts_str))
            logger.debug("SessionWindow: loaded %d messages from SQLite (persona=%s)", len(messages), persona)
            return window
        except Exception as e:
            logger.warning("SessionWindow.from_db failed: %s", e)
            return None

    def get_labeled_messages(self, now: datetime | None = None) -> list[LLMMessage]:
        if now is None:
            now = get_now()
        result = []
        for msg, ts in zip(self._messages, self._timestamps, strict=False):
            label = relative_time_str(ts, now)
            result.append(
                LLMMessage(
                    role=msg["role"],
                    content=msg["content"],
                    timestamp=ts,
                    time_label=label,
                )
            )
        return result

    def get_last_assistant_content(self) -> str | None:
        """ウィンドウ内の直近アシスタント発言を返す（なければNone）。"""
        for msg in reversed(self._messages):
            if msg["role"] == "assistant":
                return msg["content"]
        return None

    def __len__(self) -> int:
        return len(self._messages)

    def set_pending(self, payload: dict) -> None:
        """ターン終了時に遅延MemoryLLM処理用のペイロードを保存する。"""
        self._pending_payload: dict | None = payload

    def pop_pending(self) -> dict | None:
        """保存済みのペイロードを取り出してクリアする。"""
        payload = getattr(self, "_pending_payload", None)
        self._pending_payload = None
        return payload


class SessionManager:
    def __init__(self, max_sessions: int = 100) -> None:
        self._max = max_sessions
        self._sessions: OrderedDict[tuple[str, str], SessionWindow] = OrderedDict()

    def get_or_create(
        self,
        persona: str,
        session_id: str,
        max_turns: int = 3,
        db: sqlite3.Connection | None = None,
    ) -> SessionWindow:
        key = (persona, session_id)
        if key in self._sessions:
            self._sessions.move_to_end(key)
            return self._sessions[key]
        if len(self._sessions) >= self._max:
            self._sessions.popitem(last=False)

        # DBがあれば既存セッションのロードを試みる
        window: SessionWindow | None = None
        if db is not None:
            try:
                db.execute(_CHAT_SESSIONS_SCHEMA)
                db.commit()
            except Exception:
                pass
            window = SessionWindow.from_db(db, persona, session_id, max_turns)
            if window is None:
                # 新規セッション作成 + TTLクリーンアップ
                window = SessionWindow(max_turns=max_turns)
                window.attach_db(db, persona, session_id)
                _cleanup_expired_sessions(db, persona)
        else:
            window = SessionWindow(max_turns=max_turns)

        self._sessions[key] = window
        return window

    def clear(self, persona: str, session_id: str) -> None:
        self._sessions.pop((persona, session_id), None)


_session_manager = SessionManager()


async def _search_memories(
    ctx: AppContext, user_message: str, last_assistant: str | None, top_k: int = 8
) -> tuple[str, dict]:
    """T08: 2クエリ並行検索 + RRF風マージ。Returns (formatted_str, debug_info)。"""
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

    # RRF マージ（重複排除: content文字列で判定）
    seen: set[str] = set()
    merged: list = []
    rank_scores: dict[str, float] = {}
    for _rank_idx, result_list in enumerate(results):
        for pos, item in enumerate(result_list):
            # SearchResult dataclass or (Memory, score) tuple
            if isinstance(item, tuple):
                mem = item[0]
            elif hasattr(item, "memory"):
                mem = item.memory
            else:
                mem = item
            content = getattr(mem, "content", str(mem))
            score = 1.0 / (60 + pos + 1)  # RRF k=60
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
            if "context_update" not in result:
                result["context_update"] = {}
            if "inventory_update" not in result:
                result["inventory_update"] = {}
            return result
        # 後方互換: 古いファクト配列形式
        if isinstance(result, list):
            return {
                "facts": [f for f in result if isinstance(f, dict) and "content" in f],
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


async def _run_memory_llm(ctx: AppContext, config: ChatConfig, payload: dict) -> dict:
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
            # 類似検索で重複確認
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
        logger.warning("_run_memory_llm failed: %s", e)
        return {}


class ChatService:
    async def chat(
        self,
        ctx: AppContext,
        config: ChatConfig,
        session_id: str,
        user_message: str,
    ) -> AsyncIterator[str]:
        now = get_now()
        persona = ctx.persona

        # 1. セッションウィンドウ（先に取得して検索クエリ拡張に使う）
        db = ctx.connection.get_memory_db()
        session = _session_manager.get_or_create(persona, session_id, config.max_window_turns, db=db)
        last_assistant = session.get_last_assistant_content()

        # 2. コンテキスト取得 + 記憶検索（T08: 並行実行）
        #    前ターンの MemoryLLM 遅延処理があれば記憶検索と並行して実行
        context_section = ""
        related_memories = ""
        memory_debug: dict = {"queries": [], "results": []}

        pending_payload = session.pop_pending()
        memory_llm_task = None
        if pending_payload and config.auto_extract:
            memory_llm_task = asyncio.create_task(_run_memory_llm(ctx, config, pending_payload))

        state_raw: dict = {}
        try:
            state_result = ctx.persona_service.get_context(persona)
            if state_result.is_ok:
                context_section = await _build_chat_context_section(ctx, state_result.value)
                # raw state for debug
                state_obj = state_result.value
                state_raw = (
                    {
                        k: str(v) if not isinstance(v, (str, int, float, bool, list, dict, type(None))) else v
                        for k, v in vars(state_obj).items()
                    }
                    if hasattr(state_obj, "__dict__")
                    else {}
                )
        except Exception as e:
            logger.warning("get_context failed: %s", e)

        memories_raw: list[dict] = []
        try:
            related_memories, memory_debug = await _search_memories(ctx, user_message, last_assistant, top_k=8)
            memories_raw = memory_debug.get("results", [])
        except Exception as e:
            logger.warning("_search_memories failed: %s", e)

        # MemoryLLM 処理完了を待つ（context_section が最新になるよう）
        memory_llm_result: dict | None = None
        if memory_llm_task is not None:
            try:
                memory_llm_result = await memory_llm_task
            except Exception as e:
                logger.warning("MemoryLLM task error: %s", e)

        # 3. system prompt構築
        base_system = config.system_prompt or f"あなたは{persona}という名前のアシスタントです。"
        jst_now = now.strftime("%Y-%m-%d %H:%M JST")
        system_parts = [base_system, f"\n現在時刻: {jst_now}"]
        if context_section:
            system_parts.append(f"\n--- ペルソナ状態・コンテキスト ---\n{context_section}")
        if related_memories:
            system_parts.append(f"\n--- 関連記憶 ---\n{related_memories}")
        skills_raw: list[dict] = []
        if config.enabled_skills:
            from memory_mcp.config.settings import get_settings
            from memory_mcp.domain.skill import SkillRepository
            from memory_mcp.infrastructure.sqlite.connection import get_global_skills_db

            skill_repo = SkillRepository(get_global_skills_db(get_settings().data_root))
            skills = [skill_repo.get(n) for n in config.enabled_skills]
            skill_lines = [f"- {s.name}: {s.description}" for s in skills if s]
            skills_raw = [s.model_dump() for s in skills if s]
            if skill_lines:
                system_parts.append("\n--- 利用可能なSkill ---\n" + "\n".join(skill_lines))
        system = "\n".join(system_parts)

        # T26/T41/T45: デバッグデータ収集（全コンポーネントを生データで保持）
        debug_data: dict = {
            "session_id": session_id,
            "provider": config.provider,
            "model": config.get_effective_model(),
            "auto_extract": config.auto_extract,
            "window_messages_count": len(session),
            "system_prompt": system,
            "context_state": state_raw,
            "context_summary": context_section,
            "memories_raw": memories_raw,
            "memory_queries": memory_debug.get("queries", []),
            "skills_raw": skills_raw,
            "tools_injected": [],
            "messages_sent": [],
            "tool_calls": [],
            "assistant_response": "",
            "memory_llm_result": memory_llm_result,
        }

        # 4. ウィンドウメッセージ
        window_messages = session.get_labeled_messages(now)

        # 5. プロバイダー初期化
        api_key = config.get_effective_api_key()
        if not api_key:
            yield _sse("error", {"message": "APIキーが設定されていません。チャット設定でAPIキーを入力してください。"})
            return

        try:
            provider = get_provider(
                config.provider,
                api_key,
                config.get_effective_model(),
                config.get_effective_base_url(),
            )
        except Exception as e:
            yield _sse("error", {"message": f"LLMプロバイダーの初期化に失敗: {e}"})
            return

        from memory_mcp.infrastructure.llm.base import DoneEvent, ErrorEvent, TextDeltaEvent, ToolCallEvent

        messages = list(window_messages)
        messages.append(LLMMessage(role="user", content=user_message))
        full_response = ""
        tool_call_count = 0

        async with MCPClientPool(config.mcp_servers) as mcp_pool:
            extra_tools = mcp_pool.list_all_tools()

            # T44: enable_memory_tools フラグでローカル MEMORY_TOOLS を制御
            base_tools = list(MEMORY_TOOLS) if config.enable_memory_tools else []

            # T44: MCPサーバーから来る memory 系ツールの重複フィルタ
            # （同一ツール名または MemoryMCP 由来の MCP ツールは MEMORY_TOOLS と役割が重複）
            _memory_mcp_tool_names = {
                "memory",
                "search_memory",
                "get_context",
                "update_context",
                "item",
                "memory_create",
                "memory_search",
                "context_update",
            }
            filtered_extra = [t for t in extra_tools if t.name.split("__")[-1] not in _memory_mcp_tool_names]

            all_tools = base_tools + filtered_extra

            # T41: ツール定義をデバッグデータに記録
            debug_data["tools_injected"] = [{"name": t.name, "description": t.description} for t in all_tools]
            # T41: 送信メッセージ（初期ウィンドウ）をデバッグデータに記録
            debug_data["messages_sent"] = [
                {"role": m.role, "content": m.content[:500] + "..." if len(m.content or "") > 500 else m.content}
                for m in messages
            ]

            while tool_call_count <= config.max_tool_calls:
                pending_tool_calls: list[ToolCallEvent] = []
                current_text = ""

                async for event in provider.stream(
                    messages=messages,
                    system=system,
                    tools=all_tools,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                ):
                    if isinstance(event, TextDeltaEvent):
                        current_text += event.content
                        full_response += event.content
                        yield _sse("text_delta", {"content": event.content})
                    elif isinstance(event, ToolCallEvent):
                        pending_tool_calls.append(event)
                    elif isinstance(event, DoneEvent):
                        pass
                    elif isinstance(event, ErrorEvent):
                        yield _sse("error", {"message": event.message})
                        return

                if not pending_tool_calls:
                    break

                messages.append(
                    LLMMessage(
                        role="assistant",
                        content=current_text,
                        tool_calls=[
                            {"id": tc.tool_use_id, "name": tc.tool_name, "input": tc.tool_input}
                            for tc in pending_tool_calls
                        ],
                    )
                )

                for tc in pending_tool_calls:
                    yield _sse("tool_call", {"name": tc.tool_name, "input": tc.tool_input, "id": tc.tool_use_id})
                    if "__" in tc.tool_name:
                        tool_result = await mcp_pool.call_tool(tc.tool_name, tc.tool_input)
                    else:
                        tool_result = await _execute_tool(ctx, config, tc.tool_name, tc.tool_input)
                    truncated_result = _truncate_tool_result(tool_result, config.tool_result_max_chars)
                    yield _sse("tool_result", {"name": tc.tool_name, "result": truncated_result, "id": tc.tool_use_id})
                    debug_data["tool_calls"].append(
                        {
                            "name": tc.tool_name,
                            "input": tc.tool_input,
                            "result": truncated_result,
                            "result_raw": tool_result,  # T41: 切り詰め前の生結果
                        }
                    )
                    messages.append(
                        LLMMessage(
                            role="tool",
                            content=json.dumps(truncated_result, ensure_ascii=False),
                            tool_call_id=tc.tool_use_id,
                        )
                    )

                tool_call_count += 1

        session.add("user", user_message, now)
        session.add("assistant", full_response, get_now())

        # T41: 最終レスポンスを debug_data に追加
        debug_data["assistant_response"] = full_response

        # T35: ターン終了時にペイロードを保存（次ターン冒頭でMemoryLLM実行）
        if config.auto_extract and full_response:
            session.set_pending({"user": user_message, "assistant": full_response})

        try:
            yield _sse("debug_info", debug_data)
        except Exception as e:
            logger.warning("debug_info SSE emit failed: %s", e)
            yield _sse("debug_info", {"error": str(e), "system_prompt": debug_data.get("system_prompt", "")[:500]})
        yield _sse("done", {"message": "completed"})


def _format_state_summary(state) -> str:
    """PersonaState から簡潔なサマリーを生成する。(後方互換のため残す)"""
    parts = []
    if hasattr(state, "emotion") and state.emotion:
        intensity = getattr(state, "emotion_intensity", 0.5)
        parts.append(f"感情: {state.emotion} (強度: {intensity:.1f})")
    if hasattr(state, "mental_state") and state.mental_state:
        parts.append(f"精神状態: {state.mental_state}")
    if hasattr(state, "physical_state") and state.physical_state:
        parts.append(f"身体状態: {state.physical_state}")
    if hasattr(state, "environment") and state.environment:
        parts.append(f"環境: {state.environment}")
    return "\n".join(parts)


async def _build_chat_context_section(ctx: AppContext, state) -> str:
    """get_context() 同等の充実したコンテキストサマリーを構築する (T30/T40)。"""
    parts: list[str] = []

    # --- last conversation time (T40) ---
    last_conv = getattr(state, "last_conversation_time", None)
    if last_conv:
        time_since = relative_time_str(last_conv)
        parts.append(f"前回の会話: {time_since}")

    # --- emotion + body state ---
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

    # --- user_info ---
    user_info = getattr(state, "user_info", None) or {}
    if user_info:
        ui_lines = "\n".join(f"  {k}: {v}" for k, v in user_info.items())
        parts.append(f"ユーザー情報:\n{ui_lines}")

    # --- persona_info (goals/promises keys excluded — handled separately) ---
    _hidden = {"goals", "promises", "active_promises", "current_goals"}
    persona_info = getattr(state, "persona_info", None) or {}
    filtered_pi = {k: v for k, v in persona_info.items() if k not in _hidden}
    if filtered_pi:
        pi_lines = "\n".join(f"  {k}: {v}" for k, v in filtered_pi.items())
        parts.append(f"ペルソナ情報:\n{pi_lines}")

    # --- active goals / promises from memory tags ---
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

    # --- equipment (T40) ---
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


async def _execute_tool(ctx: AppContext, config: ChatConfig, tool_name: str, tool_input: dict) -> dict:
    try:
        if tool_name == "memory_create":
            result = ctx.memory_service.create_memory(
                content=tool_input.get("content", ""),
                importance=float(tool_input.get("importance", 0.6)),
                tags=tool_input.get("tags", []),
                emotion=tool_input.get("emotion_type", "neutral"),
            )
            if result.is_ok:
                return {"status": "ok", "key": result.value.key}
            return {"status": "error", "message": str(result.error)}

        elif tool_name == "memory_search":
            query = tool_input.get("query", "")
            top_k = int(tool_input.get("top_k", 5))
            result = ctx.search_engine.search(SearchQuery(text=query, top_k=min(top_k, 10)))
            if result.is_ok:
                items = []
                for item in result.value:
                    mem = item[0] if isinstance(item, tuple) else item
                    items.append(
                        {
                            "content": getattr(mem, "content", str(mem)),
                            "importance": getattr(mem, "importance", 0.5),
                            "tags": getattr(mem, "tags", []),
                        }
                    )
                return {"status": "ok", "memories": items}
            return {"status": "error", "message": str(result.error)}

        elif tool_name == "context_update":
            update_kwargs: dict = {}
            if "emotion" in tool_input:
                update_kwargs["emotion"] = tool_input["emotion"]
            if "emotion_intensity" in tool_input:
                update_kwargs["emotion_intensity"] = float(tool_input["emotion_intensity"])
            if "mental_state" in tool_input:
                update_kwargs["mental_state"] = tool_input["mental_state"]
            if update_kwargs:
                if "emotion" in update_kwargs:
                    ctx.persona_service.update_emotion(
                        ctx.persona,
                        update_kwargs["emotion"],
                        update_kwargs.get("emotion_intensity", 0.5),
                    )
                if "mental_state" in update_kwargs:
                    ctx.persona_service.update_physical_state(ctx.persona, mental_state=update_kwargs["mental_state"])
            return {"status": "ok"}

        elif tool_name == "invoke_skill":
            skill_name = tool_input.get("name", "")
            task = tool_input.get("task", "")
            return await _invoke_skill(ctx, config, skill_name, task)

        else:
            return {"status": "error", "message": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.exception("Tool execution failed: %s", tool_name)
        return {"status": "error", "message": str(e)}


def _sse(event_type: str, data: dict) -> str:
    def _default(obj):
        try:
            return str(obj)
        except Exception:
            return "<not serializable>"

    payload = json.dumps({"type": event_type, **data}, ensure_ascii=False, default=_default)
    return f"data: {payload}\n\n"


async def _invoke_skill(ctx: AppContext, config: ChatConfig, skill_name: str, task: str) -> dict:
    from memory_mcp.config.settings import get_settings
    from memory_mcp.domain.skill import SkillRepository
    from memory_mcp.infrastructure.llm.base import DoneEvent, TextDeltaEvent
    from memory_mcp.infrastructure.sqlite.connection import get_global_skills_db

    skill_repo = SkillRepository(get_global_skills_db(get_settings().data_root))
    skill = skill_repo.get(skill_name)
    if not skill:
        return {"error": f"Skill '{skill_name}' not found"}

    api_key = config.get_effective_api_key()
    if not api_key:
        return {"error": "APIキーが設定されていません"}

    try:
        provider = get_provider(
            config.provider,
            api_key,
            config.get_effective_model(),
            config.get_effective_base_url(),
        )
    except Exception as e:
        return {"error": f"Provider init failed: {e}"}

    text = ""
    try:
        async for event in provider.stream(
            messages=[LLMMessage(role="user", content=task)],
            system=skill.content,
            tools=[],
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        ):
            if isinstance(event, TextDeltaEvent):
                text += event.content
            elif isinstance(event, DoneEvent):
                break
    except Exception as e:
        return {"error": f"Skill execution failed: {e}"}

    return {"result": text or "(no response)"}


def _truncate_tool_result(result: dict, max_chars: int) -> dict:
    """Truncate tool result string to avoid context overflow."""
    result_str = json.dumps(result, ensure_ascii=False)
    if len(result_str) <= max_chars:
        return result
    remaining = len(result_str) - max_chars
    return {
        "truncated": True,
        "content": result_str[:max_chars] + f"... [truncated: {remaining} chars remaining]",
    }
