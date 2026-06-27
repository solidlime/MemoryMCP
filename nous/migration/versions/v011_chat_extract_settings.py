import contextlib


def upgrade(db) -> None:
    """chat_settings テーブルに自動ファクト抽出設定カラムを追加する。"""
    for sql in [
        "ALTER TABLE chat_settings ADD COLUMN auto_extract INTEGER DEFAULT 1",
        "ALTER TABLE chat_settings ADD COLUMN extract_model TEXT DEFAULT ''",
        "ALTER TABLE chat_settings ADD COLUMN extract_max_tokens INTEGER DEFAULT 512",
    ]:
        with contextlib.suppress(Exception):
            db.execute(sql)
    db.commit()
