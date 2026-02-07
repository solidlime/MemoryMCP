#!/usr/bin/env python3
"""nilouのDB状態を詳しく確認"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3

def main():
    # nilouのDBパス
    db_path = "/home/rausraus/memory-mcp/data/memory/nilou/inventory.sqlite"

    print(f"=== {db_path} の詳細 ===\n")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # テーブル一覧
    print("【テーブル一覧】")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    for table in tables:
        print(f"  - {table['name']}")

    print("\n" + "="*60 + "\n")

    # inventoryテーブルのスキーマ
    print("【inventoryテーブルのスキーマ】")
    cursor.execute("PRAGMA table_info(inventory)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  {col['name']}: {col['type']}")

    print("\n" + "="*60 + "\n")

    # 装備中のアイテム（生データ）
    print("【装備中のアイテム（is_equipped=1）】")
    cursor.execute("""
        SELECT
            i.item_name,
            inv.equipped_slot,
            inv.is_equipped
        FROM inventory inv
        JOIN items i ON inv.item_id = i.item_id
        WHERE inv.persona = 'nilou' AND inv.is_equipped = 1
        ORDER BY inv.equipped_slot
    """)

    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(f"  slot='{row['equipped_slot']}', item='{row['item_name']}', equipped={row['is_equipped']}")
    else:
        print("  (なし)")

    print("\n" + "="*60 + "\n")

    # 全アイテム
    print("【全アイテム（equipped_slot付き）】")
    cursor.execute("""
        SELECT
            i.item_name,
            inv.equipped_slot,
            inv.is_equipped
        FROM inventory inv
        JOIN items i ON inv.item_id = i.item_id
        WHERE inv.persona = 'nilou'
        ORDER BY inv.is_equipped DESC, inv.equipped_slot
    """)

    rows = cursor.fetchall()
    if rows:
        for row in rows:
            equipped_mark = "⚔️" if row['is_equipped'] else "  "
            slot = row['equipped_slot'] if row['equipped_slot'] else "(none)"
            print(f"  {equipped_mark} slot={slot:20s} item={row['item_name']}")
    else:
        print("  (なし)")

    conn.close()

if __name__ == "__main__":
    main()
