"""
所持品管理データベース - SQLiteベース

データベース構造:
- items: アイテムマスター（全アイテムの定義）
- inventory: 所持品リスト（persona別の所持数量）
- equipment_history: 装備履歴（装備/解除のログ）

Note: inventory.sqliteはmemory.sqliteと同じディレクトリに保存される
"""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from .time_utils import get_current_time


def get_equipment_db_path(persona: str) -> Path:
    """ペルソナ別の装備DBパスを取得

    memory.sqliteと同じディレクトリにinventory.sqliteとして保存
    Docker環境でもホストマウントされるディレクトリ
    """
    from src.utils.persona_utils import get_persona_dir
    persona_dir = Path(get_persona_dir(persona))
    new_path = persona_dir / "inventory.sqlite"

    # Legacy migration: equipment.db -> item.sqlite -> inventory.sqlite
    legacy_paths = [
        persona_dir / "equipment.db",
        persona_dir / "item.sqlite"
    ]

    for legacy_path in legacy_paths:
        if legacy_path.exists() and not new_path.exists():
            try:
                legacy_path.rename(new_path)
                print(f"✅ Migrated {legacy_path.name} -> {new_path.name}")
                break
            except Exception as e:
                print(f"⚠️ Failed to migrate {legacy_path.name}: {e}")

    return new_path


def init_equipment_db(persona: str) -> None:
    """Initialize equipment database (create tables)"""
    db_path = get_equipment_db_path(persona)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # アイテムマスター
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            item_id TEXT PRIMARY KEY,
            item_name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            tags TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # 所持品（persona別）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            persona TEXT NOT NULL,
            item_id TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            is_equipped INTEGER DEFAULT 0,
            equipped_slot TEXT,
            acquired_at TEXT NOT NULL,
            PRIMARY KEY (persona, item_id),
            FOREIGN KEY (item_id) REFERENCES items(item_id)
        )
    """)

    # 装備履歴
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS equipment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            persona TEXT NOT NULL,
            item_id TEXT,
            slot TEXT NOT NULL,
            action TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (item_id) REFERENCES items(item_id)
        )
    """)

    # インデックス
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_inventory_persona
        ON inventory(persona)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_equipment_history_persona
        ON equipment_history(persona, timestamp)
    """)

    # マイグレーション: 既存DBに新カラムを追加
    _migrate_equipment_db(conn)

    conn.commit()
    conn.close()


def _migrate_equipment_db(conn: sqlite3.Connection) -> None:
    """Migrate existing database schema"""
    cursor = conn.cursor()

    # items テーブルに tags カラムがあるか確認
    cursor.execute("PRAGMA table_info(items)")
    columns = [row[1] for row in cursor.fetchall()]

    if "tags" not in columns:
        cursor.execute("ALTER TABLE items ADD COLUMN tags TEXT")
        conn.commit()

    # inventory テーブルに is_equipped, equipped_slot カラムがあるか確認
    cursor.execute("PRAGMA table_info(inventory)")
    columns = [row[1] for row in cursor.fetchall()]

    if "is_equipped" not in columns:
        cursor.execute("ALTER TABLE inventory ADD COLUMN is_equipped INTEGER DEFAULT 0")
        conn.commit()

    if "equipped_slot" not in columns:
        cursor.execute("ALTER TABLE inventory ADD COLUMN equipped_slot TEXT")
        conn.commit()


class EquipmentDB:
    """Equipment management database class"""

    def __init__(self, persona: str):
        self.persona = persona
        self.db_path = get_equipment_db_path(persona)
        init_equipment_db(persona)
        # 旧スキーマからの移行で items のみが存在し、inventory が空の場合は
        # 現在のペルソナ用に在庫をバックフィル（数量=1, 未装備）
        try:
            self._backfill_inventory_if_empty()
        except Exception:
            # バックフィル失敗は致命的ではないため無視
            pass
        # スロット名の引用符を自動修正
        try:
            self._migrate_slot_names()
        except Exception:
            # マイグレーション失敗は致命的ではないため無視
            pass

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # dict-like access
        return conn

    @staticmethod
    def _normalize_slot_name(slot: str) -> str:
        """スロット名を正規化（引用符、余分な空白を削除）

        Args:
            slot: 正規化するスロット名

        Returns:
            正規化されたスロット名

        Examples:
            _normalize_slot_name('"top"') -> 'top'
            _normalize_slot_name('  hand  ') -> 'hand'
            _normalize_slot_name('\\"outer\\"') -> 'outer'
        """
        if not slot:
            return slot
        # 引用符を削除（シングル、ダブル、エスケープされた引用符）
        normalized = slot.strip().strip('"').strip("'").replace('\\"', '').replace("\\'", '')
        # 余分な空白を削除
        normalized = normalized.strip()
        return normalized

    def _migrate_slot_names(self):
        """Normalize existing slot names (fix quoted slots)"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 引用符付きスロットを検索
            cursor.execute("""
                SELECT DISTINCT equipped_slot
                FROM inventory
                WHERE persona = ? AND equipped_slot IS NOT NULL
            """, (self.persona,))

            slots = [row["equipped_slot"] for row in cursor.fetchall()]

            # 正規化が必要なスロットを修正
            for slot in slots:
                normalized = self._normalize_slot_name(slot)
                if slot != normalized:
                    cursor.execute("""
                        UPDATE inventory
                        SET equipped_slot = ?
                        WHERE persona = ? AND equipped_slot = ?
                    """, (normalized, self.persona, slot))

            conn.commit()
            conn.close()
        except Exception:
            # マイグレーションが失敗しても継続
            pass

    def _backfill_inventory_if_empty(self) -> None:
        """inventory が空で items が存在する場合、現在のペルソナ用に在庫をバックフィルする。
        旧DB (equipment.db / item.sqlite) からの移行時に items のみが存在するケースを救済。
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # 現在ペルソナの在庫件数
            cursor.execute("SELECT COUNT(1) FROM inventory WHERE persona = ?", (self.persona,))
            inv_count = cursor.fetchone()[0]
            if inv_count and inv_count > 0:
                conn.close()
                return

            # items テーブルの確認（レガシーからの移行で items のみが存在する可能性）
            cursor.execute("SELECT item_id FROM items")
            item_rows = cursor.fetchall()

            # まず persona_context の current_equipment からバックフィルを試みる
            seeded = False
            try:
                from core.persona_context import load_persona_context
                ctx = load_persona_context(self.persona)
                current_eq = ctx.get("current_equipment") if isinstance(ctx, dict) else None
                if isinstance(current_eq, dict) and current_eq:
                    acquired_at = get_current_time().isoformat()
                    for slot, item_name in current_eq.items():
                        if not item_name:
                            continue
                        # アイテムを登録し、在庫に数量1で追加 + 装備状態を反映
                        item_id = self.get_or_create_item(item_name)
                        cursor.execute(
                            """
                            INSERT INTO inventory (persona, item_id, quantity, is_equipped, equipped_slot, acquired_at)
                            VALUES (?, ?, 1, 1, ?, ?)
                            ON CONFLICT(persona, item_id) DO UPDATE SET
                                is_equipped = 1,
                                equipped_slot = excluded.equipped_slot
                            """,
                            (self.persona, item_id, slot, acquired_at)
                        )
                    conn.commit()
                    seeded = True
            except Exception:
                # persona_context が無い/読み込めない場合は無視
                pass

            if not seeded and item_rows:
                # items が存在し、inventory が空の場合は items 全件を数量1で在庫化（未装備）
                acquired_at = get_current_time().isoformat()
                for row in item_rows:
                    item_id = row[0]
                    cursor.execute(
                        """
                        INSERT INTO inventory (persona, item_id, quantity, is_equipped, acquired_at)
                        VALUES (?, ?, ?, 0, ?)
                        ON CONFLICT(persona, item_id) DO NOTHING
                        """,
                        (self.persona, item_id, 1, acquired_at)
                    )
                conn.commit()
        finally:
            conn.close()

    # ==================== アイテム管理 ====================

    def add_item(
        self,
        item_name: str,
        description: Optional[str] = None,
        category: str = "misc",
        tags: Optional[List[str]] = None
    ) -> str:
        """Add new item to item master"""
        import json
        item_id = str(uuid.uuid4())
        created_at = get_current_time().isoformat()
        tags_json = json.dumps(tags or [], ensure_ascii=False)

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO items (item_id, item_name, description, category, tags, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (item_id, item_name, description, category, tags_json, created_at))

        conn.commit()
        conn.close()
        return item_id

    def get_item_by_name(self, item_name: str) -> Optional[Dict[str, Any]]:
        """Get item information by item name"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM items WHERE item_name = ?
        """, (item_name,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_or_create_item(
        self,
        item_name: str,
        description: Optional[str] = None,
        category: str = "misc",
        tags: Optional[List[str]] = None
    ) -> str:
        """Get item if exists, otherwise create new item"""
        existing = self.get_item_by_name(item_name)
        if existing:
            return existing["item_id"]
        return self.add_item(item_name, description, category, tags)

    def update_item_info(
        self,
        item_name: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Update item information"""
        import json
        item = self.get_item_by_name(item_name)
        if not item:
            return False

        conn = self._get_connection()
        cursor = conn.cursor()

        updates = []
        params = []

        if description is not None:
            updates.append("description = ?")
            params.append(description)

        if category is not None:
            updates.append("category = ?")
            params.append(category)

        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags, ensure_ascii=False))

        if not updates:
            conn.close()
            return False

        params.append(item["item_id"])
        query = f"UPDATE items SET {', '.join(updates)} WHERE item_id = ?"

        cursor.execute(query, params)
        conn.commit()
        conn.close()
        return True


    def rename_item(
        self,
        old_name: str,
        new_name: str
    ) -> bool:
        """アイテム名を変更

        Args:
            old_name: 現在のアイテム名
            new_name: 新しいアイテム名

        Returns:
            bool: 成功した場合True
        """
        # 既存アイテムの確認
        item = self.get_item_by_name(old_name)
        if not item:
            return False

        # 新しい名前が既に存在するかチェック
        existing_new = self.get_item_by_name(new_name)
        if existing_new:
            return False  # 新しい名前が既に使われている

        conn = self._get_connection()
        cursor = conn.cursor()

        # item_name を更新
        cursor.execute("""
            UPDATE items SET item_name = ? WHERE item_id = ?
        """, (new_name, item["item_id"]))

        conn.commit()
        conn.close()
        return True

    # ==================== 所持品管理 ====================

    def add_to_inventory(
        self,
        item_name: str,
        quantity: int = 1,
        description: Optional[str] = None,
        category: str = "misc",
        tags: Optional[List[str]] = None
    ) -> str:
        """Add item to inventory"""
        item_id = self.get_or_create_item(item_name, description, category, tags)
        acquired_at = get_current_time().isoformat()

        conn = self._get_connection()
        cursor = conn.cursor()

        # 既に所持している場合は数量を増やす
        cursor.execute("""
            INSERT INTO inventory (persona, item_id, quantity, acquired_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(persona, item_id) DO UPDATE SET
                quantity = quantity + excluded.quantity
        """, (self.persona, item_id, quantity, acquired_at))

        conn.commit()
        conn.close()
        return item_id

    def remove_from_inventory(self, item_name: str, quantity: int = 1) -> bool:
        """Remove item from inventory"""
        item = self.get_item_by_name(item_name)
        if not item:
            return False

        conn = self._get_connection()
        cursor = conn.cursor()

        # 現在の所持数を確認
        cursor.execute("""
            SELECT quantity FROM inventory
            WHERE persona = ? AND item_id = ?
        """, (self.persona, item["item_id"]))

        row = cursor.fetchone()
        if not row:
            conn.close()
            return False

        current_qty = row["quantity"]

        if current_qty <= quantity:
            # 全て削除
            cursor.execute("""
                DELETE FROM inventory
                WHERE persona = ? AND item_id = ?
            """, (self.persona, item["item_id"]))
        else:
            # 数量を減らす
            cursor.execute("""
                UPDATE inventory
                SET quantity = quantity - ?
                WHERE persona = ? AND item_id = ?
            """, (quantity, self.persona, item["item_id"]))

        conn.commit()
        conn.close()
        return True

    def get_inventory(self, category: Optional[str] = None, tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get inventory list"""
        import json
        conn = self._get_connection()
        cursor = conn.cursor()

        if category:
            cursor.execute("""
                SELECT i.*, inv.quantity, inv.is_equipped, inv.equipped_slot, inv.acquired_at
                FROM items i
                JOIN inventory inv ON i.item_id = inv.item_id
                WHERE inv.persona = ? AND i.category = ?
                ORDER BY inv.acquired_at DESC
            """, (self.persona, category))
        else:
            cursor.execute("""
                SELECT i.*, inv.quantity, inv.is_equipped, inv.equipped_slot, inv.acquired_at
                FROM items i
                JOIN inventory inv ON i.item_id = inv.item_id
                WHERE inv.persona = ?
                ORDER BY inv.acquired_at DESC
            """, (self.persona,))

        rows = cursor.fetchall()
        conn.close()

        items = []
        for row in rows:
            item = dict(row)
            # tags を JSON から list に変換
            if item.get("tags"):
                try:
                    item["tags"] = json.loads(item["tags"])
                except (json.JSONDecodeError, TypeError):
                    item["tags"] = []
            else:
                item["tags"] = []

            # タグフィルタがある場合は絞り込み
            if tags:
                if not any(tag in item["tags"] for tag in tags):
                    continue

            items.append(item)

        return items

    def equip_item(self, item_name: str, slot: str) -> bool:
        """Equip item (automatically unequip existing item in same slot)"""
        item = self.get_item_by_name(item_name)
        if not item:
            return False

        # スロット名を正規化
        slot = self._normalize_slot_name(slot)

        conn = self._get_connection()
        cursor = conn.cursor()

        # 同じスロットに装備中のアイテムを先に外す
        cursor.execute("""
            UPDATE inventory
            SET is_equipped = 0, equipped_slot = NULL
            WHERE persona = ? AND is_equipped = 1 AND equipped_slot = ?
        """, (self.persona, slot))

        # 該当アイテムを装備状態にする
        cursor.execute("""
            UPDATE inventory
            SET is_equipped = 1, equipped_slot = ?
            WHERE persona = ? AND item_id = ?
        """, (slot, self.persona, item["item_id"]))

        affected = cursor.rowcount
        conn.commit()
        conn.close()

        if affected > 0:
            self.log_equipment_change(slot, item_name, "equip")
            return True
        return False

    def equip_items_batch(self, equipment_dict: Dict[str, str]) -> Dict[str, bool]:
        """複数のアイテムを一括装備（全装備リセット後に実行）

        Args:
            equipment_dict: {slot: item_name} の辞書

        Returns:
            Dict[str, bool]: 各スロットの装備成否
        """
        results = {}

        # スロット名を正規化した辞書を作成
        normalized_equipment = {
            self._normalize_slot_name(slot): item_name
            for slot, item_name in equipment_dict.items()
        }

        for slot, item_name in normalized_equipment.items():
            if item_name:  # item_nameがNoneや空文字でない場合のみ装備
                success = self.equip_item(item_name, slot)
                results[slot] = success
            else:
                results[slot] = True  # 空スロットは成功扱い

        return results

    def unequip_item(self, slot: str) -> Optional[str]:
        """Unequip item (change flag only)"""
        # スロット名を正規化
        slot = self._normalize_slot_name(slot)

        conn = self._get_connection()
        cursor = conn.cursor()

        # 該当スロットの装備を探す
        cursor.execute("""
            SELECT i.item_name
            FROM inventory inv
            JOIN items i ON inv.item_id = i.item_id
            WHERE inv.persona = ? AND inv.equipped_slot = ? AND inv.is_equipped = 1
        """, (self.persona, slot))

        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        item_name = row["item_name"]

        # 装備解除
        cursor.execute("""
            UPDATE inventory
            SET is_equipped = 0, equipped_slot = NULL
            WHERE persona = ? AND equipped_slot = ? AND is_equipped = 1
        """, (self.persona, slot))

        conn.commit()
        conn.close()

        self.log_equipment_change(slot, None, "unequip")
        return item_name

    def unequip_all(self) -> List[Tuple[str, str]]:
        """全てのアイテムを装備解除（フラグのみ変更）

        Returns:
            List[Tuple[str, str]]: 解除されたアイテムの(slot, item_name)のリスト
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 現在装備中のアイテムを取得
        cursor.execute("""
            SELECT inv.equipped_slot, i.item_name
            FROM inventory inv
            JOIN items i ON inv.item_id = i.item_id
            WHERE inv.persona = ? AND inv.is_equipped = 1
        """, (self.persona,))

        equipped_items = [(row["equipped_slot"], row["item_name"]) for row in cursor.fetchall()]

        if equipped_items:
            # 全ての装備を解除
            cursor.execute("""
                UPDATE inventory
                SET is_equipped = 0, equipped_slot = NULL
                WHERE persona = ? AND is_equipped = 1
            """, (self.persona,))

            conn.commit()

            # 各装備解除をログに記録
            for slot, item_name in equipped_items:
                self.log_equipment_change(slot, None, "unequip")

        conn.close()
        return equipped_items

    def get_equipped_items(self) -> Dict[str, str]:
        """Get currently equipped items"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT inv.equipped_slot, i.item_name
            FROM inventory inv
            JOIN items i ON inv.item_id = i.item_id
            WHERE inv.persona = ? AND inv.is_equipped = 1
        """, (self.persona,))

        rows = cursor.fetchall()
        conn.close()

        return {row["equipped_slot"]: row["item_name"] for row in rows}

    # ==================== 装備履歴管理 ====================

    def log_equipment_change(
        self,
        slot: str,
        item_name: Optional[str],
        action: str
    ) -> None:
        """Log equipment change to history"""
        item_id = None
        if item_name:
            item = self.get_item_by_name(item_name)
            item_id = item["item_id"] if item else None

        timestamp = get_current_time().isoformat()

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO equipment_history (persona, item_id, slot, action, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (self.persona, item_id, slot, action, timestamp))

        conn.commit()
        conn.close()

    def get_equipment_history(
        self,
        slot: Optional[str] = None,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get equipment history"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # days日前のタイムスタンプを計算
        from datetime import timedelta
        cutoff_time = get_current_time() - timedelta(days=days)
        cutoff_str = cutoff_time.isoformat()

        if slot:
            cursor.execute("""
                SELECT eh.*, i.item_name, i.description, i.category
                FROM equipment_history eh
                LEFT JOIN items i ON eh.item_id = i.item_id
                WHERE eh.persona = ? AND eh.slot = ? AND eh.timestamp >= ?
                ORDER BY eh.timestamp DESC
            """, (self.persona, slot, cutoff_str))
        else:
            cursor.execute("""
                SELECT eh.*, i.item_name, i.description, i.category
                FROM equipment_history eh
                LEFT JOIN items i ON eh.item_id = i.item_id
                WHERE eh.persona = ? AND eh.timestamp >= ?
                ORDER BY eh.timestamp DESC
            """, (self.persona, cutoff_str))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]
