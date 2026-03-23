"""Migration v004: Add entity graph tables."""

from __future__ import annotations

VERSION = "004"
DESCRIPTION = "Add entity graph tables"


def upgrade(db) -> None:
    """Create entities, entity_relations, and memory_entities tables."""
    db.executescript("""\
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL DEFAULT 'unknown',
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    mention_count INTEGER DEFAULT 1,
    metadata TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);

CREATE TABLE IF NOT EXISTS entity_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_entity TEXT NOT NULL REFERENCES entities(id),
    target_entity TEXT NOT NULL REFERENCES entities(id),
    relation_type TEXT NOT NULL,
    memory_key TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    UNIQUE(source_entity, target_entity, relation_type, memory_key)
);
CREATE INDEX IF NOT EXISTS idx_relations_source ON entity_relations(source_entity);
CREATE INDEX IF NOT EXISTS idx_relations_target ON entity_relations(target_entity);

CREATE TABLE IF NOT EXISTS memory_entities (
    memory_key TEXT NOT NULL,
    entity_id TEXT NOT NULL REFERENCES entities(id),
    role TEXT DEFAULT 'mentioned',
    PRIMARY KEY (memory_key, entity_id)
);
""")


def downgrade(db) -> None:
    """Drop entity graph tables."""
    db.execute("DROP TABLE IF EXISTS memory_entities")
    db.execute("DROP TABLE IF EXISTS entity_relations")
    db.execute("DROP TABLE IF EXISTS entities")
