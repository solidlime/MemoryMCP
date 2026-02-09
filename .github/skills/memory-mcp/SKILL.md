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

### Using the Python CLI

```bash
# Get context (always run at session start)
python scripts/memory_mcp_client.py get_context

# Create a memory
python scripts/memory_mcp_client.py memory create \
  --content "User likes strawberries" \
  --importance 0.8 \
  --emotion_type joy

# Search memories
python scripts/memory_mcp_client.py memory search \
  --query "strawberries" \
  --mode semantic \
  --top_k 5

# Add and equip an item
python scripts/memory_mcp_client.py item add \
  --name "Red Dress" \
  --category clothing \
  --description "Elegant red evening dress"

python scripts/memory_mcp_client.py item equip --name "Red Dress"

# Get item statistics
python scripts/memory_mcp_client.py item stats
```

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

## Memory Operations

### Create Memory

```bash
python scripts/memory_mcp_client.py memory create \
  --content "Completed project milestone" \
  --importance 0.9 \
  --emotion_type accomplishment \
  --tags "work,achievement" \
  --context_tags "milestone" \
  --action_tag achievement
```

### Update Memory

```bash
python scripts/memory_mcp_client.py memory update \
  --key "memory_20260209_123000" \
  --content "Updated content" \
  --importance 0.95
```

### Search Memory

```bash
# Semantic search (default)
python scripts/memory_mcp_client.py memory search \
  --query "happy moments" \
  --mode semantic

# Keyword search
python scripts/memory_mcp_client.py memory search \
  --query "Python" \
  --mode keyword

# Hybrid search (semantic 70% + keyword 30%)
python scripts/memory_mcp_client.py memory search \
  --query "project" \
  --mode hybrid

# Time-filtered search
python scripts/memory_mcp_client.py memory search \
  --query "achievements" \
  --date_range "昨日"

# Smart search (auto query expansion)
python scripts/memory_mcp_client.py memory search \
  --query "いつものあれ" \
  --mode smart
```

### Check Routines

```bash
# Detect recurring patterns at current time
python scripts/memory_mcp_client.py memory check_routines
```

### Manage Anniversaries

```bash
# List all anniversaries
python scripts/memory_mcp_client.py memory anniversary

# Add anniversary
python scripts/memory_mcp_client.py memory create \
  --content "First movie together" \
  --emotion_type joy \
  --importance 0.9 \
  --context_tags "first_time,anniversary"

# Delete anniversary
python scripts/memory_mcp_client.py memory anniversary \
  --delete_key "memory_20260101_000000"
```

## Item Operations

### Add Items

```bash
python scripts/memory_mcp_client.py item add \
  --name "Blue Hat" \
  --category accessory \
  --description "Stylish blue hat" \
  --tags "casual,outdoor"
```

### Equip/Unequip

```bash
# Equip item
python scripts/memory_mcp_client.py item equip --name "Blue Hat"

# Unequip item
python scripts/memory_mcp_client.py item unequip --name "Blue Hat"
```

### Search Items

```bash
# Search all items
python scripts/memory_mcp_client.py item search

# Search by category
python scripts/memory_mcp_client.py item search --category clothing

# Search equipped items only
python scripts/memory_mcp_client.py item search --equipped True
```

### Item History & Memories

```bash
# Get equipment history
python scripts/memory_mcp_client.py item history

# Get memories associated with an item
python scripts/memory_mcp_client.py item memories --name "Red Dress"
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
