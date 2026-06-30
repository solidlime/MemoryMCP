"""tests/unit/test_chat_pipeline.py — パイプライン各ステップのユニットテスト。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nous.application.chat.events import (
    DebugInfoSSE,
    DoneSSE,
    ErrorSSE,
    TextDeltaSSE,
    ToolCallSSE,
    ToolResultSSE,
)
from nous.application.chat.pipeline.context import ChatTurnContext
from nous.application.chat.pipeline.prepare import _compute_recency_decay

# --- Events ---


class TestSSEEvents:
    def test_text_delta_sse(self):
        ev = TextDeltaSSE(content="hello")
        s = ev.to_sse()
        assert s.startswith("data: ")
        assert '"type": "text_delta"' in s
        assert '"hello"' in s

    def test_tool_call_sse(self):
        ev = ToolCallSSE(name="memory_create", input={"content": "x"}, id="tc1")
        s = ev.to_sse()
        assert '"type": "tool_call"' in s
        assert "memory_create" in s

    def test_tool_result_sse(self):
        ev = ToolResultSSE(name="memory_create", result={"status": "ok"}, id="tc1")
        s = ev.to_sse()
        assert '"type": "tool_result"' in s

    def test_done_sse(self):
        ev = DoneSSE()
        s = ev.to_sse()
        assert '"type": "done"' in s
        assert "completed" in s

    def test_error_sse(self):
        ev = ErrorSSE(message="oops")
        s = ev.to_sse()
        assert '"type": "error"' in s
        assert "oops" in s

    def test_debug_info_sse(self):
        ev = DebugInfoSSE(data={"key": "val"})
        s = ev.to_sse()
        assert '"type": "debug_info"' in s
        assert "val" in s


# --- ChatTurnContext ---


class TestChatTurnContext:
    def test_defaults(self):
        ctx = ChatTurnContext(session_id="s1", user_message="hello")
        assert ctx.context_section == ""
        assert ctx.related_memories == ""
        assert ctx.system_prompt == ""
        assert ctx.full_response == ""
        assert ctx.tool_call_count == 0
        assert ctx.messages == []
        assert ctx.tool_calls_log == []

    def test_session_and_message_set(self):
        ctx = ChatTurnContext(session_id="abc", user_message="test message")
        assert ctx.session_id == "abc"
        assert ctx.user_message == "test message"


# --- EmotionDecay ---


class TestComputeEmotionDecay:
    def test_zero_intensity_no_decay(self):
        """Zero intensity → no decay needed, returns 0.0."""
        from nous.domain.persona.emotion_decay import compute_emotion_decay

        result = compute_emotion_decay(intensity=0.0, elapsed_hours=10)
        assert result == 0.0

    def test_decay_after_elapsed(self):
        """intensity=0.8, elapsed=48h (2 half-lives) → 0.8 * 0.25 = 0.2."""
        from nous.domain.persona.emotion_decay import compute_emotion_decay

        result = compute_emotion_decay(intensity=0.8, elapsed_hours=48.0)
        assert result > 0.0
        assert result < 0.8  # decayed
        # 48h / 24h half-life → factor 0.5^(2) = 0.25 → 0.8*0.25 = 0.2
        assert 0.19 <= result <= 0.21

    def test_no_change_for_zero_elapsed(self):
        """Zero elapsed → decay returns 0.0 (caller skips when elapsed <= 0)."""
        from nous.domain.persona.emotion_decay import compute_emotion_decay

        result = compute_emotion_decay(intensity=0.8, elapsed_hours=0)
        assert result == 0.0


# --- ToolRegistry ---


class TestToolRegistry:
    def test_builtin_tools_only(self):
        from nous.application.chat.tools.registry import ToolRegistry
        from nous.infrastructure.llm.base import ToolDefinition

        tools = [ToolDefinition(name="t1", description="d1", input_schema={})]
        reg = ToolRegistry(tools, mcp_pool=None)
        assert len(reg.get_all_tools()) == 1
        assert reg.get_all_tools()[0].name == "t1"

    def test_mcp_tool_detection(self):
        from nous.application.chat.tools.registry import ToolRegistry

        reg = ToolRegistry([], mcp_pool=None)
        assert reg.is_mcp_tool("server__tool") is True
        assert reg.is_mcp_tool("memory_create") is False

    def test_truncate_result(self):
        from nous.application.chat.tools.registry import ToolRegistry

        reg = ToolRegistry([], mcp_pool=None)
        result = {"content": "x" * 10000}
        truncated = reg.truncate_result(result, max_chars=100)
        assert isinstance(truncated, dict)


# ──────────────────────────────────────────────
# PrepareStep — _compute_recency_decay
# ──────────────────────────────────────────────


class TestComputeRecencyDecay:
    """Tests for _compute_recency_decay()."""

    def test_none_created_at_returns_half(self):
        """When created_at is None, return 0.5 (default half-life decay)."""
        result = _compute_recency_decay(None)
        assert result == 0.5

    def test_tz_naive_created_at(self):
        """A timezone-naive datetime should be handled (converted to UTC)."""
        naive_dt = datetime.now().replace(tzinfo=None) - timedelta(days=1)
        result = _compute_recency_decay(naive_dt)
        assert 0.0 < result < 1.0

    def test_tz_aware_created_at(self):
        """A timezone-aware datetime should work directly."""
        aware_dt = datetime.now(UTC) - timedelta(days=1)
        result = _compute_recency_decay(aware_dt)
        assert 0.0 < result < 1.0

    def test_future_date_clamps_to_zero(self):
        """Created_at in the future should result in days_elapsed=0 → exp(0)=1."""
        future = datetime.now(UTC) + timedelta(days=365)
        result = _compute_recency_decay(future)
        assert result == 1.0

    def test_recent_memory_higher_than_old(self):
        """A very recent memory should have higher recency than a very old one."""
        recent = datetime.now(UTC) - timedelta(hours=1)
        old = datetime.now(UTC) - timedelta(days=30)
        recent_decay = _compute_recency_decay(recent)
        old_decay = _compute_recency_decay(old)
        assert recent_decay > old_decay


# ──────────────────────────────────────────────
# PrepareStep — _build_context_section tier structure
# ──────────────────────────────────────────────


class TestBuildContextSectionLightMode:
    """_build_context_section should skip heavy sections in light/aggressive mode."""

    @pytest.mark.asyncio
    async def test_light_mode_skips_heavy_sections(self):
        """compress_mode='light' should skip reflection, mental model, session summary, emotion history."""
        from unittest.mock import MagicMock

        from nous.application.chat.pipeline.prepare import _build_context_section

        ctx = MagicMock()
        ctx.persona = "test"
        ctx.memory_service = MagicMock()
        ctx.persona_service = MagicMock()
        ctx.equipment_service = MagicMock()

        # State with minimal data to trigger tiers
        state = MagicMock()
        state.last_conversation_time = None
        state.emotion = None
        state.mental_state = None
        state.speech_style = None
        state.physical_state = None
        state.environment = None
        state.relationship_status = None
        state.user_info = {}
        state.persona_info = {}
        state.fatigue = None
        state.pain = None
        state.arousal = None

        result = await _build_context_section(ctx, state, compress_mode="light")
        # Should still contain basic info
        assert "Now:" in result
        # Should not call emotion history
        ctx.persona_service.get_emotion_history.assert_not_called()
        # Light mode should not fetch heavy sections (reflection, mental_model, session_summary)
        for call_args in ctx.memory_service.get_by_tags.call_args_list:
            tags = call_args[0][0]
            assert "reflection" not in tags
            assert "mental_model" not in tags
            assert "session_summary" not in tags


class TestBuildContextSectionNormalMode:
    """_build_context_section should include heavy sections in auto/normal mode."""

    @pytest.mark.asyncio
    async def test_normal_mode_includes_all_sections(self):
        """compress_mode='auto' should attempt to fetch all sections."""
        from unittest.mock import MagicMock

        from nous.application.chat.pipeline.prepare import _build_context_section
        from nous.domain.shared.result import Success

        ctx = MagicMock()
        ctx.persona = "test"
        ctx.memory_service = MagicMock()
        ctx.memory_service.get_by_tags.return_value = Success([])
        ctx.persona_service = MagicMock()
        ctx.persona_service.get_emotion_history.return_value = Success([])
        ctx.equipment_service = MagicMock()
        ctx.equipment_service.get_equipment.return_value = Success({})

        state = MagicMock()
        state.last_conversation_time = None
        state.emotion = None
        state.mental_state = None
        state.speech_style = None
        state.physical_state = None
        state.environment = None
        state.relationship_status = None
        state.user_info = {}
        state.persona_info = {}
        state.fatigue = None
        state.pain = None
        state.arousal = None

        result = await _build_context_section(ctx, state, compress_mode="auto")
        assert "Now:" in result


class TestBuildContextSectionTierContent:
    """Verify specific tier content in _build_context_section."""

    @pytest.mark.asyncio
    async def test_tier1_emotion_and_mental_state(self):
        """Tier1 should include emotion and mental state when present."""
        from unittest.mock import MagicMock

        from nous.application.chat.pipeline.prepare import _build_context_section

        ctx = MagicMock()
        ctx.persona = "test"
        ctx.memory_service = MagicMock()
        ctx.memory_service.get_by_tags.return_value = MagicMock()
        ctx.memory_service.get_by_tags.return_value.is_ok = False
        ctx.persona_service = MagicMock()
        ctx.persona_service.get_emotion_history.return_value = MagicMock()
        ctx.persona_service.get_emotion_history.return_value.is_ok = False
        ctx.equipment_service = MagicMock()
        ctx.equipment_service.get_equipment.return_value = MagicMock()
        ctx.equipment_service.get_equipment.return_value.is_ok = False

        state = MagicMock()
        state.last_conversation_time = None
        state.emotion = "喜び"
        state.emotion_intensity = 0.8
        state.mental_state = "集中"
        state.speech_style = "元気"
        state.physical_state = None
        state.environment = None
        state.relationship_status = None
        state.user_info = {}
        state.persona_info = {}
        state.fatigue = None
        state.pain = None
        state.arousal = None

        result = await _build_context_section(ctx, state)
        assert "喜び" in result
        assert "集中" in result
        assert "元気" in result
        assert "強い" in result  # intensity 0.8 > 0.6 → "強い"

    @pytest.mark.asyncio
    async def test_tier2_body_metrics_and_environment(self):
        """Tier2 should include body metrics and environment when present."""
        from unittest.mock import MagicMock

        from nous.application.chat.pipeline.prepare import _build_context_section

        ctx = MagicMock()
        ctx.persona = "test"
        ctx.memory_service = MagicMock()
        ctx.memory_service.get_by_tags.return_value = MagicMock()
        ctx.memory_service.get_by_tags.return_value.is_ok = False
        ctx.persona_service = MagicMock()
        ctx.persona_service.get_emotion_history.return_value = MagicMock()
        ctx.persona_service.get_emotion_history.return_value.is_ok = False
        ctx.equipment_service = MagicMock()
        ctx.equipment_service.get_equipment.return_value = MagicMock()
        ctx.equipment_service.get_equipment.return_value.is_ok = False

        state = MagicMock()
        state.last_conversation_time = None
        state.emotion = None
        state.mental_state = None
        state.speech_style = None
        state.physical_state = "少し疲れた"
        state.fatigue = 0.8
        state.pain = 0.0
        state.arousal = 0.3
        state.environment = "自室"
        state.relationship_status = None
        state.user_info = {}
        state.persona_info = {}
        state.equipped_items = None

        result = await _build_context_section(ctx, state)
        assert "身体:" in result
        assert "疲労" in result
        assert "自室" in result

    @pytest.mark.asyncio
    async def test_tier2_user_info_and_persona_info(self):
        """Tier2 should include user_info and persona_info."""
        from unittest.mock import MagicMock

        from nous.application.chat.pipeline.prepare import _build_context_section

        ctx = MagicMock()
        ctx.persona = "test"
        ctx.memory_service = MagicMock()
        ctx.memory_service.get_by_tags.return_value = MagicMock()
        ctx.memory_service.get_by_tags.return_value.is_ok = False
        ctx.persona_service = MagicMock()
        ctx.persona_service.get_emotion_history.return_value = MagicMock()
        ctx.persona_service.get_emotion_history.return_value.is_ok = False
        ctx.equipment_service = MagicMock()
        ctx.equipment_service.get_equipment.return_value = MagicMock()
        ctx.equipment_service.get_equipment.return_value.is_ok = False

        state = MagicMock()
        state.last_conversation_time = None
        state.emotion = None
        state.mental_state = None
        state.speech_style = None
        state.physical_state = None
        state.fatigue = None
        state.pain = None
        state.arousal = None
        state.environment = None
        state.relationship_status = None
        state.user_info = {"name": "Taro", "age": "30"}
        state.persona_info = {"role": "assistant", "goals": "hidden_goal"}

        result = await _build_context_section(ctx, state)
        assert "ユーザー情報:" in result
        assert "Taro" in result
        assert "ペルソナ情報:" in result
        assert "assistant" in result
        # goals should be filtered out (in _hidden set)
        assert "hidden_goal" not in result
