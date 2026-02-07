#!/usr/bin/env python3
"""装備データの整合性をデバッグ"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.equipment_db import EquipmentDB

def main():
    persona = "nilou"
    db = EquipmentDB(persona)

    print("=== 装備データのデバッグ ===\n")

    # 1. get_equipped_items()の結果
    equipped = db.get_equipped_items()
    print("📋 get_equipped_items()の結果:")
    if equipped:
        for slot, item in equipped.items():
            print(f"  {slot}: {item}")
    else:
        print("  (なし)")

    print("\n" + "="*50 + "\n")

    # 2. データベースから直接取得
    import sqlite3
    conn = db._get_connection()
    cursor = conn.cursor()

    print("📋 データベースの生データ (is_equipped=1):")
    cursor.execute("""
        SELECT
            i.item_name,
            inv.equipped_slot,
            inv.is_equipped,
            inv.persona
        FROM inventory inv
        JOIN items i ON inv.item_id = i.item_id
        WHERE inv.persona = ? AND inv.is_equipped = 1
    """, (persona,))

    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(f"  item={row['item_name']}, slot={row['equipped_slot']}, equipped={row['is_equipped']}, persona={row['persona']}")
    else:
        print("  (なし)")

    print("\n" + "="*50 + "\n")

    # 3. unequip_item("hand")をテスト
    print("🧪 unequip_item('hand')のテスト:")
    result = db.unequip_item("hand")
    if result:
        print(f"  ✅ 解除成功: {result}")
    else:
        print(f"  ⚠️ 解除失敗: Noneが返された")

    print("\n" + "="*50 + "\n")

    # 4. 再度確認
    print("📋 unequip後の装備状態:")
    equipped_after = db.get_equipped_items()
    if equipped_after:
        for slot, item in equipped_after.items():
            print(f"  {slot}: {item}")
    else:
        print("  (なし)")

    conn.close()

if __name__ == "__main__":
    main()
