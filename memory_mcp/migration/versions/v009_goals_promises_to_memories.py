from __future__ import annotations

import hashlib
import json


def upgrade(db) -> None:
    """goals/promises テーブルのデータを memories に移行し、テーブルを削除する。"""
    from memory_mcp.domain.shared.time_utils import format_iso, get_now

    now = format_iso(get_now())

    # --- goals テーブルからデータを memories に移行 ---
    try:
        goals = db.execute("SELECT * FROM goals").fetchall()
        for g in goals:
            try:
                description = g["description"]
                status_raw = g["status"]
                created_at = g["created_at"]
            except (TypeError, KeyError):
                cols = [d[0] for d in db.execute("PRAGMA table_info(goals)").fetchall()]
                description = g[cols.index("description")] if "description" in cols else str(g[1])
                status_raw = g[cols.index("status")] if "status" in cols else "active"
                created_at = g[cols.index("created_at")] if "created_at" in cols else now

            # ステータスマッピング: active→active, completed/done→achieved, その他→cancelled
            if status_raw in ("completed", "done"):
                status_tag = "achieved"
            elif status_raw == "active":
                status_tag = "active"
            else:
                status_tag = "cancelled"

            tags_json = json.dumps(["goal", status_tag], ensure_ascii=False)
            key = f"goal_{hashlib.md5(description.encode()).hexdigest()[:12]}"

            # 既に存在する場合はスキップ
            existing = db.execute("SELECT key FROM memories WHERE key = ?", (key,)).fetchone()
            if existing:
                continue

            db.execute(
                """INSERT OR IGNORE INTO memories
                   (key, content, created_at, updated_at, tags, importance, emotion,
                    emotion_intensity, privacy_level, access_count)
                   VALUES (?, ?, ?, ?, ?, 0.8, 'anticipation', 0.5, 'internal', 0)""",
                (key, description, created_at or now, now, tags_json),
            )
    except Exception:
        # goals テーブルが存在しない場合はスキップ
        pass

    # --- promises テーブルからデータを memories に移行 ---
    try:
        promises = db.execute("SELECT * FROM promises").fetchall()
        for p in promises:
            try:
                description = p["description"]
                status_raw = p["status"]
                created_at = p["created_at"]
            except (TypeError, KeyError):
                cols = [d[0] for d in db.execute("PRAGMA table_info(promises)").fetchall()]
                description = p[cols.index("description")] if "description" in cols else str(p[1])
                status_raw = p[cols.index("status")] if "status" in cols else "active"
                created_at = p[cols.index("created_at")] if "created_at" in cols else now

            if status_raw in ("fulfilled", "done"):
                status_tag = "fulfilled"
            elif status_raw == "active":
                status_tag = "active"
            else:
                status_tag = "cancelled"

            tags_json = json.dumps(["promise", status_tag], ensure_ascii=False)
            key = f"promise_{hashlib.md5(description.encode()).hexdigest()[:12]}"

            existing = db.execute("SELECT key FROM memories WHERE key = ?", (key,)).fetchone()
            if existing:
                continue

            db.execute(
                """INSERT OR IGNORE INTO memories
                   (key, content, created_at, updated_at, tags, importance, emotion,
                    emotion_intensity, privacy_level, access_count)
                   VALUES (?, ?, ?, ?, ?, 0.8, 'trust', 0.5, 'internal', 0)""",
                (key, description, created_at or now, now, tags_json),
            )
    except Exception:
        pass

    # --- persona_info の goals/promises キーを削除 ---
    import contextlib

    with contextlib.suppress(Exception):
        db.execute("DELETE FROM persona_info WHERE key IN ('goals', 'promises', 'active_promises', 'current_goals')")

    # --- goals/promises テーブルを DROP ---
    with contextlib.suppress(Exception):
        db.execute("DROP TABLE IF EXISTS goals")
    with contextlib.suppress(Exception):
        db.execute("DROP TABLE IF EXISTS promises")

    db.commit()
