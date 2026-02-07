#!/usr/bin/env python3
"""persona と DBパスの確認"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.persona_utils import get_current_persona
from core.equipment_db import EquipmentDB, get_equipment_db_path

def main():
    print("=== Persona & DB Path 確認 ===\n")

    # Case 1: 環境変数なし
    print("【Case 1: 環境変数なし】")
    if 'PERSONA' in os.environ:
        del os.environ['PERSONA']

    try:
        persona1 = get_current_persona()
        print(f"  persona: {persona1}")
        db_path1 = get_equipment_db_path(persona1)
        print(f"  DB path: {db_path1}")
        print(f"  DB exists: {os.path.exists(db_path1)}")

        db1 = EquipmentDB(persona1)
        equipped1 = db1.get_equipped_items()
        print(f"  装備数: {len(equipped1)}")
        for slot, item in list(equipped1.items())[:3]:
            print(f"    {slot}: {item}")
    except Exception as e:
        print(f"  エラー: {e}")

    print("\n" + "="*50 + "\n")

    # Case 2: 環境変数 PERSONA=nilou
    print("【Case 2: PERSONA=nilou】")
    os.environ['PERSONA'] = 'nilou'

    try:
        persona2 = get_current_persona()
        print(f"  persona: {persona2}")
        db_path2 = get_equipment_db_path(persona2)
        print(f"  DB path: {db_path2}")
        print(f"  DB exists: {os.path.exists(db_path2)}")

        db2 = EquipmentDB(persona2)
        equipped2 = db2.get_equipped_items()
        print(f"  装備数: {len(equipped2)}")
        for slot, item in list(equipped2.items())[:3]:
            print(f"    {slot}: {item}")
    except Exception as e:
        print(f"  エラー: {e}")

    print("\n" + "="*50 + "\n")

    # Case 3: 明示的に"nilou"を指定
    print("【Case 3: 明示的に\"nilou\"を指定】")
    persona3 = "nilou"
    db_path3 = get_equipment_db_path(persona3)
    print(f"  persona: {persona3}")
    print(f"  DB path: {db_path3}")
    print(f"  DB exists: {os.path.exists(db_path3)}")

    db3 = EquipmentDB(persona3)
    equipped3 = db3.get_equipped_items()
    print(f"  装備数: {len(equipped3)}")
    for slot, item in equipped3.items():
        print(f"    {slot}: {item}")

    print("\n" + "="*50 + "\n")

    # 既存のequipment.dbを探す
    print("【既存のequipment.dbを探す】")
    memory_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memory")
    print(f"  memory dir: {memory_dir}")

    for root, dirs, files in os.walk(memory_dir):
        for file in files:
            if file == "equipment.db":
                full_path = os.path.join(root, file)
                print(f"  見つかった: {full_path}")

if __name__ == "__main__":
    main()
