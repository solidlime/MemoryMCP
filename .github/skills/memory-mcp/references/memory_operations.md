# Memory Operations Reference

Core CRUD (Create, Read, Update, Delete) and search operations for the memory system.

## Overview

Memory operations use the unified `memory` tool with different operation types. All memories are stored in SQLite with vector embeddings for semantic search.

**Available Operations:**
- `create` - Create new memory
- `read` - Retrieve memory by key or recent memories
- `update` - Update existing memory
- `delete` - Delete memory
- `search` - Search memories (semantic/keyword/hybrid/related/smart)
- `stats` - Get memory statistics
- `check_routines` - Detect recurring patterns

---

## Create Memory

Create a new memory entry with optional context and metadata.

### Basic Creation

```bash
python scripts/memory_mcp_client.py memory create \
  --content "User prefers Python over JavaScript"
```

### Full Context Creation

```bash
python scripts/memory_mcp_client.py memory create \
  --content "Successfully deployed new feature" \
  --importance 0.9 \
  --emotion_type joy \
  --emotion_intensity 0.8 \
  --tags "work,achievement" \
  --context_tags "milestone" \
  --action_tag achievement \
  --physical_state "energized" \
  --mental_state "accomplished" \
  --environment "home office"
```

### Privacy Control

```bash
python scripts/memory_mcp_client.py memory create \
  --content "API key for production server" \
  --privacy_level secret \
  --importance 1.0
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | string | *required* | Memory content |
| `importance` | float | 0.5 | Importance score (0.0-1.0) |
| `emotion_type` | string | null | Emotion type (joy, sadness, etc.) |
| `emotion_intensity` | float | null | Emotion intensity (0.0-1.0) |
| `tags` | list[string] | [] | Tags for categorization |
| `context_tags` | list[string] | [] | Contextual tags |
| `action_tag` | string | null | Action category tag |
| `physical_state` | string | null | Physical condition |
| `mental_state` | string | null | Mental/emotional state |
| `environment` | string | null | Current environment |
| `privacy_level` | string | "internal" | Privacy level (see below) |
| `defer_vector` | bool | false | Skip vector indexing |

**Privacy Levels:**
- `public`: Shareable externally
- `internal`: Default, normal use
- `private`: Personal, sensitive
- `secret`: Highly confidential

**Performance Option:**
- `defer_vector=true`: Creates memory without immediate vector indexing (faster bulk imports)

---

## Read Memory

Retrieve memories by key or get recent memories.

### Read by Key

```bash
python scripts/memory_mcp_client.py memory read \
  --query "memory_20260210_123000"
```

### Read Recent Memories

```bash
# Default: 10 most recent
python scripts/memory_mcp_client.py memory read

# Custom count
python scripts/memory_mcp_client.py memory read --top_k 20
```

**Parameters:**
- `query`: Memory key (optional)
- `top_k`: Number of recent memories to return (default: 10)

---

## Update Memory

Update existing memory content and/or metadata.

### Update Content

```bash
python scripts/memory_mcp_client.py memory update \
  --memory_key "memory_20260210_123000" \
  --content "Updated content with more details"
```

### Update Importance

```bash
python scripts/memory_mcp_client.py memory update \
  --memory_key "memory_20260210_123000" \
  --importance 0.95
```

### Full Update

```bash
python scripts/memory_mcp_client.py memory update \
  --memory_key "memory_20260210_123000" \
  --content "Revised content" \
  --importance 0.9 \
  --emotion_type pride \
  --tags "updated,important"
```

**Parameters:**
- `memory_key`: Memory key to update (required)
- `content`: New content (optional)
- `importance`: New importance (optional)
- `emotion_type`: New emotion (optional)
- All creation parameters are available

**Note:** Vector embedding is automatically updated when content changes.

---

## Delete Memory

Remove memory from database and vector store.

```bash
python scripts/memory_mcp_client.py memory delete \
  --query "memory_20260210_123000"
```

**Parameters:**
- `query`: Memory key to delete (required)

**Warning:** Deletion is permanent and cannot be undone.

---

## Search Memory

Search memories using various modes and filters.

### Semantic Search (Default)

```bash
python scripts/memory_mcp_client.py memory search \
  --query "happy moments with friends" \
  --mode semantic \
  --top_k 5
```

### Keyword Search

```bash
python scripts/memory_mcp_client.py memory search \
  --query "Python coding" \
  --mode keyword \
  --top_k 10
```

### Hybrid Search (Semantic + Keyword)

```bash
python scripts/memory_mcp_client.py memory search \
  --query "project deployment" \
  --mode hybrid \
  --top_k 5
```

### Related Memories (Similar to Specific Memory)

```bash
python scripts/memory_mcp_client.py memory search \
  --query "memory_20260210_123000" \
  --mode related \
  --top_k 5
```

### Smart Search (Auto Query Expansion)

```bash
python scripts/memory_mcp_client.py memory search \
  --query "いつものあれ" \
  --mode smart \
  --top_k 10
```

**Search Modes:**

| Mode | Description | Use Case |
|------|-------------|----------|
| `semantic` | Vector similarity search | Conceptual queries, natural language |
| `keyword` | Exact text matching | Specific terms, names, IDs |
| `hybrid` | 70% semantic + 30% keyword | Balanced, most queries |
| `related` | Find similar to given memory | "More like this" |
| `smart` | Auto-expand ambiguous queries | Vague or colloquial queries |

### Advanced Filters

#### Tag Filtering

```bash
# Any tag match (OR)
python scripts/memory_mcp_client.py memory search \
  --query "achievements" \
  --search_tags "work,personal" \
  --tag_match_mode any

# All tags match (AND)
python scripts/memory_mcp_client.py memory search \
  --query "achievements" \
  --search_tags "work,milestone" \
  --tag_match_mode all
```

#### Time-based Filtering

```bash
# Recent memories (natural language)
python scripts/memory_mcp_client.py memory search \
  --query "meetings" \
  --date_range "過去1週間"

# Specific date range
python scripts/memory_mcp_client.py memory search \
  --query "work" \
  --date_range "2026-02-01 to 2026-02-07"
```

**Natural Language Date Ranges:**
- `今日`, `昨日`, `今週`, `先週`
- `過去3日間`, `過去1週間`, `過去1ヶ月`

#### Importance Filtering

```bash
python scripts/memory_mcp_client.py memory search \
  --query "important events" \
  --min_importance 0.8
```

#### Equipment Filtering

```bash
# Memories associated with equipped item
python scripts/memory_mcp_client.py memory search \
  --query "outdoor activities" \
  --equipped_item "White Dress"
```

#### Fuzzy Matching

```bash
python scripts/memory_mcp_client.py memory search \
  --query "Pythn" \
  --mode keyword \
  --fuzzy_match true \
  --fuzzy_threshold 80
```

**Parameters:**
- `fuzzy_match`: Enable fuzzy matching (default: false)
- `fuzzy_threshold`: Match threshold 0-100 (default: 70)

### Ranking Weights

Customize result ranking with importance and recency weights:

```bash
python scripts/memory_mcp_client.py memory search \
  --query "project work" \
  --importance_weight 0.3 \
  --recency_weight 0.2
```

**Parameters:**
- `importance_weight`: Boost important memories (0.0-1.0)
- `recency_weight`: Boost recent memories (0.0-1.0)

**Note:** Weights are added to similarity score.

---

## Memory Statistics

Get comprehensive memory statistics.

```bash
python scripts/memory_mcp_client.py memory stats
```

**Returns:**
- Total memory count
- Memory count per day/week/month
- Average importance
- Most common tags
- Emotion distribution
- Privacy level distribution
- Vector store metrics

---

## Check Routines

Detect recurring patterns at the current time.

```bash
python scripts/memory_mcp_client.py memory check_routines
```

**How it works:**
- Analyzes memories from the same time window (±2 hours) across different days
- Returns memories that suggest routine activities
- Useful for reminder systems and habit tracking

**Example Output:**
```
🔄 Routine detected:
- 08:00-10:00: Morning coffee and planning (5 occurrences)
- 14:00-16:00: Code review session (3 occurrences)
```

---

## Common Patterns

### Quick Note Taking

```bash
# Simple note
python scripts/memory_mcp_client.py memory create \
  --content "User mentioned preferring dark theme"

# Important note
python scripts/memory_mcp_client.py memory create \
  --content "Deadline: Project due Friday" \
  --importance 0.9 \
  --tags "deadline,urgent"
```

### Emotional Journaling

```bash
python scripts/memory_mcp_client.py memory create \
  --content "Had a great conversation with the team" \
  --emotion_type joy \
  --emotion_intensity 0.8 \
  --tags "social,work" \
  --importance 0.7
```

### Knowledge Base Building

```bash
# Add fact
python scripts/memory_mcp_client.py memory create \
  --content "FastAPI uses Pydantic for data validation" \
  --tags "fastapi,python,knowledge" \
  --importance 0.6

# Search knowledge
python scripts/memory_mcp_client.py memory search \
  --query "how does FastAPI validate data" \
  --search_tags "knowledge" \
  --mode semantic
```

### Meeting Notes

```bash
python scripts/memory_mcp_client.py memory create \
  --content "Team meeting: Decided to use PostgreSQL for production database" \
  --tags "meeting,decision,database" \
  --context_tags "team,production" \
  --importance 0.8 \
  --action_tag decision
```

---

## Performance Considerations

### Bulk Import

When importing many memories, use `defer_vector=true`:

```bash
for content in "${memories[@]}"; do
  python scripts/memory_mcp_client.py memory create \
    --content "$content" \
    --defer_vector true
done

# Rebuild vector store afterward
# (Use admin tools or dashboard)
```

### Search Optimization

- Use `keyword` mode for exact matches (fastest)
- Use `hybrid` mode for general queries (balanced)
- Use `semantic` mode for concept queries (slowest, most accurate)
- Limit `top_k` to needed results (default: 5-10)

---

## See Also

- [Context Operations](./context_operations.md) - Context and state management
- [SKILL.md](../SKILL.md) - Main skill documentation
- [Item Operations](./item_operations.md) - Item and equipment management
