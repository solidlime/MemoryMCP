---
name: context-status
description: Get current persona context from Memory MCP server. Use at session start to retrieve persona state, current time, memory statistics, and conversation history. Essential for maintaining context continuity across sessions.
---

# Context Status

## Overview

Get current persona context from Memory MCP server using the `get_context()` tool. This skill provides session initialization, persona state retrieval, and context-aware response preparation.

## When to Use

**Always use at session start** to:
- Retrieve current time and persona state
- Get memory statistics and recent activity
- Load conversation history for context continuity
- Understand persona's current situation before responding

**Also use when:**
- User asks about current time or date
- Need to check memory statistics
- Want to verify persona configuration
- Debugging context-related issues

## Quick Start

### Using the MCP Tool (Recommended)

Call `get_context()` at the beginning of each session:

```python
# No parameters needed - uses current persona from Authorization header
result = get_context()
```

### Using the Python Script

For standalone testing or debugging:

```bash
# Basic usage with default settings
python scripts/get_context.py

# Specify persona and server
python scripts/get_context.py --persona nilou --url http://localhost:26262

# Get JSON output
python scripts/get_context.py --format json
```

## Configuration

Configuration is stored in `references/config.json`:

```json
{
  "mcp_server": {
    "url": "http://localhost:26262",
    "timeout": 30,
    "retry_attempts": 3
  },
  "persona": {
    "default": "nilou",
    "description": "ペルソナ名はAuthorizationヘッダーで指定"
  },
  "settings": {
    "auto_get_context_on_session_start": true,
    "log_operations": true
  }
}
```

**Key settings:**
- `mcp_server.url`: Memory MCP server endpoint
- `persona.default`: Default persona name
- `settings.auto_get_context_on_session_start`: Auto-call on session start

## Response Format

`get_context()` returns:

```
📊 ペルソナ状態 (nilou)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
現在時刻: 2026-02-09 14:30:00 (JST)
記憶総数: 1,234
最近の活動: 5件

[会話履歴]
- User: こんにちは
- Nilou: こんにちは！今日も素敵な一日になりそうね ✨
```

## Workflow

1. **Session Start** → Call `get_context()`
2. **Parse Response** → Extract time, stats, history
3. **Contextualize** → Use info to inform response
4. **Respond** → Reply with awareness of current context

## Resources

### scripts/get_context.py
Standalone Python script for testing and debugging. Can be used independently of the MCP tool.

**Features:**
- Command-line interface
- JSON and text output formats
- Configuration file support
- Error handling and retries

### references/config.json
Configuration file for MCP server connection and persona settings.

**Customization:**
- Update `mcp_server.url` for different server endpoints
- Change `persona.default` for different personas
- Adjust timeout and retry settings as needed
