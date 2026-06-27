def upgrade(db) -> None:
    """chat_settings テーブルを追加する。"""
    db.execute("""
    CREATE TABLE IF NOT EXISTS chat_settings (
        persona     TEXT PRIMARY KEY,
        provider    TEXT DEFAULT 'anthropic',
        model       TEXT DEFAULT '',
        api_key     TEXT DEFAULT '',
        base_url    TEXT DEFAULT '',
        system_prompt TEXT DEFAULT '',
        temperature REAL DEFAULT 0.7,
        max_tokens  INTEGER DEFAULT 2048,
        max_window_turns INTEGER DEFAULT 3,
        max_tool_calls INTEGER DEFAULT 5,
        updated_at  TEXT
    )
    """)
    db.commit()
