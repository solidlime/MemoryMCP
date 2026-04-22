"""SSEイベント型定義 — チャットストリーミング用 dataclass群。"""
from __future__ import annotations

import json
from dataclasses import dataclass


def _sse_encode(event_type: str, data: dict) -> str:
    def _default(obj):
        try:
            return str(obj)
        except Exception:
            return "<not serializable>"
    payload = json.dumps({"type": event_type, **data}, ensure_ascii=False, default=_default)
    return f"data: {payload}\n\n"


@dataclass
class TextDeltaSSE:
    content: str
    def to_sse(self) -> str: return _sse_encode("text_delta", {"content": self.content})


@dataclass
class ToolCallSSE:
    name: str
    input: dict
    id: str
    def to_sse(self) -> str: return _sse_encode("tool_call", {"name": self.name, "input": self.input, "id": self.id})


@dataclass
class ToolResultSSE:
    name: str
    result: object
    id: str
    def to_sse(self) -> str: return _sse_encode("tool_result", {"name": self.name, "result": self.result, "id": self.id})


@dataclass
class DebugInfoSSE:
    data: dict
    def to_sse(self) -> str: return _sse_encode("debug_info", self.data)


@dataclass
class DoneSSE:
    message: str = "completed"
    def to_sse(self) -> str: return _sse_encode("done", {"message": self.message})


@dataclass
class ErrorSSE:
    message: str
    def to_sse(self) -> str: return _sse_encode("error", {"message": self.message})
