# Item Operations Reference

Complete reference for item and equipment management using the unified `item` tool.

## Overview

Item operations manage the persona's inventory and equipment system. Items can be added, equipped, searched, and analyzed for associated memories.

**Available Operations:**
- `add` - Add item to inventory
- `remove` - Remove item from inventory
- `equip` - Equip item to slot(s)
- `unequip` - Unequip item from slot(s)
- `update` - Update item details
- `rename` - Rename an item
- `search` - Search inventory
- `history` - Get equipment history
- `memories` - Get memories associated with item
- `stats` - Get item statistics

---

## Add Item

Add a new item to the inventory.

### Basic Addition

```bash
mcp_item add "Red Dress" \
  --category clothing
```

### Full Details

```bash
mcp_item add "Blue Summer Hat" \
  --category accessory \
  --description "Light blue straw hat with ribbon" \
  --tags "summer,casual,outdoor" \
  --quantity 1
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `item_name` | string | *required* | Item name |
| `category` | string | null | Item category |
| `description` | string | null | Item description |
| `tags` | list[string] | [] | Tags for categorization |
| `quantity` | int | 1 | Number of items to add |

**Categories:**
- `clothing` - Dresses, shirts, pants
- `accessory` - Hats, jewelry, bags
- `footwear` - Shoes, sandals, boots
- `weapon` - Combat equipment
- `consumable` - Single-use items
- `tool` - Utility items
- Custom categories allowed

**Guidelines:**

✅ **ADD to inventory:**
- Physical items that can be equipped or worn
- Items that can be held or carried
- Equipment with visual/tactical significance

❌ **DO NOT add to inventory:**
- Body states ("敏感な胸", "tired body")
- Sensations ("warm feeling", "hunger")
- Emotions or memories
- Abstract concepts

Use the `memory` tool for body states and sensations instead.

---

## Remove Item

Remove item from inventory.

### Remove Single Item

```bash
mcp_item remove "Red Dress"
```

### Remove Multiple Quantities

```bash
mcp_item remove "Health Potion" \
  --quantity 3
```

**Parameters:**
- `item_name`: Item name to remove (required)
- `quantity`: Number to remove (default: 1)

**Notes:**
- If item is currently equipped, it will be unequipped first
- Removing all quantities deletes the item entry
- Cannot remove more than available quantity

---

## Equip Item

Equip items to equipment slots.

### Equip Single Item

```bash
mcp_item equip \
  --top "White Dress"
```

### Equip Multiple Items

```bash
mcp_item equip \
  --top "White Dress" \
  --foot "Sandals" \
  --accessory "Blue Hat"
```

**Equipment Slots:**

| Slot | Description | Examples |
|------|-------------|----------|
| `top` | Upper body | Dresses, shirts, jackets |
| `bottom` | Lower body | Pants, skirts |
| `foot` | Footwear | Shoes, sandals, boots |
| `accessory` | Accessories | Hats, jewelry, bags |
| `hand_left` | Left hand | Shields, tools |
| `hand_right` | Right hand | Weapons, tools |
| Custom slots | Any slot name | Use as needed |

**Parameters:**
- `equipment`: Dict mapping slot names to item names (required)

**Behavior:**
- Replaces any previously equipped item in the slot
- Unequipped items remain in inventory
- All specified slots are equipped atomically
- Other slots remain unchanged

**Examples:**

```bash
# Change outfit (keeps other slots)
mcp_item equip \
  --top "Red Evening Dress" \
  --foot "High Heels"

# Full equipment
mcp_item equip \
  --top "Battle Armor" \
  --hand_right "Sword" \
  --hand_left "Shield"
```

---

## Unequip Item

Unequip items from slots.

### Unequip Single Slot

```bash
mcp_item unequip \
  --slots "top"
```

### Unequip Multiple Slots

```bash
mcp_item unequip \
  --slots "top,foot,accessory"
```

**Parameters:**
- `slots`: Comma-separated slot names (required)

**Notes:**
- Unequipped items remain in inventory
- Empty slots are left empty
- Invalid slot names are ignored

---

## Update Item

Update item details (description, tags, category).

```bash
mcp_item update "Blue Hat" \
  --description "Light blue summer hat with white ribbon" \
  --tags "summer,casual,favorite"
```

**Parameters:**
- `item_name`: Item to update (required)
- `description`: New description (optional)
- `tags`: New tags (optional)
- `category`: New category (optional)

**Notes:**
- Only specified fields are updated
- Unspecified fields remain unchanged
- Cannot update quantity (use add/remove instead)

---

## Rename Item

Rename an existing item.

```bash
mcp_item rename "Blue Hat" \
  --new-name "Azure Summer Hat"
```

**Parameters:**
- `item_name`: Current item name (required)
- `new_name`: New item name (required)

**Behavior:**
- Updates item name in inventory database
- Updates equipment record if item is currently equipped
- Updates all associated memories containing the item name
- Preserves all other item attributes (description, tags, etc.)

**Notes:**
- Item must exist in inventory
- New name must not conflict with existing items
- Equipment slot remains unchanged if item is equipped

---

## Search Items

Search inventory with various filters.

### Search All Items

```bash
mcp_item search
```

### Search by Category

```bash
mcp_item search \
  --category clothing
```

### Search Equipped Items

```bash
mcp_item search \
  --equipped True
```

### Search by Query

```bash
mcp_item search \
  --query "summer"
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Search term (matches name, description, tags) |
| `category` | string | Filter by category |
| `equipped` | bool | Filter equipped items only |

**Search Behavior:**
- Query searches item name, description, and tags
- Case-insensitive matching
- Partial matches supported
- Results include item details and equipment status

---

## Equipment History

View equipment change history.

### All History

```bash
mcp_item history
```

### Specific Slot History

```bash
mcp_item history \
  --history-slot "top" \
  --days 30
```

**Parameters:**
- `history_slot`: Slot name to filter (optional)
- `days`: Number of days to look back (default: 7)

**Output:**
- Timestamp of equipment change
- Slot name
- Previous item (if any)
- New item (if any)
- Action (equipped/unequipped)

---

## Item Memories

Get memories associated with an item.

```bash
mcp_item memories "White Dress" \
  --limit 10
```

**Parameters:**
- `item_name`: Item name (required)
- `top_k`: Number of memories to return (default: 10)
- `mode`: Analysis mode (currently: "memories")

**How it works:**
- Searches memories for mentions of the item name
- Returns semantic matches (not just exact text)
- Sorted by relevance and recency
- Includes equipment context (when was it worn)

**Use cases:**
- "What memories do I have with this item?"
- "When did I last wear this dress?"
- "What happened while using this tool?"

---

## Item Statistics

Get comprehensive item statistics.

```bash
mcp_item stats
```

**Returns:**
- Total item count
- Item count by category
- Currently equipped items
- Most frequently equipped items
- Items with most associated memories
- Recently added items
- Equipment change frequency

---

## Common Patterns

### Outfit Management

```bash
# Morning outfit
mcp_item equip \
  --top "Casual Shirt" \
  --bottom "Jeans" \
  --foot "Sneakers"

# Evening outfit
mcp_item equip \
  --top "Evening Dress" \
  --foot "Heels" \
  --accessory "Pearl Necklace"

# Check current outfit
mcp_item search --equipped True
```

### Inventory Organization

```bash
# Add with detailed categorization
mcp_item add "Winter Coat" \
  --category clothing \
  --description "Warm wool coat for cold weather" \
  --tags "winter,warm,formal"

# Search by tag
mcp_item search --query "winter"

# Update organization
mcp_item update "Winter Coat" \
  --tags "winter,warm,formal,favorite"
```

### Memory Association

```bash
# Add item
mcp_item add "Camera" \
  --category tool \
  --description "Digital camera for photography"

# Create memory while item is equipped
mcp_memory create "Captured beautiful sunset photos at the beach" \
  --tags "photography,outdoor" \
  --importance 0.8

# Later: find memories with this item
mcp_item memories "Camera" \
  --limit 20
```

### Equipment Tracking

```bash
# Check recent equipment changes
mcp_item history --days 7

# Track specific slot
mcp_item history \
  --history-slot "hand_right" \
  --days 30

# See what was worn during an event
mcp_memory search "party" \
  --date-range "2026-02-01"
```

---

## Integration with Memory System

### Auto-Association

When an item is equipped, new memories automatically reference equipped items:

```bash
# Equip item
mcp_item equip \
  --top "Red Dress"

# Create memory (auto-associated with equipped items)
mcp_memory create "Attended gala event downtown"

# Later: search memories by item
mcp_memory search "events" \
  --equipped-item "Red Dress"
```

### Contextual Search

```bash
# Find all activities while wearing specific item
mcp_item memories "Running Shoes" \
  --limit 20

# Find memories from specific time period with item
mcp_memory search "exercise" \
  --equipped-item "Running Shoes" \
  --date-range "過去1ヶ月"
```

---

## Best Practices

### Naming Convention

```bash
# ✅ Good: Descriptive, unique names
"White Summer Dress"
"Blue Straw Hat"
"Silver Wedding Ring"

# ❌ Avoid: Generic, duplicate names
"Dress"
"Hat"
"Ring"
```

### Category Usage

```bash
# Consistent categorization helps organization
clothing:   top, bottom, outer
accessory:  hat, jewelry, bag
footwear:   shoes, sandals, boots
tool:       camera, phone, laptop
weapon:     sword, bow, staff
```

### Tag Strategy

```bash
# Multi-dimensional tagging
--tags "season:winter,style:formal,color:black,occasion:business"

# Enables flexible search
item search --query "formal"
item search --query "winter"
item search --query "business"
```

---

## See Also

- [Memory Operations](./memory_operations.md) - Core memory CRUD and search
- [Context Operations](./context_operations.md) - Context management
- [SKILL.md](../SKILL.md) - Main skill documentation
