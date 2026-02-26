# Memory Features

This document describes the advanced memory management features.

---

## Ebbinghaus Forgetting Curve

Memories decay over time according to the [Ebbinghaus forgetting curve](https://en.wikipedia.org/wiki/Forgetting_curve):

```
R(t) = e^(-t / S)
```

| Variable | Description |
|----------|-------------|
| `R` | Retention (0.0–1.0) |
| `t` | Days since last access |
| `S` | Stability (grows on each recall) |

**Effective search score**: `strength = importance × R(t)`

### How it works

1. When a memory is created, its initial stability is set based on emotional charge:
   - `emotion_intensity > 0.7` → S = 10 (emotionally vivid, hard to forget)
   - `emotion_intensity > 0.5` → S = 5
   - otherwise → S = 1

2. Every 6 hours, a background worker recomputes `strength` for all memories.

3. When a memory is recalled (returned by search), its stability is multiplied by 1.5 (capped at 365 days), effectively resetting the decay clock. This models the "spacing effect."

4. Search ranking uses `strength` instead of raw `importance` when `importance_weight > 0`.

### Key columns

| Table | Column | Description |
|-------|--------|-------------|
| `memories` | `importance` | Immutable score set at creation |
| `memory_strength` | `strength` | Current effective score (decayed) |
| `memory_strength` | `stability` | Current stability factor |
| `memory_strength` | `last_decay_at` | Last time the decay worker ran |

---

## Bi-temporal User State Tracking

User information fields (`name`, `nickname`, `preferred_address`) are stored with full temporal history. Instead of overwriting values, each change is recorded with `valid_from` / `valid_until` timestamps.

### Schema

```sql
CREATE TABLE user_state_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    persona     TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    valid_from  TEXT NOT NULL,
    valid_until TEXT DEFAULT NULL,  -- NULL means "currently valid"
    created_at  TEXT NOT NULL
);
```

### Usage

```python
# Get current state
state = get_current_user_state("herta")
# → {"name": "らうらう", "nickname": "らう", ...}

# Full history for a key
history = get_user_state_history("herta", "name")
# → [{"value": "らうらう", "valid_from": "...", "valid_until": None, "is_current": True}, ...]
```

When `memory(operation="update_context", user_info={"name": "..."})` is called, the current record is invalidated and a new one is inserted atomically.

---

## Named Memory Blocks

Inspired by [Letta (MemGPT)](https://letta.com/), memory blocks are structured segments that are **always included in `get_context()` output** — unlike regular memories which require a search query.

Think of them as "RAM" for the AI: a small set of key facts always in working memory.

### Standard block names

| Name | Purpose |
|------|---------|
| `persona_state` | The persona's current internal state, mood, ongoing goals |
| `user_model` | What the persona knows/infers about the user |
| `active_context` | Current session focus, open questions, ongoing topics |

Custom block names are also allowed.

### Operations via `memory()` tool

```python
# Write a block
memory(operation="block_write", query="user_model",
       content="らうらうはmemory-mcpを開発中。Python好き。")

# Read a specific block
memory(operation="block_read", query="user_model")

# Read all blocks
memory(operation="block_read")

# List block names
memory(operation="block_list")

# Delete a block
memory(operation="block_delete", query="user_model")
```

### Schema

```sql
CREATE TABLE memory_blocks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    persona     TEXT NOT NULL,
    name        TEXT NOT NULL,
    content     TEXT NOT NULL,
    description TEXT DEFAULT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE(persona, name)
);
```
