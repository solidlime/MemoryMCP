"""Conversation file importer.

Supports three formats:
- **Claude Code JSONL** (``~/.claude/projects/{id}/*.jsonl``)
- **Claude.ai JSON** (web export — ``conversations.json``)
- **ChatGPT JSON** (``conversations.json`` export)

Extracts user messages as candidate memories.  Short or trivial messages are
skipped.  Each message is auto-tagged with ``type_classifier`` and stored with
``source_context="convo_import"``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ConvoMessage:
    """A normalised conversation message."""

    role: str  # "user" | "assistant"
    content: str
    timestamp: str | None = None


# ---------------------------------------------------------------------------
# Format detectors / parsers
# ---------------------------------------------------------------------------

_MIN_CONTENT_LENGTH = 20  # chars — skip trivial one-liners
_MAX_CONTENT_LENGTH = 4000  # chars — truncate very long messages


def _extract_text(content: object) -> str:
    """Recursively extract plain text from various content shapes."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                t = item.get("type", "")
                if t == "text":
                    parts.append(str(item.get("text", "")))
                elif t == "tool_result":
                    # skip tool outputs
                    pass
                elif "text" in item:
                    parts.append(str(item["text"]))
        return " ".join(p.strip() for p in parts if p.strip())
    if isinstance(content, dict):
        if "parts" in content:
            return _extract_text(content["parts"])
        if "text" in content:
            return str(content["text"])
    return ""


def _parse_claude_code_jsonl(path: Path) -> list[ConvoMessage]:
    """Parse Claude Code project JSONL files (one JSON object per line)."""
    messages: list[ConvoMessage] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj: dict = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = obj.get("type", "")
            ts = obj.get("timestamp")

            # Event style: {"type": "user"|"assistant", "message": {...}}
            inner = obj.get("message") or obj
            role = inner.get("role", msg_type)
            raw_content = inner.get("content", "")
            text = _extract_text(raw_content)

            if role in ("user", "human") and text:
                messages.append(ConvoMessage(role="user", content=text, timestamp=ts))

    return messages


def _parse_claude_ai_json(data: object) -> list[ConvoMessage]:
    """Parse Claude.ai web export JSON.

    Handles both single-conversation ``{"messages": [...]}`` and
    multi-conversation ``{"conversations": [...]}`` shapes.
    """
    messages: list[ConvoMessage] = []

    def _extract_from_msg_list(msg_list: list) -> None:
        for m in msg_list:
            if not isinstance(m, dict):
                continue
            role = m.get("role", m.get("sender", ""))
            content = _extract_text(m.get("content", ""))
            if role in ("user", "human") and content:
                messages.append(ConvoMessage(role="user", content=content))

    if isinstance(data, dict):
        if "messages" in data:
            _extract_from_msg_list(data["messages"])
        elif "conversations" in data:
            for convo in data.get("conversations", []):
                if isinstance(convo, dict):
                    _extract_from_msg_list(convo.get("messages", []))
    elif isinstance(data, list):
        for convo in data:
            if isinstance(convo, dict):
                _extract_from_msg_list(convo.get("messages", []))

    return messages


def _parse_chatgpt_json(data: object) -> list[ConvoMessage]:
    """Parse ChatGPT ``conversations.json`` export.

    Structure:
    ``[{"mapping": {"<uuid>": {"message": {"author": {"role": "user"},
                                            "content": {"parts": [...]}}}}}]``
    """
    messages: list[ConvoMessage] = []
    convos = data if isinstance(data, list) else [data]
    for convo in convos:
        if not isinstance(convo, dict):
            continue
        mapping = convo.get("mapping", {})
        for node in mapping.values():
            if not isinstance(node, dict):
                continue
            msg = node.get("message")
            if not msg or not isinstance(msg, dict):
                continue
            author = msg.get("author", {})
            role = author.get("role", "")
            content = _extract_text(msg.get("content", ""))
            if role in ("user", "human") and content:
                ts = msg.get("create_time")
                messages.append(
                    ConvoMessage(
                        role="user",
                        content=content,
                        timestamp=str(ts) if ts else None,
                    )
                )
    return messages


def _detect_format(path: Path, data: object) -> str:
    """Detect conversation export format from file extension and content."""
    if path.suffix.lower() == ".jsonl":
        return "claude_code"

    if isinstance(data, dict):
        if "conversations" in data:
            return "claude_ai"
        if "messages" in data:
            return "claude_ai"
        if "mapping" in data:
            return "chatgpt"
    elif isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and "mapping" in first:
            return "chatgpt"
        if isinstance(first, dict) and "messages" in first:
            return "claude_ai"

    return "unknown"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _is_trivial(text: str) -> bool:
    """Return True for messages that are not worth storing as memories."""
    stripped = text.strip()
    if len(stripped) < _MIN_CONTENT_LENGTH:
        return True
    # Pure URL lines
    if re.match(r"^https?://\S+$", stripped):
        return True
    # Just "ok", "yes", "no", "thanks", etc.
    return bool(re.match(r"^(ok|yes|no|yeah|sure|thanks|thank you|got it|understood)[.!?]*$", stripped, re.IGNORECASE))


def parse_conversation_file(file_path: str) -> list[ConvoMessage]:
    """Parse a conversation export file and return user messages.

    Args:
        file_path: Path to the conversation file (JSONL or JSON).

    Returns:
        List of non-trivial user ``ConvoMessage`` objects.

    Raises:
        OSError: If the file cannot be read.
        ValueError: If the format cannot be detected or parsed.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    messages: list[ConvoMessage] = []

    if path.suffix.lower() == ".jsonl":
        messages = _parse_claude_code_jsonl(path)
    else:
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {file_path}: {exc}") from exc

        fmt = _detect_format(path, data)
        if fmt == "claude_ai":
            messages = _parse_claude_ai_json(data)
        elif fmt == "chatgpt":
            messages = _parse_chatgpt_json(data)
        else:
            raise ValueError(
                f"Unknown conversation format in {file_path}. "
                "Supported: Claude Code JSONL, Claude.ai JSON, ChatGPT JSON."
            )

    # Filter trivial messages and truncate
    filtered: list[ConvoMessage] = []
    for m in messages:
        if _is_trivial(m.content):
            continue
        if len(m.content) > _MAX_CONTENT_LENGTH:
            m.content = m.content[:_MAX_CONTENT_LENGTH]
        filtered.append(m)

    return filtered
