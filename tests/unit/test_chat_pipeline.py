"""tests/unit/test_chat_pipeline.py — パイプライン各ステップのユニットテスト。"""

from __future__ import annotations

from memory_mcp.application.chat.events import (
    DebugInfoSSE,
    DoneSSE,
    ErrorSSE,
    TextDeltaSSE,
    ToolCallSSE,
    ToolResultSSE,
)
from memory_mcp.application.chat.pipeline.context import ChatTurnContext

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
        from memory_mcp.domain.persona.emotion_decay import compute_emotion_decay

        result = compute_emotion_decay(intensity=0.0, elapsed_hours=10)
        assert result == 0.0

    def test_decay_after_elapsed(self):
        """intensity=0.8, elapsed=48h (2 half-lives) → 0.8 * 0.25 = 0.2."""
        from memory_mcp.domain.persona.emotion_decay import compute_emotion_decay

        result = compute_emotion_decay(intensity=0.8, elapsed_hours=48.0)
        assert result > 0.0
        assert result < 0.8  # decayed
        # 48h / 24h half-life → factor 0.5^(2) = 0.25 → 0.8*0.25 = 0.2
        assert 0.19 <= result <= 0.21

    def test_no_change_for_zero_elapsed(self):
        """Zero elapsed → decay returns 0.0 (caller skips when elapsed <= 0)."""
        from memory_mcp.domain.persona.emotion_decay import compute_emotion_decay

        result = compute_emotion_decay(intensity=0.8, elapsed_hours=0)
        assert result == 0.0


# --- ToolRegistry ---


class TestToolRegistry:
    def test_builtin_tools_only(self):
        from memory_mcp.application.chat.tools.registry import ToolRegistry
        from memory_mcp.infrastructure.llm.base import ToolDefinition

        tools = [ToolDefinition(name="t1", description="d1", input_schema={})]
        reg = ToolRegistry(tools, mcp_pool=None)
        assert len(reg.get_all_tools()) == 1
        assert reg.get_all_tools()[0].name == "t1"

    def test_mcp_tool_detection(self):
        from memory_mcp.application.chat.tools.registry import ToolRegistry

        reg = ToolRegistry([], mcp_pool=None)
        assert reg.is_mcp_tool("server__tool") is True
        assert reg.is_mcp_tool("memory_create") is False

    def test_truncate_result(self):
        from memory_mcp.application.chat.tools.registry import ToolRegistry

        reg = ToolRegistry([], mcp_pool=None)
        result = {"content": "x" * 10000}
        truncated = reg.truncate_result(result, max_chars=100)
        assert isinstance(truncated, dict)
