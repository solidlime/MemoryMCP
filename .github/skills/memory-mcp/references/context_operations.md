# Context Operations Reference

Context operations manage the persona's current state, relationships, goals, and preferences through the unified `memory` tool.

## Overview

Context operations use the same `memory` tool with different operation types. These operations update the persona's context file (`persona_context.json`) in real-time.

**Available Operations:**
- `promise` - Update/clear active promise
- `goal` - Update/clear current goal
- `favorite` - Add to favorites
- `preference` - Update preferences
- `anniversary` - Manage anniversaries
- `sensation` - Update physical sensations
- `emotion_flow` - Record emotion changes
- `situation_context` - Analyze current situation
- `update_context` - Batch update multiple fields

---

## Promise Operations

Manage active promises or commitments.

### Set Promise

```bash
mcp_memory promise "週末に買い物に行く約束"
```

**Parameters:**
- `content`: Promise text (required)

### Clear Promise

```bash
mcp_memory promise ""
```

---

## Goal Operations

Set or clear the current goal.

### Set Goal

```bash
mcp_memory goal "プロジェクトを今週中に完成させる"
```

### Clear Goal

```bash
mcp_memory goal ""
```

---

## Favorite Operations

Add items to the favorites list.

### Add Favorite

```bash
mcp_memory favorite "strawberry_cake"
```

**Parameters:**
- `content`: Favorite item name (required)

**Notes:**
- Items are automatically deduplicated
- Existing favorites are preserved

---

## Preference Operations

Update persona preferences.

### Set Preference

```bash
mcp_memory preference "music" \
  --persona-info '{"value": "classical, jazz"}'
```

**Parameters:**
- `content`: Preference key (required)
- `persona_info.value`: Preference value (required)

**Example Preferences:**
- `music`: "classical, jazz"
- `food`: "Italian, Japanese"
- `color`: "blue, white"
- `activity`: "reading, dancing"

---

## Anniversary Operations

Manage important dates and anniversaries.

### Add Anniversary

```bash
mcp_memory anniversary "結婚記念日" \
  --persona-info '{"date": "2025-11-10"}'
```

**Parameters:**
- `content`: Anniversary description (required)
- `persona_info.date`: Date in YYYY-MM-DD format (required)

### List Anniversaries

```bash
mcp_memory anniversary
```

### Delete Anniversary

```bash
mcp_memory anniversary \
  --persona-info '{"delete_key": "memory_20260101_000000"}'
```

**Parameters:**
- `persona_info.delete_key`: Memory key to delete (required)

---

## Sensation Operations

Update physical sensations or body state.

### Record Sensation

```bash
mcp_memory sensation "温かい風を感じる"
```

**Parameters:**
- `content`: Sensation description (required)

**Common Sensations:**
- Temperature: "暖かい", "寒い", "涼しい"
- Touch: "柔らかい", "硬い", "滑らか"
- Physical state: "疲れている", "リラックスしている"

---

## Emotion Flow Operations

Record emotion changes over time.

### Record Emotion Change

```bash
mcp_memory emotion_flow "プロジェクト完成で嬉しい" \
  --emotion-type joy \
  --emotion-intensity 0.8
```

**Parameters:**
- `emotion_type`: Emotion type (joy, sadness, anger, fear, etc.)
- `emotion_intensity`: 0.0-1.0 intensity level
- `content`: Context or reason for emotion

**Emotion Types:**
- Positive: `joy`, `excitement`, `pride`, `gratitude`
- Neutral: `calm`, `neutral`, `thoughtful`
- Negative: `sadness`, `anger`, `fear`, `frustration`

---

## Situation Context Operations

Analyze and record the current situation.

### Analyze Situation

```bash
mcp_memory situation_context "深夜のコーディングセッション中" \
  --environment "quiet office" \
  --physical_state "focused" \
  --mental_state "concentrated"
```

**Parameters:**
- `content`: Situation description
- `environment`: Current environment
- `physical_state`: Physical condition
- `mental_state`: Mental/emotional state

---

## Batch Context Update

Update multiple context fields simultaneously.

### Batch Update

```bash
mcp_memory update_context \
  --physical_state "energetic" \
  --mental_state "creative" \
  --environment "sunny park" \
  --relationship_status "happy"
```

**Updatable Fields:**
- `physical_state`: Physical condition
- `mental_state`: Mental/emotional state
- `environment`: Current surroundings
- `relationship_status`: Relationship state
- Any custom context fields

---

## Integration with Memory Creation

Context parameters can also be used when creating memories:

```bash
mcp_memory create "Finished the project" \
  --emotion-type joy \
  --emotion-intensity 0.9 \
  --physical_state "tired but satisfied" \
  --mental_state "accomplished" \
  --environment "home office" \
  --importance 0.8
```

**Note:** These parameters are stored with the memory AND update the current context.

---

## Common Patterns

### Daily Routine Setup

```bash
# Morning routine
mcp_memory update_context \
  --physical_state "refreshed" \
  --mental_state "ready" \
  --environment "home"

# Set daily goal
mcp_memory goal "Complete code review and implement new feature"
```

### Emotion Tracking

```bash
# Start of work
mcp_memory emotion_flow "Starting work day" \
  --emotion-type calm \
  --emotion-intensity 0.6

# After achievement
mcp_memory emotion_flow "Successfully deployed feature" \
  --emotion-type joy \
  --emotion-intensity 0.9
```

### Anniversary Reminders

```bash
# Add important dates
mcp_memory anniversary "Project launch anniversary" \
  --persona-info '{"date": "2025-06-15"}'

# Check upcoming anniversaries (automatic in get_context)
mcp_context
```

---

## See Also

- [Memory Operations](./memory_operations.md) - Core CRUD and search operations
- [SKILL.md](../SKILL.md) - Main skill documentation
- [Item Operations](./item_operations.md) - Item and equipment management
