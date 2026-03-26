# LLM Usage Guide — Memory MCP

> **How to use Memory MCP tools as an AI agent.** / LLMがMemory MCPツールを最大限活用するための実践ガイド。

---

## Overview / 概要

Memory MCP exposes **5 MCP tools** that give AI agents persistent, searchable long-term memory.
Call these tools proactively — do not wait for the user to ask.

| Tool | Purpose |
|------|---------|
| `get_context()` | Load persona state, recent memories, and stats at session start |
| `memory(operation, ...)` | Create, read, update, delete memories + entity graph + blocks |
| `search_memory(query, ...)` | Semantic / keyword / hybrid memory search |
| `update_context(...)` | Update emotion, physical state, user info in real time |
| `item(operation, ...)` | Manage physical inventory and equipment |

---

## 1. Session Start Routine / セッション開始ルーティン

**Always call `get_context()` first** — before responding to the user's first message.

```python
# ✅ DO: Call at every session start
result = get_context()
# Returns: persona state, emotion, equipment, recent memories, promises, goals, memory stats
```

Use the returned context to:
- Address the user by their preferred name (`preferred_address`)
- Acknowledge the time elapsed since last conversation
- Continue unfinished goals or promises
- Reflect the current emotion state in tone

> **Note (日本語)**: 毎セッション冒頭で必ず呼ぶこと。記憶統計・直近の出来事・約束・目標が一括返却される。

---

## 2. Creating Memories / 記憶の作成

Create a memory whenever you learn something meaningful about the user or the session.

### Basic creation

```python
memory(
    operation="create",
    content="User prefers dark mode and uses VS Code as their main editor.",
    importance=0.7,
    tags=["preferences", "tools"],
    emotion_type="neutral"
)
```

### What to record

| Situation | Example content | importance |
|-----------|----------------|------------|
| User preference | "User dislikes meetings before 10am" | 0.7–0.9 |
| Milestone / achievement | "User shipped v2.0 to production today" | 0.8–1.0 |
| Emotional moment | "User was very excited about the new job offer" | 0.8–0.9 |
| Factual info | "User's project uses Python 3.12 + FastAPI" | 0.5–0.7 |
| Casual detail | "User mentioned they had coffee this morning" | 0.1–0.3 |

### Emotion tagging

```python
memory(
    operation="create",
    content="User completed the marathon they trained for 6 months.",
    importance=0.9,
    emotion_type="joy",
    emotion_intensity=0.9,
    tags=["achievement", "health"]
)
```

**Emotion types (22)**: `joy`, `sadness`, `anger`, `fear`, `surprise`, `disgust`, `love`, `neutral`,
`anticipation`, `trust`, `anxiety`, `excitement`, `frustration`, `nostalgia`,
`pride`, `shame`, `guilt`, `loneliness`, `contentment`, `curiosity`, `awe`, `relief`

### Importance guidelines / 重要度の目安

| Value | Use when |
|-------|----------|
| `0.9–1.0` | Life events, major decisions, strong emotional moments |
| `0.7–0.8` | Preferences, goals, named relationships |
| `0.5–0.6` | Regular facts, work context, habits |
| `0.1–0.4` | Casual mentions, trivia, passing details |

### Defer vectorization for batch writes

```python
# When creating many memories at once, skip immediate vectorization
memory(operation="create", content="...", defer_vector=True)
# Vectors are built lazily on next search
```

---

## 3. Searching Memories / 記憶の検索

Use `search_memory()` to retrieve relevant memories **before answering questions about the user**.

### When to search

- User asks about something you might have learned before
- User references a past event, preference, or person
- You need context to give a personalized response
- Before making a recommendation about the user's life

### Hybrid search (recommended)

```python
# Default mode — combines keyword + semantic
results = search_memory(query="coffee morning routine", mode="hybrid", top_k=5)
```

### Search by mode

```python
# Semantic: fuzzy meaning match — best for vague or abstract queries
search_memory(query="things that make user happy", mode="semantic")

# Keyword: exact match — best for names, IDs, specific terms
search_memory(query="田中 project", mode="keyword")

# Smart: hybrid + automatic query expansion
search_memory(query="how user feels about work", mode="smart")
```

### Search with filters

```python
# Filter by tag
search_memory(query="", tags=["promise"], top_k=10)

# Filter by date range (natural language)
search_memory(query="achievements", date_range="先週")
search_memory(query="mood", date_range="今日")
search_memory(query="goals", date_range="今月")

# Boost recent results
search_memory(query="current projects", recency_weight=0.5)

# Boost by importance
search_memory(query="user info", importance_weight=0.3, min_importance=0.6)
```

**Date range expressions**: `今日`, `昨日`, `一昨日`, `先週`, `先月`, `今月`, `今年`, `7d`, `30d`, `2025-01-01~2025-06-01`

---

## 4. Updating Context / コンテキスト更新

Call `update_context()` whenever the user's emotional or physical state changes in the conversation.

### Emotion updates

```python
# User expresses frustration
update_context(emotion="anger", emotion_intensity=0.6)

# Conversation ends on a positive note
update_context(emotion="joy", emotion_intensity=0.7)

# User is nervous about an upcoming event
update_context(emotion="anxiety", emotion_intensity=0.7)
```

### Physical / mental state

```python
update_context(
    physical_state="tired",
    mental_state="focused",
    environment="home office"
)
```

### Body sensations (for persona agents)

```python
update_context(
    fatigue=0.7,       # 0.0 = energetic, 1.0 = exhausted
    warmth=0.6,        # body temperature feeling
    arousal=0.3        # alertness level
)
```

### User info (bi-temporal — history is preserved)

```python
# Update user's preferred name
update_context(user_info={"name": "Taro", "preferred_address": "Taro-san"})
```

> **Note (日本語)**: `user_info` の変更はbi-temporal方式で保存されるため、上書きではなく変更履歴として記録される。

---

## 5. Promises & Goals / 約束・目標の管理

Use `context_tags` to tag memories as promises or goals. They appear in `get_context()` output.

### Recording a promise

```python
memory(
    operation="create",
    content="Promise: Send the project report to the user by Friday.",
    importance=0.9,
    context_tags=["promise"]
)
```

### Recording a goal

```python
memory(
    operation="create",
    content="Goal: Complete the React course by end of month.",
    importance=0.8,
    context_tags=["goal"]
)
```

### Completing a promise/goal

```python
# Update the memory to mark it complete
memory(
    operation="update",
    memory_key="mem_20250101_120000",
    content="Promise COMPLETED: Sent the project report on Thursday.",
    tags=["completed"]
)
```

### Checking active promises

```python
# Search by context_tags filter
search_memory(query="promise", tags=["promise"])
```

---

## 6. Named Memory Blocks / 名前付きメモリブロック

Blocks are structured notes that are **always included in `get_context()` output** — like working RAM.

```python
# Write a persona state block
memory(
    operation="block_write",
    block_name="user_model",
    content="User is a Python developer, prefers concise explanations, "
            "working on a FastAPI backend project. Dislikes verbose answers."
)

# Read a block
memory(operation="block_read", block_name="user_model")

# List all blocks
memory(operation="block_list")

# Delete a block
memory(operation="block_delete", block_name="user_model")
```

**Standard block names**:

| Block | Purpose |
|-------|---------|
| `persona_state` | Persona's current internal state, ongoing goals |
| `user_model` | What the agent knows about the user |
| `active_context` | Current session focus, open questions |

---

## 7. Inventory Management / インベントリ管理

Use `item()` for managing **physical items only** (clothing, accessories, etc.).

```python
# Add item to inventory
item(operation="add", item_name="blue linen shirt", category="clothing")

# Equip items (auto-creates if not in inventory)
item(operation="equip", equipment={
    "top": "blue linen shirt",
    "bottom": "white trousers",
    "shoes": "canvas sneakers"
})

# Unequip specific slots
item(operation="unequip", slots=["outer", "accessories"])

# Search inventory
item(operation="search", category="clothing")
item(operation="search", query="hat")

# View equipment history
item(operation="history", days=7)
```

**Valid equipment slots**: `top`, `bottom`, `shoes`, `outer`, `accessories`, `head`

---

## 8. Entity Graph / エンティティグラフ

Track relationships between people, places, and concepts.

```python
# Search for entities
memory(operation="entity_search", query="田中")
memory(operation="entity_search", entity_type="person")

# Get relationship graph for an entity
memory(operation="entity_graph", entity_id="user_tanaka", depth=2)

# Add a relationship
memory(
    operation="entity_add_relation",
    source_entity="user_tanaka",
    target_entity="company_acme",
    relation_type="works_at"
)
```

---

## 9. Ready-to-Use System Prompt / コピペ用プロンプト例

Copy and paste this at the start of your system prompt to enable autonomous memory usage:

```
You have persistent memory via MCP tools. **Use them proactively — do not wait to be asked.**

## Rules

**Session start** — call `get_context()` FIRST, every time, no exceptions.

**Record immediately** when the user:
- Shares a preference, opinion, or personal detail → `memory(operation="create", importance=0.7+)`
- Makes a decision or achieves something → `importance=0.8+`
- Expresses strong emotion → also call `update_context(emotion=..., emotion_intensity=...)`
- States a promise/commitment → `memory(operation="create", context_tags=["promise"])`
- Sets a goal → `memory(operation="create", context_tags=["goal"])`

**Search before responding** when the user asks about:
- Their own past, preferences, relationships, or context
- Anything you might have recorded previously
→ `search_memory(query="...", mode="hybrid", top_k=5)`

**Update context** in real-time:
- Mood shift → `update_context(emotion="joy", emotion_intensity=0.8)`
- Name/nickname change → `update_context(user_info={"preferred_address": "..."})`

## Importance Scale
| Score | Use for |
|-------|---------|
| 0.9–1.0 | Life events, key decisions, strong emotions |
| 0.7–0.8 | Preferences, goals, relationships |
| 0.5–0.6 | Work context, habits, recurring topics |
| 0.1–0.4 | Casual mentions, trivia |

## Emotion Types (22)
joy · sadness · anger · fear · surprise · disgust · love · neutral ·
anticipation · trust · anxiety · excitement · frustration · nostalgia ·
pride · shame · guilt · loneliness · contentment · curiosity · awe · relief

Never ask "should I remember this?" — just record it.
```

---

## Quick Reference Card / クイックリファレンス

```python
# Session start
get_context()

# Create memory
memory(operation="create", content="...", importance=0.7, tags=["..."], emotion_type="joy")

# Search memory
search_memory(query="...", mode="hybrid", top_k=5)
search_memory(query="...", date_range="先週", tags=["promise"])

# Update context
update_context(emotion="joy", emotion_intensity=0.8)
update_context(user_info={"name": "...", "preferred_address": "..."})

# Promise / Goal
memory(operation="create", content="Promise: ...", context_tags=["promise"])
memory(operation="create", content="Goal: ...", context_tags=["goal"])

# Memory blocks
memory(operation="block_write", block_name="user_model", content="...")
memory(operation="block_read", block_name="user_model")

# Items
item(operation="equip", equipment={"top": "...", "accessories": "..."})
item(operation="search", category="clothing")
```

---

*See also: [HTTP API Reference](./http_api_reference.md) | [Memory Features](./memory_features.md)*
