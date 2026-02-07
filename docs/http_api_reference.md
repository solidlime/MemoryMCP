# Memory MCP — HTTP API Reference

All endpoints are served from the MCP HTTP server (default port `26262`).  
Persona-scoped endpoints use `{persona}` as a path parameter (e.g. `nilou`, `default`).

---

## Dashboard & Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Web dashboard UI |
| GET | `/health` | Health check + stats |
| GET | `/api/personas` | List available personas |

---

## Dashboard Data

### `GET /api/dashboard/{persona}`
Returns combined dashboard payload (info, metrics, stats, knowledge graph URL).

**Response fields:**
- `info` – persona context (name, relationship, favorites, etc.)
- `metrics` – total memories, content chars, vector count, tagged/linked counts
- `stats` – timeline array, tag distribution, top links
  - `stats.timeline` – array of `{date, count}` for last N days (configurable via `dashboard.timeline_days`, default 14)
- `knowledge_graph_url` – URL to the latest knowledge graph HTML, or `null`

---

## Observation Stream (Memory Browsing)

### `GET /api/observations/{persona}`
Paginated list of all memories, sorted chronologically.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number (1-based) |
| `per_page` | int | 20 | Items per page (max 100) |
| `sort` | str | `desc` | `desc` (newest first) or `asc` |
| `tag` | str | — | Filter by tag |
| `q` | str | — | Keyword search in content |

**Response:**
```json
{
  "success": true,
  "total": 142,
  "page": 1,
  "per_page": 20,
  "total_pages": 8,
  "items": [
    {
      "key": "memory_20250101_120000",
      "content_preview": "First 300 chars...",
      "emotion_type": "joy",
      "emotion_intensity": 0.8,
      "importance": 0.9,
      "tags": ["coding", "milestone"],
      "context_tags": ["workspace"],
      "created_at": "2025-01-01T12:00:00",
      "updated_at": "2025-01-01T12:00:00",
      "privacy_level": "internal",
      "action_tag": "achievement",
      "environment": "vscode"
    }
  ]
}
```

### `GET /api/memory/{persona}/{key}`
Get full detail for a single memory by its key.

**Response:**
```json
{
  "success": true,
  "memory": { "...full row..." },
  "linked_keys": ["other_memory_key"],
  "history": [
    { "timestamp": "...", "operation": "create", "success": 1, "error": null }
  ]
}
```

---

## Emotion & Sensation Timelines

### `GET /api/emotion-timeline/{persona}`
Daily and weekly emotion aggregations.

**Query params:** `days` (default 30)

### `GET /api/physical-sensations-timeline/{persona}`
Physical sensation history (fatigue, warmth, arousal).

**Query params:** `days` (default 30)

---

## Anniversaries

### `GET /api/anniversaries/{persona}`
Anniversary-tagged memories grouped by month-day.

---

## Audit Log

### `GET /api/audit-log/{persona}`
Browse the operations audit log with filtering and pagination.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number (1-based) |
| `per_page` | int | 50 | Items per page (max 200) |
| `operation` | str | — | Filter by op type (create/read/update/delete/search) |
| `key` | str | — | Filter by memory key (substring match) |
| `success` | str | — | `true` or `false` |
| `since` | str | — | ISO date filter (e.g. `2025-01-01`) |

**Response:**
```json
{
  "success": true,
  "total": 520,
  "page": 1,
  "per_page": 50,
  "total_pages": 11,
  "operation_breakdown": { "create": 200, "read": 150, "search": 120, "update": 40, "delete": 10 },
  "items": [
    {
      "id": 520,
      "timestamp": "2025-07-15T10:30:00",
      "operation_id": "uuid...",
      "operation": "create",
      "key": "memory_20250715_103000",
      "success": 1,
      "error": null,
      "metadata": {}
    }
  ]
}
```

---

## Unified Timeline

### `GET /api/timeline/{persona}`
Merges memories, emotions, physical sensations, and operations into a single chronological stream.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `days` | int | 7 | Days to look back (max 90) |
| `types` | str | `memory,emotion,sensation,operation` | Comma-separated event types |
| `limit` | int | 100 | Max events (max 500) |

**Response:**
```json
{
  "success": true,
  "days": 7,
  "total_events": 85,
  "type_counts": { "memory": 30, "emotion": 25, "sensation": 20, "operation": 10 },
  "events": [
    { "type": "memory", "timestamp": "...", "key": "...", "summary": "...", "emotion_type": "joy", ... },
    { "type": "emotion", "timestamp": "...", "emotion_type": "love", "emotion_intensity": 0.9, "trigger": "..." },
    { "type": "sensation", "timestamp": "...", "fatigue": 0.3, "warmth": 0.7, "arousal": 0.2 },
    { "type": "operation", "timestamp": "...", "operation": "search", "key": null, "success": true }
  ]
}
```

---

## Admin Tools

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/admin/clean` | Clean/delete a memory by key |
| POST | `/api/admin/rebuild` | Rebuild vector store |
| POST | `/api/admin/rebuild-stream` | Rebuild vector store (SSE stream) |
| POST | `/api/admin/migrate` | Migrate vector backend |
| POST | `/api/admin/migrate-schema` | Migrate DB schema (add missing columns) |
| POST | `/api/admin/detect-duplicates` | Detect duplicate memories |
| POST | `/api/admin/merge-memories` | Merge duplicate memories |
| POST | `/api/admin/generate-knowledge-graph` | Generate knowledge graph |
| POST | `/api/admin/create-summary` | Create memory summary |
| GET  | `/api/admin/create-summary-stream` | Create summary (SSE stream) |

---

## Configuration Notes

### Privacy Filtering
Dashboard and observation APIs respect `privacy.dashboard_max_level` config.
Only memories with privacy rank ≤ configured level are shown.

Levels: `public` (0) < `internal` (1) < `private` (2) < `secret` (3)

### Resource Profiles
Set `resource_profile` in config to tune for hardware:
- `"normal"` – full features, default settings
- `"low"` – DS920+ 20GB optimized (relaxed reranker, longer intervals)
- `"minimal"` – very constrained (no reranker, no semantic fallback)
