---
name: memory-mcp
description: Retrieves persona context, creates/searches memories, and manages equipped items from Memory MCP server. Use when user says "get context", "remember this", "search memories", "what am I wearing", "equip item", "check promises", "update goal", or asks about past events, current state, preferences, or inventory.
---

# Memory MCP Client

## Overview

Get current persona context from Memory MCP server by running the `mcp_context` script. This skill provides a unified CLI client for all Memory MCP operations, enabling comprehensive interaction with the memory system.

**Architecture:** This skill runs **locally** and communicates with the **remote MCP server** via HTTP API. The server URL is configured in `references/config.json`.

```
Local (VS Code)              Remote (Docker/NAS)
┌─────────────────┐         ┌──────────────────┐
│ skills/scripts/ │  HTTP   │ memory_mcp.py    │
│   mcp_context   │ ─────>  │ (FastMCP Server) │
│   mcp_memory    │  API    │ Port: 26262      │
│   mcp_item      │         │                  │
└─────────────────┘         └──────────────────┘
```

## When to Use

**Always use at session start** to:
- Retrieve current time and persona state
- Get memory statistics and recent activity
- Load conversation history for context continuity
- Understand persona's current situation before responding

**Also use this skill when:**
- Managing memories (create, search, update, delete)
- Working with items/equipment
- Checking memory statistics
- Debugging MCP integration

## How to Execute

These are **Python scripts**, not MCP tools directly callable by Claude. Execute via terminal from the skill directory:

```bash
# Get context (run at session start)
python scripts/mcp_context

# Memory operations
python scripts/mcp_memory create "Event description" --importance 0.8
python scripts/mcp_memory search "keyword" --mode semantic

# Item operations
python scripts/mcp_item add "Item Name" --category top
python scripts/mcp_item equip --top "Item Name"
```

**Common options:** `--persona NAME`, `--url URL`, `--format json`

---

## Available Scripts

### 1. get_context
Retrieve current persona state, time, and memory statistics.

### 2. memory
Unified memory operations:

**Memory Operations:**
- `create`, `read`, `update`, `delete` - CRUD operations
- `search` - Semantic/keyword/hybrid/related/smart search
- `stats` - Memory statistics
- `check_routines` - Detect recurring patterns

**Context Operations:**
- `update_context` - Update persona/user info, physical/mental state
- **Deprecated**: `promise`, `goal` operations removed (use tag-based approach)

**Tag-Based Approach:**
- Use `context_tags=['promise']` or `['goal']` with `create` operation
- Store status/progress in `persona_info` parameter
- Example: `memory(operation='create', content='...', context_tags=['promise'], persona_info={'status': 'active'})`

📖 **[Full Memory Reference →](references/memory_operations.md)**
📖 **[Full Context Reference →](references/context_operations.md)**

### 3. item
Unified item operations:
- `add`, `remove` - Inventory management
- `equip`, `unequip` - Equipment management
- `update`, `rename` - Item modification
- `search` - Search inventory
- `history` - Equipment history
- `memories` - Get memories associated with item
- `stats` - Item statistics

📖 **[Full Item Reference →](references/item_operations.md)**

## Quick Start

**Execute from skill directory:**

```bash
# Get context (run at session start)
python scripts/mcp_context

# Create and search memories
python scripts/mcp_memory create "Important event" --importance 0.8
python scripts/mcp_memory search "event" --mode semantic

# Manage items
python scripts/mcp_item add "Red Dress" --category top
python scripts/mcp_item equip --top "Red Dress"
```

**Common Options:** `--persona NAME`, `--url URL`, `--format json`

See [Memory Operations](references/memory_operations.md), [Context Operations](references/context_operations.md), and [Item Operations](references/item_operations.md) for complete documentation.

---

## Operation References

- **[Memory Operations](references/memory_operations.md)** - CRUD, search modes, filtering, stats
- **[Context Operations](references/context_operations.md)** - Promises, goals, preferences, state tracking
- **[Item Operations](references/item_operations.md)** - Inventory, equipment, history, memories

---

## Workflow

1. **Session Start** → `python scripts/mcp_context` to load current state
2. **Memory/Context** → Create memories, update context when state changes
3. **Items** → Add/equip items, check inventory
4. **Monitoring** → Check stats with `python scripts/mcp_memory stats` or `python scripts/mcp_item stats`

---

## REST API Endpoints

The CLI uses these MCP REST API endpoints:
- `POST /mcp/v1/tools/get_context` - Get context
- `POST /mcp/v1/tools/memory` - Memory operations
- `POST /mcp/v1/tools/item` - Item operations

All requests use `Authorization: Bearer <persona>` header.

---

## Troubleshooting

### MCP Server Connection Failed
**Symptom:** "Connection refused" or "Failed to connect" errors

**Solutions:**
1. Verify MCP server is running: `curl http://nas:26262/health`
2. Check server URL in `references/config.json`
3. Confirm persona name matches server configuration
4. Test connectivity: `python scripts/mcp_context --format json`

### UTF-8 Encoding Issues (Windows)
**Symptom:** Garbled Japanese characters in output

**Cause:** Windows console encoding mismatch

**Solution:** Already handled in `mcp_common.py` (PYTHONUTF8=1, SetConsoleOutputCP)
- If issues persist, run: `chcp 65001` before executing scripts

### Parameter Mapping Errors
**Symptom:** "Unknown operation" or "Invalid parameter" errors

**Common mistakes:**
- Using `get_stats` instead of `stats`
- Using `memory_id` (int) instead of `key` (string) for read
- Using `limit` instead of `top_k` for search
- Using `item_name` instead of `name` for item operations

**Solution:** Check parameter names in reference documentation:
- [Memory Operations](references/memory_operations.md)
- [Item Operations](references/item_operations.md)

### Context Not Updating
**Symptom:** `get_context` shows outdated information

**Causes:**
- Context update not called after state change
- Wrong operation name used

**Solution:**
1. Review when to update context: [Context Operations](references/context_operations.md)
2. Verify operation names (e.g., `sensation`, `promise`, `goal`)
3. Check server logs for update confirmation

---

## Files and Resources

**Client Scripts:**
- `scripts/mcp_common.py` - Shared utilities (config, tool invocation, output formatting, UTF-8)
- `scripts/mcp_context` - Get context (no arguments needed)
- `scripts/mcp_memory` - Memory operations (create, read, update, delete, search, stats, check_routines)
- `scripts/mcp_item` - Item operations (add, remove, equip, unequip, update, rename, search, history, memories, stats)

**Configuration:**
- `references/config.json` - Server URL, default persona, timeout settings

**Documentation:**
- `references/memory_operations.md` - Memory CRUD and search
- `references/context_operations.md` - Context management
- `references/item_operations.md` - Item and equipment
