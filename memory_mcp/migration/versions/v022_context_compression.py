from __future__ import annotations

import contextlib


def upgrade(db) -> None:
    """Add context compression and parallel tools columns to chat_settings (v2.1)."""
    new_columns = [
        ("max_stored_messages", "INTEGER DEFAULT 200"),
        ("context_max_tokens", "INTEGER DEFAULT NULL"),
        ("context_compression_threshold", "REAL DEFAULT 0.8"),
        ("context_compression_mode", "TEXT DEFAULT 'auto'"),
        ("context_keep_recent_turns", "INTEGER DEFAULT 2"),
        ("context_compress_system_prompt", "INTEGER DEFAULT 1"),
        ("context_compress_history", "INTEGER DEFAULT 1"),
        ("memory_preload_count", "INTEGER DEFAULT 3"),
        ("enable_parallel_tools", "INTEGER DEFAULT 1"),
    ]
    for col_name, col_def in new_columns:
        with contextlib.suppress(Exception):
            db.execute(f"ALTER TABLE chat_settings ADD COLUMN {col_name} {col_def}")
    db.commit()
