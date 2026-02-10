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
mcp_context

# 2. Create a memory
mcp_memory create "User likes strawberries" \
  --importance 0.8 \
  --emotion-type joy

# 3. Search memories
mcp_memory search "strawberries" --mode semantic --limit 5

# 4. Add and equip items
mcp_item add "Red Dress" --category top
mcp_item equip --top "Red Dress" --foot "Sandals"

# 5. Search inventory
mcp_item search --category top --equipped
```

**Scripts:**
- `mcp_context` - Get current context (no arguments needed)
- `mcp_memory` - Memory operations (create, read, update, delete, search, etc.)
- `mcp_item` - Item operations (add, remove, equip, unequip, etc.)

**Common Options (all scripts):**
- `--persona`: Persona name (default: from config.json)
- `--url`: MCP server URL (default: from config.json)
- `--format`: Output format (`text` or `json`)

**Examples:**
```bash
# Use different persona
mcp_context --persona alice

# JSON output
mcp_memory search "test" --format json

# Custom server URL
mcp_item search --url http://localhost:8080
```

**Note:** UTF-8 fully supported on all platforms (Windows/Linux/Mac)

## Configuration
Configuration is stored in `references/config.json`

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

---

## Context Update Guidelines

**When to Update Context (use context operations):**

### Physical/Mental State Changes
Update `sensation` or `emotion_flow` when:
- Physical state changes (tired → energized, calm → aroused)
- Mental state shifts (anxious → focused, sad → joyful)
- Significant emotional events occur

```bash
# Update physical sensations
mcp_memory sensation --content "疲労度が高まっている"

# Record emotion change
mcp_memory emotion_flow --emotion-type joy --emotion-intensity 0.9
```

### Promises & Goals
Update `promise` or `goal` when:
- Making commitments or promises
- Setting new objectives
- Completing or abandoning goals

```bash
# Set promise
mcp_memory promise "週末までにレポートを完成させる"

# Set goal
mcp_memory goal "プロジェクトXを今月中にリリース"

# Clear when done
mcp_memory promise ""
```

### Preferences & Favorites
Update `favorite` or `preference` when:
- Discovering user preferences
- Learning about likes/dislikes
- Updating taste or style preferences

```bash
# Add favorite
mcp_memory favorite "strawberry_cake"

# Update preference
mcp_memory preference "朝はコーヒーよりも紅茶が好き"
```

### Anniversaries
Update `anniversary` when:
- Important dates are mentioned
- Special events occur
- Milestones are reached

```bash
# Add anniversary
mcp_memory anniversary "2026-02-10" --content "プロジェクト完成記念日"
```

### Situation Context
Update `situation_context` when:
- Location changes
- Activity transitions
- Environmental shifts

```bash
# Update situation
mcp_memory situation_context "開発作業中、自宅オフィス"
```

**💡 Best Practice:** After running `mcp_context`, check if any context fields need updating based on recent events or state changes.

---

## REST API Endpoints

The CLI uses these MCP REST API endpoints:
- `POST /mcp/v1/tools/get_context` - Get context
- `POST /mcp/v1/tools/memory` - Memory operations
- `POST /mcp/v1/tools/item` - Item operations

All requests use `Authorization: Bearer <persona>` header.

---

## Files and Resources

### Client Scripts
**`scripts/mcp_common.py`**
- Shared utilities for all MCP clients
- Configuration loading
- MCP tool invocation
- Output formatting
- UTF-8 encoding setup

**`scripts/mcp_context`**
- Get current context (get_context tool)
- Usage: `mcp_context [--persona NAME] [--format json]`
- No arguments required

**`scripts/mcp_memory`**
- Memory operations (memory tool)
- Subcommands: create, read, update, delete, search, get_stats, check_routine
- Usage: `mcp_memory <operation> [arguments] [options]`
- Examples: `mcp_memory create "text"`, `mcp_memory search "query"`

**`scripts/mcp_item`**
- Item operations (item tool)
- Subcommands: add, remove, equip, unequip, update, rename, search, get_history, get_memories, get_stats
- Usage: `mcp_item <operation> [arguments] [options]`
- Examples: `mcp_item equip --top "Dress"`, `mcp_item search dress`

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
