"""
所持品管理データベース - SQLiteベース

データベース構造:
- items: アイテムマスター（全アイテムの定義）
- inventory: 所持品リスト（persona別の所持数量）
- equipment_history: 装備履歴（装備/解除のログ）
"""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from .time_utils import get_current_time


def get_equipment_db_path(persona: str) -> Path:
    """ペルソナ別の装備DBパスを取得"""
    base_dir = Path("data/memory") / persona
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "equipment.db"


def init_equipment_db(persona: str) -> None:
    """装備DBを初期化（テーブル作成）"""
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
            created_at TEXT NOT NULL
        )
    """)
    
    # 所持品（persona別）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            persona TEXT NOT NULL,
            item_id TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
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
    
    conn.commit()
    conn.close()


class EquipmentDB:
    """装備管理データベースクラス"""
    
    def __init__(self, persona: str):
        self.persona = persona
        self.db_path = get_equipment_db_path(persona)
        init_equipment_db(persona)
    
    def _get_connection(self) -> sqlite3.Connection:
        """DB接続を取得"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # dict-like access
        return conn
    
    # ==================== アイテム管理 ====================
    
    def add_item(
        self, 
        item_name: str, 
        description: str = None, 
        category: str = "misc"
    ) -> str:
        """アイテムマスターに新規アイテムを追加"""
        item_id = str(uuid.uuid4())
        created_at = get_current_time().isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO items (item_id, item_name, description, category, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (item_id, item_name, description, category, created_at))
        
        conn.commit()
        conn.close()
        return item_id
    
    def get_item_by_name(self, item_name: str) -> Optional[Dict[str, Any]]:
        """アイテム名でアイテム情報を取得"""
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
        description: str = None, 
        category: str = "misc"
    ) -> str:
        """アイテムを取得、存在しなければ作成"""
        existing = self.get_item_by_name(item_name)
        if existing:
            return existing["item_id"]
        return self.add_item(item_name, description, category)
    
    # ==================== 所持品管理 ====================
    
    def add_to_inventory(
        self, 
        item_name: str, 
        quantity: int = 1,
        description: str = None,
        category: str = "misc"
    ) -> str:
        """所持品に追加"""
        item_id = self.get_or_create_item(item_name, description, category)
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
        """所持品から削除"""
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
    
    def get_inventory(self, category: str = None) -> List[Dict[str, Any]]:
        """所持品リストを取得"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if category:
            cursor.execute("""
                SELECT i.*, inv.quantity, inv.acquired_at
                FROM items i
                JOIN inventory inv ON i.item_id = inv.item_id
                WHERE inv.persona = ? AND i.category = ?
                ORDER BY inv.acquired_at DESC
            """, (self.persona, category))
        else:
            cursor.execute("""
                SELECT i.*, inv.quantity, inv.acquired_at
                FROM items i
                JOIN inventory inv ON i.item_id = inv.item_id
                WHERE inv.persona = ?
                ORDER BY inv.acquired_at DESC
            """, (self.persona,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # ==================== 装備履歴管理 ====================
    
    def log_equipment_change(
        self, 
        slot: str, 
        item_name: Optional[str], 
        action: str
    ) -> None:
        """装備変更を履歴に記録"""
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
        """装備履歴を取得"""
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
