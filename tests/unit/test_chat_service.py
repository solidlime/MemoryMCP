from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from memory_mcp.application.chat_service import SessionManager, SessionWindow, _sse
from memory_mcp.domain.chat_config import ChatConfig, ChatConfigRepository
from memory_mcp.infrastructure.llm.base import DoneEvent, TextDeltaEvent, ToolCallEvent

# ─────────────────────────────────────────────────────────────
# SessionWindow tests
# ─────────────────────────────────────────────────────────────


class TestSessionWindow:
    def test_initial_empty(self):
        win = SessionWindow(max_turns=3)
        assert len(win) == 0

    def test_add_and_retrieve(self):
        win = SessionWindow(max_turns=2)
        win.add("user", "hello")
        win.add("assistant", "hi there")
        assert len(win) == 2

    def test_max_turns_eviction(self):
        win = SessionWindow(max_turns=2)  # max_messages = 4
        for i in range(6):
            win.add("user" if i % 2 == 0 else "assistant", f"msg{i}")
        assert len(win) == 4

    def test_get_labeled_messages_returns_llm_messages(self):
        win = SessionWindow(max_turns=3)
        ts = datetime(2025, 1, 1, 12, 0, 0)
        win.add("user", "test message", ts)
        now = datetime(2025, 1, 1, 13, 0, 0)
        msgs = win.get_labeled_messages(now)
        assert len(msgs) == 1
        assert msgs[0].role == "user"
        assert msgs[0].content == "test message"
        assert msgs[0].time_label == "1時間前"

    def test_labeled_messages_recent(self):
        win = SessionWindow(max_turns=3)
        now = datetime(2025, 3, 1, 10, 0, 0)
        win.add("user", "just now message", now)
        msgs = win.get_labeled_messages(now)
        assert msgs[0].time_label == "たった今"


# ─────────────────────────────────────────────────────────────
# SessionManager tests
# ─────────────────────────────────────────────────────────────


class TestSessionManager:
    def test_creates_new_session(self):
        mgr = SessionManager(max_sessions=10)
        win = mgr.get_or_create("persona1", "session1", max_turns=3)
        assert isinstance(win, SessionWindow)

    def test_returns_same_session(self):
        mgr = SessionManager(max_sessions=10)
        win1 = mgr.get_or_create("persona1", "session1")
        win2 = mgr.get_or_create("persona1", "session1")
        assert win1 is win2

    def test_different_persona_different_session(self):
        mgr = SessionManager(max_sessions=10)
        win1 = mgr.get_or_create("persona1", "session1")
        win2 = mgr.get_or_create("persona2", "session1")
        assert win1 is not win2

    def test_lru_eviction(self):
        mgr = SessionManager(max_sessions=2)
        mgr.get_or_create("p1", "s1")
        mgr.get_or_create("p2", "s2")
        mgr.get_or_create("p3", "s3")  # p1/s1 should be evicted
        assert ("p1", "s1") not in mgr._sessions
        assert ("p2", "s2") in mgr._sessions
        assert ("p3", "s3") in mgr._sessions

    def test_clear_removes_session(self):
        mgr = SessionManager(max_sessions=10)
        mgr.get_or_create("p1", "s1")
        mgr.clear("p1", "s1")
        assert ("p1", "s1") not in mgr._sessions

    def test_clear_nonexistent_is_noop(self):
        mgr = SessionManager(max_sessions=10)
        mgr.clear("nonexistent", "session")  # should not raise


# ─────────────────────────────────────────────────────────────
# ChatConfig tests
# ─────────────────────────────────────────────────────────────


class TestChatConfig:
    def test_defaults(self):
        cfg = ChatConfig(persona="test")
        assert cfg.provider == "anthropic"
        assert cfg.model == ""
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 2048

    def test_temperature_clamped(self):
        cfg = ChatConfig(persona="test", temperature=5.0)
        assert cfg.temperature == 2.0
        cfg2 = ChatConfig(persona="test", temperature=-1.0)
        assert cfg2.temperature == 0.0

    def test_max_tokens_clamped(self):
        cfg = ChatConfig(persona="test", max_tokens=99999)
        assert cfg.max_tokens == 32768
        cfg2 = ChatConfig(persona="test", max_tokens=0)
        assert cfg2.max_tokens == 1

    def test_window_turns_clamped(self):
        cfg = ChatConfig(persona="test", max_window_turns=100)
        assert cfg.max_window_turns == 50

    def test_tool_calls_clamped(self):
        cfg = ChatConfig(persona="test", max_tool_calls=50)
        assert cfg.max_tool_calls == 20

    def test_get_effective_model_default(self):
        cfg = ChatConfig(persona="test", provider="anthropic", model="")
        assert cfg.get_effective_model() == "claude-opus-4-5"

    def test_get_effective_model_custom(self):
        cfg = ChatConfig(persona="test", provider="anthropic", model="claude-3-haiku-20240307")
        assert cfg.get_effective_model() == "claude-3-haiku-20240307"

    def test_get_effective_base_url_openrouter(self):
        cfg = ChatConfig(persona="test", provider="openrouter", base_url="")
        assert cfg.get_effective_base_url() == "https://openrouter.ai/api/v1"

    def test_get_effective_api_key_stored(self):
        cfg = ChatConfig(persona="test", api_key="sk-abc123")
        assert cfg.get_effective_api_key() == "sk-abc123"

    def test_get_effective_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key-123")
        cfg = ChatConfig(persona="test", provider="anthropic", api_key="")
        assert cfg.get_effective_api_key() == "env-key-123"

    def test_is_configured_with_key(self):
        cfg = ChatConfig(persona="test", api_key="sk-test")
        assert cfg.is_configured() is True

    def test_is_not_configured_without_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        cfg = ChatConfig(persona="test", api_key="")
        assert cfg.is_configured() is False

    def test_to_safe_dict_masks_key(self):
        cfg = ChatConfig(persona="test", api_key="sk-secret-key-12345")
        d = cfg.to_safe_dict()
        assert "secret" not in d["api_key"]
        assert d["api_key"].endswith("****")
        assert d["is_configured"] is True

    def test_to_safe_dict_empty_key(self):
        cfg = ChatConfig(persona="test", api_key="")
        d = cfg.to_safe_dict()
        assert d["api_key"] == ""
        assert d["is_configured"] is False


# ─────────────────────────────────────────────────────────────
# ChatConfigRepository tests
# ─────────────────────────────────────────────────────────────


class TestChatConfigRepository:
    def _make_db(self):
        import sqlite3

        db = sqlite3.connect(":memory:")
        db.execute("""
            CREATE TABLE chat_settings (
                persona TEXT PRIMARY KEY,
                provider TEXT DEFAULT 'anthropic',
                model TEXT DEFAULT '',
                api_key TEXT DEFAULT '',
                base_url TEXT DEFAULT '',
                system_prompt TEXT DEFAULT '',
                temperature REAL DEFAULT 0.7,
                max_tokens INTEGER DEFAULT 2048,
                max_window_turns INTEGER DEFAULT 3,
                max_tool_calls INTEGER DEFAULT 5,
                updated_at TEXT,
                auto_extract INTEGER DEFAULT 1,
                extract_model TEXT DEFAULT '',
                extract_max_tokens INTEGER DEFAULT 512,
                tool_result_max_chars INTEGER DEFAULT 4000,
                mcp_servers TEXT DEFAULT '[]',
                enabled_skills TEXT DEFAULT '[]'
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                content     TEXT NOT NULL DEFAULT '',
                created_at  TEXT,
                updated_at  TEXT
            )
        """)
        db.commit()
        return db

    def test_get_returns_defaults_when_not_found(self):
        db = self._make_db()
        repo = ChatConfigRepository(db)
        cfg = repo.get("persona1")
        assert cfg.persona == "persona1"
        assert cfg.provider == "anthropic"

    def test_save_and_get(self):
        db = self._make_db()
        repo = ChatConfigRepository(db)
        cfg = ChatConfig(
            persona="persona1",
            provider="openai",
            model="gpt-4o",
            api_key="sk-test",
            temperature=0.5,
        )
        repo.save(cfg)
        loaded = repo.get("persona1")
        assert loaded.provider == "openai"
        assert loaded.model == "gpt-4o"
        assert loaded.api_key == "sk-test"
        assert loaded.temperature == 0.5

    def test_save_updates_existing(self):
        db = self._make_db()
        repo = ChatConfigRepository(db)
        cfg1 = ChatConfig(persona="p1", provider="anthropic", api_key="key1")
        repo.save(cfg1)
        cfg2 = ChatConfig(persona="p1", provider="openai", api_key="key2")
        repo.save(cfg2)
        loaded = repo.get("p1")
        assert loaded.provider == "openai"
        assert loaded.api_key == "key2"

    def test_delete(self):
        db = self._make_db()
        repo = ChatConfigRepository(db)
        cfg = ChatConfig(persona="p1", api_key="sk-abc")
        repo.save(cfg)
        repo.delete("p1")
        loaded = repo.get("p1")
        assert loaded.api_key == ""


# ─────────────────────────────────────────────────────────────
# _sse helper tests
# ─────────────────────────────────────────────────────────────


class TestSseHelper:
    def test_format(self):
        result = _sse("text_delta", {"content": "hello"})
        assert result.startswith("data: ")
        assert result.endswith("\n\n")

    def test_json_content(self):
        import json

        result = _sse("done", {"message": "completed"})
        payload = json.loads(result[6:].strip())
        assert payload["type"] == "done"
        assert payload["message"] == "completed"

    def test_unicode_preserved(self):
        result = _sse("text_delta", {"content": "日本語テスト"})
        assert "日本語テスト" in result


# ─────────────────────────────────────────────────────────────
# ChatService basic tests (with mocked LLM provider)
# ─────────────────────────────────────────────────────────────


class TestChatService:
    def _make_ctx(self):
        """Build a minimal mock AppContext."""
        ctx = MagicMock()
        ctx.persona = "test_persona"

        # persona_service
        state = MagicMock()
        state.emotion = "neutral"
        state.emotion_intensity = 0.5
        state.mental_state = None
        state.physical_state = None
        state.environment = None
        state_result = MagicMock()
        state_result.is_ok = True
        state_result.value = state
        ctx.persona_service.get_context.return_value = state_result

        # search_engine
        search_result = MagicMock()
        search_result.is_ok = True
        search_result.value = []
        ctx.search_engine.search.return_value = search_result

        return ctx

    def _make_config(self, api_key="test-key"):
        return ChatConfig(
            persona="test_persona",
            provider="anthropic",
            api_key=api_key,
            model="claude-opus-4-5",
        )

    @pytest.mark.asyncio
    async def test_no_api_key_yields_error(self):
        from memory_mcp.application.chat_service import ChatService

        ctx = self._make_ctx()
        cfg = self._make_config(api_key="")
        service = ChatService()
        chunks = []
        async for chunk in service.chat(ctx, cfg, "sess1", "hello"):
            chunks.append(chunk)
        import json

        assert any("error" in chunk for chunk in chunks)
        payload = json.loads(chunks[0][6:].strip())
        assert payload["type"] == "error"
        assert "APIキー" in payload["message"]

    @pytest.mark.asyncio
    async def test_streams_text_and_done(self):
        from memory_mcp.application.chat_service import ChatService

        async def mock_stream(*args, **kwargs):
            yield TextDeltaEvent(content="Hello ")
            yield TextDeltaEvent(content="world!")
            yield DoneEvent(full_content="Hello world!", tool_calls=[])

        mock_provider = MagicMock()
        mock_provider.stream = mock_stream

        ctx = self._make_ctx()
        cfg = self._make_config(api_key="sk-valid-key")
        service = ChatService()

        with patch("memory_mcp.application.chat_service.get_provider", return_value=mock_provider):
            chunks = []
            async for chunk in service.chat(ctx, cfg, "sess1", "hello"):
                chunks.append(chunk)

        import json

        types = [json.loads(c[6:].strip())["type"] for c in chunks]
        assert "text_delta" in types
        assert "done" in types

    @pytest.mark.asyncio
    async def test_tool_call_executed(self):
        from memory_mcp.application.chat_service import ChatService

        tool_evt = ToolCallEvent(
            tool_name="memory_search",
            tool_input={"query": "test"},
            tool_use_id="tool_001",
        )

        call_count = 0

        async def mock_stream(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield tool_evt
                yield DoneEvent(full_content="", tool_calls=[tool_evt])
            else:
                yield TextDeltaEvent(content="Found it!")
                yield DoneEvent(full_content="Found it!", tool_calls=[])

        mock_provider = MagicMock()
        mock_provider.stream = mock_stream

        ctx = self._make_ctx()
        # Make search return something
        mem = MagicMock()
        mem.content = "test memory"
        mem.importance = 0.8
        mem.tags = []
        search_result = MagicMock()
        search_result.is_ok = True
        search_result.value = [(mem, 0.9)]
        ctx.search_engine.search.return_value = search_result

        cfg = self._make_config(api_key="sk-valid-key")
        service = ChatService()

        with patch("memory_mcp.application.chat_service.get_provider", return_value=mock_provider):
            chunks = []
            async for chunk in service.chat(ctx, cfg, "sess2", "search memories"):
                chunks.append(chunk)

        import json

        types = [json.loads(c[6:].strip())["type"] for c in chunks]
        assert "tool_call" in types
        assert "tool_result" in types
        assert "done" in types
