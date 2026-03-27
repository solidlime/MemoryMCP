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

Promises and goals are stored as **persona state** via `update_context(persona_info=...)`.
They appear in the **ACTIVE COMMITMENTS** section of `get_context()` output.

> **⚠️ Important**: `context_tags=["promise"]` / `context_tags=["goal"]` is **not a valid feature**.
> Do **not** use `context_tags` for promise or goal tracking — use `update_context(persona_info=...)` instead.
> (`context_tags` is a reserved parameter in the `memory()` tool for future use, but has no promise/goal effect.)

### Registering promises and goals

```python
# Register promises and goals
# ⚠️ This OVERWRITES the existing list — see "Appending" below if you need to add
update_context(persona_info={
    "promises": ["Send the project report by Friday"],
    "goals": ["Complete the React course by end of month"]
})
```

### Appending to existing promises/goals

```python
# Step 1: Read current state
ctx = get_context()  # check the ACTIVE COMMITMENTS section for existing entries

# Step 2: Merge existing + new entries and write back
update_context(persona_info={
    "promises": ["Send the project report by Friday", "Follow up on Monday"],  # existing + new
    "goals": ["Complete the React course by end of month", "Finish the side project"]
})
```

### Clearing completed promises/goals

```python
# Clear all promises and goals
update_context(persona_info={"promises": [], "goals": []})

# Clear only promises (goals remain unchanged)
update_context(persona_info={"promises": []})
```

### Checking active promises/goals

```python
# Returns the ACTIVE COMMITMENTS section listing all current promises and goals
get_context()
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

Use `item()` for managing **the LLM/persona's own physical items** (clothing, accessories, etc.).
This tool tracks what **the assistant itself** wears and carries — not the user's belongings.

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
You have persistent memory via MCP tools. Use them autonomously — never wait to be asked.

**Every session:** call `get_context()` first, no exceptions.

**Record** when user shares preferences/decisions/emotions/achievements:
→ `memory(operation="create", content="...", importance=0.7, tags=[...], emotion_type="joy")`
→ Promise/Goal: `update_context(persona_info={"promises": ["..."], "goals": ["..."]})`
  (overwrites — call `get_context()` first if you need to append)

**Search** before answering anything about user's past/preferences:
→ `search_memory(query="...", mode="hybrid", top_k=5)`

**Update live** on mood/name change:
→ `update_context(emotion="anxiety", emotion_intensity=0.7)`
→ `update_context(user_info={"preferred_address": "..."})`

**Track persona items** (the assistant's own equipment):
→ `item(operation="equip", equipment={"top": "...", "accessories": "..."})`
→ `item(operation="add", item_name="...", category="clothing")`

Importance: 0.9+ life events · 0.7 preferences · 0.5 context · 0.2 trivia
Emotions: joy sadness anger fear surprise disgust love neutral anticipation trust anxiety excitement frustration nostalgia pride shame guilt loneliness contentment curiosity awe relief

Never ask "should I remember this?" — just do it.
```

### 日本語版

```
あなたはMCPツールで永続的な記憶を持っています。自律的に使ってください — 指示を待つ必要はありません。

**毎セッション開始時:** 例外なく最初に `get_context()` を呼ぶ。

**記録する** — ユーザーが以下を伝えたとき:
→ 好み・意見・個人情報 → `memory(operation="create", content="...", importance=0.7, tags=[...])`
→ 決断・達成・感情的な出来事 → `importance=0.8+`、感情は `emotion_type="joy"` で指定
→ 約束・目標 → `update_context(persona_info={"promises": ["..."], "goals": ["..."]})`
  （上書き型 — 追加する場合は先に `get_context()` で既存リストを確認してから渡す）

**検索する** — ユーザーの過去・好み・文脈に関する質問に答える前に:
→ `search_memory(query="...", mode="hybrid", top_k=5)`

**リアルタイム更新** — 感情変化・名前変更があったとき:
→ `update_context(emotion="anxiety", emotion_intensity=0.7)`
→ `update_context(user_info={"preferred_address": "..."})`

**所持品・装備を記録** — 自分自身の持ち物・着ているものが変わったとき:
→ `item(operation="equip", equipment={"top": "...", "accessories": "..."})`
→ `item(operation="add", item_name="...", category="clothing")`

重要度: 0.9+ 人生の出来事 · 0.7 好み · 0.5 文脈 · 0.2 雑談
感情: joy sadness anger fear surprise disgust love neutral anticipation trust anxiety excitement frustration nostalgia pride shame guilt loneliness contentment curiosity awe relief

「覚えておきましょうか？」と聞かない — 重要だと思ったらすぐ記録する。
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

# Promise / Goal  ← uses update_context, NOT memory() context_tags
update_context(persona_info={"promises": ["..."]})           # set promises (overwrites existing)
update_context(persona_info={"goals": ["..."]})              # set goals (overwrites existing)
update_context(persona_info={"promises": ["..."], "goals": ["..."]})  # set both at once
# → call get_context() first if you need to append rather than overwrite
# → appears in get_context() ACTIVE COMMITMENTS section

# Memory blocks
memory(operation="block_write", block_name="user_model", content="...")
memory(operation="block_read", block_name="user_model")

# Items
item(operation="equip", equipment={"top": "...", "accessories": "..."})
item(operation="search", category="clothing")
```

---

*See also: [HTTP API Reference](./http_api_reference.md) | [Memory Features](./memory_features.md)*
