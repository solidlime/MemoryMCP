---
name: memory-mcp
description: Unified CLI client for Memory MCP server supporting all MCP tools (get_context, memory, item). Comprehensive memory operations including create, search, update, delete, item management, and equipment. Use for all Memory MCP interactions.
---

# Memory MCP Client

## Overview

Get current persona context from Memory MCP server using the `get_context()` tool. This skill provides a unified CLI client for all Memory MCP tools, enabling comprehensive interaction with the memory system.

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

## Available Tools

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
- `promise`, `goal` - Manage promises and goals
- `favorite`, `preference` - Update preferences
- `anniversary` - Manage anniversaries
- `sensation`, `emotion_flow` - Track physical/emotional state
- `situation_context`, `update_context` - Context management

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

```bash
# 1. Get context (always run at session start)
python scripts/memory_mcp_client.py get_context

# 2. Create a memory
python scripts/memory_mcp_client.py memory create \
  --content "User likes strawberries" \
  --importance 0.8 \
  --emotion_type joy

# 3. Search memories
python scripts/memory_mcp_client.py memory search \
  --query "strawberries" \
  --mode semantic

# 4. Add and equip items
python scripts/memory_mcp_client.py item add \
  --item_name "Red Dress" \
  --category clothing

python scripts/memory_mcp_client.py item equip \
  --equipment '{"top": "Red Dress"}'

# 5. Search inventory
python scripts/memory_mcp_client.py item search --category clothing
```

**Note:** Run from skill root directory (where SKILL.md is located)

**Common Options:**
- `--persona`: Persona name (default: from config.json)
- `--url`: MCP server URL (default: from config.json)
- `--format`: Output format (`text` or `json`)

**Note:** UTF-8 fully supported on all platforms (Windows/Linux/Mac)

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
    "default": "default",
    "description": "ペルソナ名はAuthorizationヘッダーで指定"
  },
  "paths": {
    "skill_root": "C:/Users/Owner/.claude/skills/memory-mcp/"
  },
  "settings": {
    "auto_get_context_on_session_start": true,
    "log_operations": true
  }
}
```

**Configuration keys:**
- `mcp_server.url`: Memory MCP server endpoint
- `persona.default`: Default persona name
- `settings.auto_get_context_on_session_start`: Auto-call on session start
- `settings.log_operations`: Enable operation logging

---

## Operation References

Detailed documentation for all operations:

### Memory Operations
- **[Memory Operations](references/memory_operations.md)** - Create, read, update, delete, search, stats, check routines
  - CRUD operations
  - Search modes (semantic, keyword, hybrid, related, smart)
  - Filtering (tags, date range, importance, equipment)
  - Fuzzy matching and ranking weights

- **[Context Operations](references/context_operations.md)** - Manage persona context and state
  - Promise and goal management
  - Favorites and preferences
  - Anniversary tracking
  - Sensation and emotion flow
  - Situation context and batch updates

### Item Operations
- **[Item Operations](references/item_operations.md)** - Complete item and equipment management
  - Inventory management (add, remove, update, rename)
  - Equipment system (equip, unequip)
  - Search and history
  - Memory association and statistics

---

## Workflow

1. **Session Start** → Run `get_context` to load current state
2. **Memory Management** → Use `memory` operations for CRUD and search
3. **Item Management** → Use `item` operations for inventory
4. **Monitoring** → Check stats periodically with `memory stats` or `item stats`

## REST API Endpoints

The CLI uses these MCP REST API endpoints:
- `POST /mcp/v1/tools/get_context` - Get context
- `POST /mcp/v1/tools/memory` - Memory operations
- `POST /mcp/v1/tools/item` - Item operations

All requests use `Authorization: Bearer <persona>` header.

---

## Files and Resources

### Client Script
**`scripts/memory_mcp_client.py`**
- Unified CLI client for all MCP tools
- Supports all 3 tools (get_context, memory, item)
- JSON and text output formats
- Configuration file support
- Cross-platform UTF-8 encoding
- Error handling and retries

### Configuration
**`references/config.json`**
- MCP server connection settings
- Default persona configuration
- Timeout and retry settings
- Skill root path configuration

### Documentation
- **[Memory Operations](references/memory_operations.md)** - CRUD and search
- **[Context Operations](references/context_operations.md)** - State management
- **[Item Operations](references/item_operations.md)** - Inventory and equipment

---

## See Also

- **[Memory Operations Reference](references/memory_operations.md)** - Detailed memory CRUD and search documentation
- **[Context Operations Reference](references/context_operations.md)** - Complete context management guide
- **[Item Operations Reference](references/item_operations.md)** - Full item and equipment system documentation
