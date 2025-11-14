"""
所持品管理ツール - 完全版実装

提供機能:
1. add_to_inventory: 所持品に追加
2. remove_from_inventory: 所持品から削除
3. equip_item: アイテムを装備（inventory → equipment）
4. unequip_item: 装備を解除（equipment → inventory）
5. search_inventory: 所持品検索
6. get_equipment_history: 装備履歴取得
"""

from typing import Optional
from core.equipment_db import EquipmentDB
from core.persona_context import get_current_persona, load_persona_context, save_persona_context


def add_to_inventory(
    item_name: str,
    description: str = None,
    quantity: int = 1,
    category: str = "misc"
) -> str:
    """
    所持品にアイテムを追加する。
    
    Args:
        item_name: アイテム名
        description: アイテムの説明（オプション）
        quantity: 追加する数量（デフォルト: 1）
        category: カテゴリ（weapon, armor, consumable, misc など）
    
    Returns:
        追加結果のメッセージ
    
    Examples:
        add_to_inventory("ポーション", "HP回復薬", 5, "consumable")
        add_to_inventory("銀の剣", "魔物に有効な剣", 1, "weapon")
    """
    persona = get_current_persona()
    db = EquipmentDB(persona)
    
    item_id = db.add_to_inventory(item_name, quantity, description, category)
    
    # 所持品リストを取得して確認
    inventory = db.get_inventory()
    item_data = next((i for i in inventory if i["item_id"] == item_id), None)
    
    if item_data:
        total_qty = item_data["quantity"]
        return f"✅ Added {quantity}x '{item_name}' to inventory (total: {total_qty})"
    else:
        return f"⚠️ Failed to add '{item_name}' to inventory"


def remove_from_inventory(
    item_name: str,
    quantity: int = 1
) -> str:
    """
    所持品からアイテムを削除する。
    
    Args:
        item_name: アイテム名
        quantity: 削除する数量（デフォルト: 1）
    
    Returns:
        削除結果のメッセージ
    
    Examples:
        remove_from_inventory("ポーション", 3)
        remove_from_inventory("銀の剣")
    """
    persona = get_current_persona()
    db = EquipmentDB(persona)
    
    success = db.remove_from_inventory(item_name, quantity)
    
    if success:
        return f"✅ Removed {quantity}x '{item_name}' from inventory"
    else:
        return f"❌ Item '{item_name}' not found in inventory"


def equip_item(
    item_name: str,
    slot: str
) -> str:
    """
    所持品からアイテムを装備する。
    
    アイテムは所持品に残り、persona_context.jsonのcurrent_equipmentに登録される。
    装備履歴にも記録される。
    
    Args:
        item_name: 装備するアイテム名
        slot: 装備スロット（weapon, armor, clothing, accessory など）
    
    Returns:
        装備結果のメッセージ
    
    Examples:
        equip_item("銀の剣", "weapon")
        equip_item("白いワンピース", "clothing")
    """
    persona = get_current_persona()
    db = EquipmentDB(persona)
    
    # アイテムが所持品にあるか確認
    item = db.get_item_by_name(item_name)
    if not item:
        return f"❌ Item '{item_name}' not found in database"
    
    inventory = db.get_inventory()
    if not any(i["item_name"] == item_name for i in inventory):
        return f"❌ Item '{item_name}' not in inventory. Add it first with add_to_inventory()"
    
    # persona_contextに装備を記録
    context = load_persona_context(persona)
    if "current_equipment" not in context:
        context["current_equipment"] = {}
    
    old_item = context["current_equipment"].get(slot)
    context["current_equipment"][slot] = item_name
    save_persona_context(persona, context)
    
    # 装備履歴に記録
    db.log_equipment_change(slot, item_name, "equip")
    
    if old_item:
        return f"✅ Equipped '{item_name}' to {slot} (replaced '{old_item}')"
    else:
        return f"✅ Equipped '{item_name}' to {slot}"


def unequip_item(slot: str) -> str:
    """
    装備を解除する。
    
    アイテムは所持品に残る。persona_context.jsonから装備が削除される。
    装備履歴にも記録される。
    
    Args:
        slot: 解除する装備スロット（weapon, armor, clothing, accessory など）
    
    Returns:
        解除結果のメッセージ
    
    Examples:
        unequip_item("weapon")
        unequip_item("clothing")
    """
    persona = get_current_persona()
    db = EquipmentDB(persona)
    
    # persona_contextから装備を削除
    context = load_persona_context(persona)
    if "current_equipment" not in context or slot not in context["current_equipment"]:
        return f"❌ No item equipped in slot '{slot}'"
    
    old_item = context["current_equipment"].pop(slot)
    save_persona_context(persona, context)
    
    # 装備履歴に記録
    db.log_equipment_change(slot, None, "unequip")
    
    return f"✅ Unequipped '{old_item}' from {slot}"


def search_inventory(
    query: str = None,
    category: str = None
) -> str:
    """
    所持品を検索する。
    
    Args:
        query: 検索キーワード（アイテム名に部分一致、オプション）
        category: カテゴリフィルタ（weapon, armor, consumable, misc など、オプション）
    
    Returns:
        所持品リストの整形済み文字列
    
    Examples:
        search_inventory()  # 全て表示
        search_inventory(category="weapon")  # 武器のみ
        search_inventory(query="剣")  # "剣"を含むアイテム
    """
    persona = get_current_persona()
    db = EquipmentDB(persona)
    
    inventory = db.get_inventory(category)
    
    # クエリでフィルタ
    if query:
        inventory = [
            item for item in inventory 
            if query.lower() in item["item_name"].lower() or 
               (item["description"] and query.lower() in item["description"].lower())
        ]
    
    if not inventory:
        return "📦 Inventory is empty"
    
    # 整形して出力
    lines = [f"📦 **Inventory** ({len(inventory)} items):\n"]
    for item in inventory:
        desc = f" - {item['description']}" if item["description"] else ""
        lines.append(
            f"- **{item['item_name']}** x{item['quantity']} "
            f"[{item['category']}]{desc}"
        )
    
    return "\n".join(lines)


def get_equipment_history(
    slot: str = None,
    days: int = 7
) -> str:
    """
    装備変更履歴を取得する。
    
    Args:
        slot: スロット指定（オプション、指定すると特定スロットのみ）
        days: 取得する日数（デフォルト: 7日）
    
    Returns:
        装備履歴の整形済み文字列
    
    Examples:
        get_equipment_history()  # 全スロットの7日分
        get_equipment_history(slot="weapon", days=30)  # 武器スロットの30日分
    """
    persona = get_current_persona()
    db = EquipmentDB(persona)
    
    history = db.get_equipment_history(slot, days)
    
    if not history:
        slot_str = f" for slot '{slot}'" if slot else ""
        return f"📜 No equipment history found{slot_str} in the last {days} days"
    
    # 整形して出力
    lines = [f"📜 **Equipment History** (last {days} days):\n"]
    for entry in history:
        action_icon = "⚔️" if entry["action"] == "equip" else "🔓"
        item_str = entry["item_name"] if entry["item_name"] else "(unequipped)"
        lines.append(
            f"{action_icon} {entry['timestamp'][:10]} - "
            f"{entry['slot']}: {entry['action']} '{item_str}'"
        )
    
    return "\n".join(lines)
