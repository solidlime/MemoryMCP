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
- `create`: Create new memory
- `update`: Update existing memory
- `delete`: Delete memory
- `search`: Search memories (semantic/keyword/hybrid/related/smart)
- `stats`: Get memory statistics
- `check_routines`: Detect recurring patterns
- `anniversary`: Manage anniversaries

### 3. item
Unified item operations:
- `add`: Add item to inventory
- `remove`: Remove item
- `equip`: Equip item
- `unequip`: Unequip item
- `update`: Update item details
- `search`: Search inventory
- `history`: Get equipment history
- `memories`: Get memories associated with item
- `stats`: Get item statistics

## Quick Start

```bash
# Script path: {skill_root}/scripts/memory_mcp_client.py
# Get context (always run at session start)
python <skill_root>/scripts/memory_mcp_client.py get_context

# Create a memory
python <skill_root>/scripts/memory_mcp_client.py memory create \
  --content "User likes strawberries" \
  --importance 0.8 \
  --emotion_type joy

# Search memories
python <skill_root>/scripts/memory_mcp_client.py memory search \
  --query "strawberries" \
  --mode semantic \
  --top_k 5

# Add and equip an item
python <skill_root>/scripts/memory_mcp_client.py item add \
  --name "Red Dress" \
  --category clothing \
  --description "Elegant red evening dress"

python <skill_root>/scripts/memory_mcp_client.py item equip --slot top --name "Red Dress"

# Equip multiple items at once
python <skill_root>/scripts/memory_mcp_client.py item equip \
  --equipment '{"top": "White Dress", "foot": "Sandals"}'

# Unequip a single slot
python <skill_root>/scripts/memory_mcp_client.py item unequip --slot top

# Unequip multiple slots
python <skill_root>/scripts/memory_mcp_client.py item unequip --slots top,foot

# Get item statistics
python <skill_root>/scripts/memory_mcp_client.py item stats
```

**Note:** Python client fully supports UTF-8 across all platforms (Windows/Linux/Mac) with automatic console encoding configuration.

### Common Options

All commands support these options:
- `--persona`: Persona name (default: from config.json)
- `--url`: MCP server URL (default: from config.json)
- `--format`: Output format (`text` or `json`)

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
- `paths.skill_root`: Absolute path to skill root directory (client script: `{skill_root}/scripts/memory_mcp_client.py`)
- `settings.auto_get_context_on_session_start`: Auto-call on session start

## Memory Operations

### Create Memory

```bash
python <skill_root>/scripts/memory_mcp_client.py memory create \
  --content "Completed project milestone" \
  --importance 0.9 \
  --emotion_type accomplishment \
  --tags "work,achievement" \
  --context_tags "milestone" \
  --action_tag achievement
```

### Update Memory

```bash
python <skill_root>/scripts/memory_mcp_client.py memory update \
  --key "memory_20260209_123000" \
  --content "Updated content" \
  --importance 0.95
```

### Search Memory

```bash
# Semantic search (default)
python <skill_root>/scripts/memory_mcp_client.py memory search \
  --query "happy moments" \
  --mode semantic

# Keyword search
python <skill_root>/scripts/memory_mcp_client.py memory search \
  --query "Python" \
  --mode keyword

# Hybrid search (semantic 70% + keyword 30%)
python <skill_root>/scripts/memory_mcp_client.py memory search \
  --query "project" \
  --mode hybrid

# Time-filtered search
python <skill_root>/scripts/memory_mcp_client.py memory search \
  --query "achievements" \
  --date_range "昨日"

# Smart search (auto query expansion)
python <skill_root>/scripts/memory_mcp_client.py memory search \
  --query "いつものあれ" \
  --mode smart
```

### Check Routines

```bash
# Detect recurring patterns at current time
python <skill_root>/scripts/memory_mcp_client.py memory check_routines
```

### Manage Anniversaries

```bash
# List all anniversaries
python <skill_root>/scripts/memory_mcp_client.py memory anniversary

# Add anniversary
python <skill_root>/scripts/memory_mcp_client.py memory create \
  --content "First movie together" \
  --emotion_type joy \
  --importance 0.9 \
  --context_tags "first_time,anniversary"

# Delete anniversary
python <skill_root>/scripts/memory_mcp_client.py memory anniversary \
  --delete_key "memory_20260101_000000"
```

## Item Operations

### Add Items

```bash
python <skill_root>/scripts/memory_mcp_client.py item add \
  --name "Blue Hat" \
  --category accessory \
  --description "Stylish blue hat" \
  --tags "casual,outdoor"
```

### Equip/Unequip

```bash
# Equip single item to a slot
python <skill_root>/scripts/memory_mcp_client.py item equip --slot accessory --name "Blue Hat"

# Equip multiple items at once
python <skill_root>/scripts/memory_mcp_client.py item equip \
  --equipment '{"top": "White Dress", "accessory": "Blue Hat", "foot": "Sandals"}'

# Unequip a single slot
python <skill_root>/scripts/memory_mcp_client.py item unequip --slot accessory

# Unequip multiple slots
python <skill_root>/scripts/memory_mcp_client.py item unequip --slots top,foot,accessory
```

### Search Items

```bash
# Search all items
python <skill_root>/scripts/memory_mcp_client.py item search

# Search by category
python <skill_root>/scripts/memory_mcp_client.py item search --category clothing

# Search equipped items only
python <skill_root>/scripts/memory_mcp_client.py item search --equipped True
```

### Item History & Memories

```bash
# Get equipment history
python <skill_root>/scripts/memory_mcp_client.py item history

# Get memories associated with an item
python <skill_root>/scripts/memory_mcp_client.py item memories --name "Red Dress"
```

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

## Resources

### scripts/memory_mcp_client.py
Unified CLI client for all MCP tools.

**Features:**
- All 3 MCP tools (get_context, memory, item)
- Comprehensive operation support
- JSON and text output formats
- Configuration file support
- Error handling and retries

### references/config.json
Configuration file for MCP server connection and persona settings.

**Customization:**
- Update `mcp_server.url` for different server endpoints
- Change `persona.default` for different personas
- Adjust timeout and retry settings as needed
