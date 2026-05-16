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
    def test_no_decay_for_neutral(self):
        """All-zero emotions → no decay (empty dict returned)."""
        from memory_mcp.domain.persona.emotion_decay import compute_emotion_decay

        emotions = {
            "joy": 0.0,
            "sadness": 0.0,
            "anger": 0.0,
            "fear": 0.0,
            "disgust": 0.0,
            "surprise": 0.0,
            "love": 0.0,
            "trust": 0.0,
            "anticipation": 0.0,
        }
        result = compute_emotion_decay(emotions, elapsed_hours=10)
        assert result == {}

    def test_anger_decays_after_threshold(self):
        """anger half-life=3h, elapsed=4h → significant decay."""
        from memory_mcp.domain.persona.emotion_decay import compute_emotion_decay

        emotions = {"anger": 0.8}
        result = compute_emotion_decay(emotions, elapsed_hours=4.0)
        assert result  # non-empty
        assert "anger" in result
        assert result["anger"] < 0.8  # decayed
        # 4h / 3h half-life → factor 0.5^(4/3) ≈ 0.397 → 0.8*0.397 ≈ 0.317
        assert result["anger"] < 0.5

    def test_no_change_for_zero_elapsed(self):
        """Zero elapsed → no decay."""
        from memory_mcp.domain.persona.emotion_decay import compute_emotion_decay

        emotions = {"anger": 0.8, "joy": 0.5}
        result = compute_emotion_decay(emotions, elapsed_hours=0)
        assert result == {}


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
