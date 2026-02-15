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
mcp_memory create "User prefers Python over JavaScript"
```

### Full Context Creation

```bash
mcp_memory create "Successfully deployed new feature" \
  --importance 0.9 \
  --emotion-type joy \
  --emotion-intensity 0.8 \
  --tags "work,achievement,milestone" \
  --action_tag achievement \
  --physical_state "energized" \
  --mental_state "accomplished" \
  --environment "home office"
```

### Anniversary/Milestone Creation

**Recommended approach** for creating anniversaries and milestones:

```bash
# Special commemorative date
mcp_memory create "初めて会った日 - 忘れられない特別な日" \
  --tags "anniversary" \
  --importance 0.9 \
  --emotion-type "gratitude"

# Important achievement
mcp_memory create "プロジェクト完成 - 大きな達成" \
  --tags "milestone" \
  --importance 0.8 \
  --emotion-type "joy"

# First time experience
mcp_memory create "初めての○○ - 特別な体験" \
  --tags "first_time" \
  --importance 0.7
```

**Anniversary Tags:**
- `anniversary`: Special commemorative dates (first meeting, relationship milestones)
- `milestone`: Important achievements or life events
- `first_time`: First time experiences worth remembering

### Privacy Control

```bash
mcp_memory create "API key for production server" \
  --privacy-level secret \
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
mcp_memory read "memory_20260210_123000"
```

### Read Recent Memories

```bash
# Default: 10 most recent
mcp_memory read

# Custom count
mcp_memory read --limit 20
```

**Parameters:**
- `query`: Memory key (optional)
- `top_k`: Number of recent memories to return (default: 10)

---

## Update Memory

Update existing memory content and/or metadata.

### Update Content

```bash
mcp_memory update "memory_20260210_123000" \
  "Updated content with more details"
```

### Update Importance

```bash
mcp_memory update "memory_20260210_123000" \
  --importance 0.95
```

### Full Update

```bash
mcp_memory update "memory_20260210_123000" \
  "Revised content" \
  --importance 0.9 \
  --emotion-type pride \
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
mcp_memory delete "memory_20260210_123000"
```

**Parameters:**
- `query`: Memory key to delete (required)

**Warning:** Deletion is permanent and cannot be undone.

---

## Search Memory

Search memories using various modes and filters.

### Semantic Search (Default)

```bash
mcp_memory search "happy moments with friends" \
  --mode semantic \
  --limit 5
```

### Keyword Search

```bash
mcp_memory search "Python coding" \
  --mode keyword \
  --limit 10
```

### Hybrid Search (Semantic + Keyword with RRF)

Reciprocal Rank Fusion (RRF) merges semantic and keyword search results intelligently.

```bash
mcp_memory search "project deployment" \
  --mode hybrid \
  --limit 5
```

**How RRF Works:**
- Runs semantic and keyword searches in parallel
- Merges results using rank-based scoring: `score = Σ 1/(k + rank)`
- Automatically deduplicates and sorts by combined relevance
- Lightweight (no ML overhead, no external API calls)

### Related Memories (Similar to Specific Memory)

```bash
mcp_memory search "memory_20260210_123000" \
  --mode related \
  --limit 5
```

### Smart Search (Auto Query Expansion)

```bash
mcp_memory search "いつものあれ" \
  --mode smart \
  --limit 10
```

**Search Modes:**

| Mode | Description | Use Case |
|------|-------------|----------|
| `semantic` | Vector similarity search | Conceptual queries, natural language |
| `keyword` | Exact text matching | Specific terms, names, IDs |
| `hybrid` | RRF fusion (semantic + keyword) | Most queries, balanced precision+recall |
| `related` | Find similar to given memory | "More like this" |
| `smart` | Auto-expand ambiguous queries | Vague or colloquial queries |

### Advanced Filters

#### Tag Filtering

```bash
# Any tag match (OR)
mcp_memory search "achievements" \
  --search-tags "work,personal" \
  --tag-match-mode any

# All tags match (AND)
mcp_memory search "achievements" \
  --search-tags "work,milestone" \
  --tag-match-mode all
```

#### Time-based Filtering

```bash
# Recent memories (natural language)
mcp_memory search "meetings" \
  --date-range "過去1週間"

# Specific date range
mcp_memory search "work" \
  --date-range "2026-02-01 to 2026-02-07"
```

**Natural Language Date Ranges:**
- `今日`, `昨日`, `今週`, `先週`
- `過去3日間`, `過去1週間`, `過去1ヶ月`

#### Importance Filtering

```bash
mcp_memory search "important events" \
  --min-importance 0.8
```

#### Equipment Filtering

```bash
# Memories associated with equipped item
mcp_memory search "outdoor activities" \
  --equipped-item "White Dress"
```

#### Fuzzy Matching

```bash
mcp_memory search "Pythn" \
  --mode keyword \
  --fuzzy-match true \
  --fuzzy-threshold 80
```

**Parameters:**
- `fuzzy_match`: Enable fuzzy matching (default: false)
- `fuzzy_threshold`: Match threshold 0-100 (default: 70)

### Ranking Weights

Customize result ranking with importance and recency weights:

```bash
mcp_memory search "project work" \
  --importance-weight 0.3 \
  --recency-weight 0.2
```

**Parameters:**
- `importance_weight`: Boost important memories (0.0-1.0)
- `recency_weight`: Boost recent memories (0.0-1.0)

**Note:** Weights are added to similarity score.

---

## Memory Statistics

Get comprehensive memory statistics.

```bash
mcp_memory stats
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
mcp_memory check_routines
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
mcp_memory create "User mentioned preferring dark theme"

# Important note
mcp_memory create "Deadline: Project due Friday" \
  --importance 0.9 \
  --tags "deadline,urgent"
```

### Emotional Journaling

```bash
mcp_memory create "Had a great conversation with the team" \
  --emotion-type joy \
  --emotion-intensity 0.8 \
  --tags "social,work" \
  --importance 0.7
```

### Knowledge Base Building

```bash
# Add fact
mcp_memory create "FastAPI uses Pydantic for data validation" \
  --tags "fastapi,python,knowledge" \
  --importance 0.6

# Search knowledge
mcp_memory search "how does FastAPI validate data" \
  --search-tags "knowledge" \
  --mode semantic
```

### Meeting Notes

```bash
mcp_memory create "Team meeting: Decided to use PostgreSQL for production database" \
  --tags "meeting,decision,database,team,production" \
  --importance 0.8 \
  --action_tag decision
```

---

## Performance Considerations

### Bulk Import

When importing many memories, use `defer_vector=true`:

```bash
for content in "${memories[@]}"; do
  mcp_memory create "$content" \
    --defer-vector true
done

# Rebuild vector store afterward
# (Use admin tools or dashboard)
```

### Search Optimization

- Use `keyword` mode for exact matches (fastest)
- Use `hybrid` mode (RRF) for general queries (balanced precision+recall)
- Use `semantic` mode for concept queries (slowest, most accurate)
- Limit `top_k` to needed results (default: 5-10)

---

## See Also

- [Context Operations](./context_operations.md) - Context and state management
- [SKILL.md](../SKILL.md) - Main skill documentation
- [Item Operations](./item_operations.md) - Item and equipment management
