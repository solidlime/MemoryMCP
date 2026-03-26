from __future__ import annotations


def upgrade(db) -> None:
    """Create initial schema tables if they don't already exist.

    This mirrors the canonical schema defined in
    ``memory_mcp.infrastructure.sqlite.connection`` so that a blank database
    can be bootstrapped purely through the migration system.
    """
    db.executescript(
        """\
CREATE TABLE IF NOT EXISTS memories (
    key TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    tags TEXT DEFAULT '[]',
    importance REAL DEFAULT 0.5,
    emotion TEXT DEFAULT 'neutral',
    emotion_intensity REAL DEFAULT 0.0,
    physical_state TEXT,
    mental_state TEXT,
    environment TEXT,
    relationship_status TEXT,
    action_tag TEXT,
    source_context TEXT,
    related_keys TEXT DEFAULT '[]',
    summary_ref TEXT,
    equipped_items TEXT,
    access_count INTEGER DEFAULT 0,
    last_accessed TEXT,
    privacy_level TEXT DEFAULT 'internal'
);

CREATE TABLE IF NOT EXISTS memory_strength (
    memory_key TEXT PRIMARY KEY,
    strength REAL DEFAULT 1.0,
    stability REAL DEFAULT 1.0,
    last_decay TEXT,
    recall_count INTEGER DEFAULT 0,
    last_recall TEXT,
    FOREIGN KEY (memory_key) REFERENCES memories(key)
);

CREATE TABLE IF NOT EXISTS memory_blocks (
    block_name TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    block_type TEXT DEFAULT 'custom',
    max_tokens INTEGER DEFAULT 500,
    priority INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS context_state (
    persona TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    valid_from TEXT NOT NULL,
    valid_until TEXT,
    change_source TEXT,
    PRIMARY KEY (persona, key, valid_from)
);

CREATE TABLE IF NOT EXISTS emotion_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emotion_type TEXT NOT NULL,
    intensity REAL DEFAULT 0.5,
    timestamp TEXT NOT NULL,
    trigger_memory_key TEXT,
    context TEXT
);

CREATE TABLE IF NOT EXISTS user_info (
    persona TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (persona, key)
);

CREATE TABLE IF NOT EXISTS persona_info (
    persona TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (persona, key)
);

CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    priority INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS promises (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    priority INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    fulfilled_at TEXT,
    metadata TEXT DEFAULT '{}'
);
"""
    )
