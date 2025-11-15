"""Equipment Management Tools - Full Implementation

Provides:
1. add_to_inventory: Add items to inventory
2. remove_from_inventory: Remove items from inventory
3. equip_item: Equip items (inventory → equipment)
4. unequip_item: Unequip items (equipment → persona_context)
5. update_item_info: Update item description/category
6. change_equipment_slot: Change equipment slot for equipped item
7. search_inventory: Search inventory
8. get_equipment_history: Get equipment change history
"""

from typing import Optional, Tuple
from core.equipment_db import EquipmentDB
from core.persona_context import get_current_persona, load_persona_context, save_persona_context


def add_to_inventory(
    item_name: str,
    description: str = None,
    quantity: int = 1,
    category: str = "misc",
    tags: list = None
) -> str:
    """Add item to inventory.
    
    Args:
        item_name: Item name
        description: Item description (optional)
        quantity: Quantity to add (default: 1)
        category: Category (weapon, armor, consumable, clothing, accessory, misc)
        tags: Tags for grouping items (optional, e.g., ["星月の祈り", "clothing_set"])
    
    Returns:
        Result message
    
    Examples:
        add_to_inventory("Health Potion", "Restores HP", 5, "consumable")
        add_to_inventory("Steel Sword", "Sharp blade", 1, "weapon")
        add_to_inventory("White Dress", "Beautiful dress", 1, "clothing", ["星月の祈り"])
    """
    persona = get_current_persona()
    db = EquipmentDB(persona)
    
    item_id = db.add_to_inventory(item_name, quantity, description, category, tags)
    
    inventory = db.get_inventory()
    item_data = next((i for i in inventory if i["item_id"] == item_id), None)
    
    if item_data:
        total_qty = item_data["quantity"]
        tags_str = f" 🏷️{tags}" if tags else ""
        return f"✅ Added {quantity}x '{item_name}' to inventory (total: {total_qty}){tags_str}"
    else:
        return f"⚠️ Failed to add '{item_name}' to inventory"


def remove_from_inventory(
    item_name: str,
    quantity: int = 1
) -> str:
    """Remove item from inventory.
    
    Args:
        item_name: Item name
        quantity: Quantity to remove (default: 1)
    
    Returns:
        Result message
    
    Examples:
        remove_from_inventory("Health Potion", 3)
        remove_from_inventory("Steel Sword")
    """
    persona = get_current_persona()
    db = EquipmentDB(persona)
    
    success = db.remove_from_inventory(item_name, quantity)
    
    if success:
        return f"✅ Removed {quantity}x '{item_name}' from inventory"
    else:
        return f"❌ Item '{item_name}' not found in inventory"


def equip_item(
    equipment: dict[str, str]
) -> str:
    """Equip items from inventory (batch mode).
    
    Unequips all current equipment first, then equips specified items.
    Prevents forgetting to unequip previous items when changing outfits.
    
    Args:
        equipment: Dictionary of {slot: item_name}
                   Example: {"top": "囁きのシフォンドレス", "foot": "蓮花サンダル"}
    
    Returns:
        Result message
    
    Examples:
        equip_item({"weapon": "Steel Sword", "armor": "Leather Armor"})
        equip_item({"top": "白いドレス", "foot": "サンダル"})
    """
    persona = get_current_persona()
    db = EquipmentDB(persona)
    
    # Check if all items exist in inventory
    inventory = db.get_inventory()
    inventory_items = {i["item_name"] for i in inventory}
    
    missing_items = []
    for slot, item_name in equipment.items():
        if item_name and item_name not in inventory_items:
            missing_items.append(item_name)
    
    if missing_items:
        return f"❌ Items not in inventory: {', '.join(missing_items)}. Add them first with add_to_inventory()"
    
    # Unequip all current equipment
    unequipped = db.unequip_all()
    
    # Equip new items
    results = db.equip_items_batch(equipment)
    
    # Format result message
    success_items = [f"{slot}: {item}" for slot, item in equipment.items() if results.get(slot, False)]
    failed_items = [f"{slot}: {item}" for slot, item in equipment.items() if not results.get(slot, True)]
    
    message_parts = []
    if unequipped:
        unequipped_str = ", ".join([f"{slot}({item})" for slot, item in unequipped])
        message_parts.append(f"🔄 Unequipped: {unequipped_str}")
    
    if success_items:
        message_parts.append(f"✅ Equipped: {', '.join(success_items)}")
    
    if failed_items:
        message_parts.append(f"❌ Failed: {', '.join(failed_items)}")
    
    return "\n".join(message_parts) if message_parts else "✅ Equipment reset completed"


def unequip_item(
    slot: str
) -> str:
    """Unequip item.
    
    Item remains in inventory. Removes equipment from database.
    Logs to equipment history.
    
    Args:
        slot: Equipment slot to unequip (weapon, armor, clothing, accessory, etc.)
    
    Returns:
        Result message
    
    Examples:
        unequip_item("weapon")
        unequip_item("armor")
    """
    persona = get_current_persona()
    db = EquipmentDB(persona)
    
    # Unequip from database
    item_name = db.unequip_item(slot)
    
    if item_name:
        return f"✅ Unequipped '{item_name}' from {slot}"
    else:
        return f"❌ No item equipped in slot '{slot}'"


def update_item(
    item_name: str,
    description: str = None,
    category: str = None,
    tags: list = None,
    new_slot: str = None
) -> str:
    """Update item information and/or change equipment slot.
    
    Can update item metadata (description, category, tags) and change equipped slot.
    All parameters are optional - specify only what you want to change.
    
    Args:
        item_name: Item name to update
        description: New description (optional)
        category: New category (optional)
        tags: New tags list (optional)
        new_slot: New equipment slot if currently equipped (optional)
    
    Returns:
        Result message
    
    Examples:
        update_item("Steel Sword", description="A very sharp blade")
        update_item("Health Potion", category="consumable", tags=["healing"])
        update_item("White Dress", tags=["星月の祈り", "clothing_set"])
        update_item("Magic Ring", new_slot="weapon")  # Change equipped slot
    """
    persona = get_current_persona()
    db = EquipmentDB(persona)
    
    updates = []
    
    # Update item metadata
    if description is not None or category is not None or tags is not None:
        success = db.update_item_info(item_name, description, category, tags)
        if not success:
            return f"❌ Item '{item_name}' not found"
        
        if description is not None:
            updates.append("description")
        if category is not None:
            updates.append("category")
        if tags is not None:
            updates.append("tags")
    
    # Change equipment slot if specified
    if new_slot is not None:
        # Check if item is currently equipped
        equipped = db.get_equipped_items()
        old_slot = None
        for slot, name in equipped.items():
            if name == item_name:
                old_slot = slot
                break
        
        if not old_slot:
            return f"❌ Item '{item_name}' is not equipped"
        
        if old_slot == new_slot:
            return f"⚠️ Item '{item_name}' is already in slot '{new_slot}'"
        
        # Unequip from old slot and equip to new slot
        db.unequip_item(old_slot)
        db.equip_item(item_name, new_slot)
        updates.append(f"slot: {old_slot} → {new_slot}")
    
    if updates:
        return f"✅ Updated {', '.join(updates)} for '{item_name}'"
    else:
        return f"⚠️ No changes specified for '{item_name}'"


def search_inventory(
    query: str = None,
    category: str = None,
    tags: list = None
) -> str:
    """Search inventory.
    
    Args:
        query: Search keyword (partial match on item name, description, and tags)
        category: Category filter (weapon, armor, consumable, clothing, accessory, misc)
        tags: Tag filter (match any of the specified tags, optional)
    
    Returns:
        Formatted inventory list
    
    Examples:
        search_inventory()  # Show all
        search_inventory(category="weapon")  # Weapons only
        search_inventory(query="sword")  # Items containing "sword" in name, desc, or tags
        search_inventory(tags=["星月の祈り"])  # Items with specific tag
    """
    persona = get_current_persona()
    db = EquipmentDB(persona)
    
    inventory = db.get_inventory(category, tags)
    
    # Filter by query - search in name, description, AND tags
    if query:
        inventory = [
            item for item in inventory 
            if query.lower() in item["item_name"].lower() or 
               (item["description"] and query.lower() in item["description"].lower()) or
               any(query.lower() in tag.lower() for tag in item.get("tags", []))
        ]
    
    if not inventory:
        return "📦 Inventory is empty"
    
    # Format output
    lines = [f"📦 **Inventory** ({len(inventory)} items):\n"]
    for item in inventory:
        desc = f" - {item['description']}" if item["description"] else ""
        tags_str = f" 🏷️{item['tags']}" if item.get('tags') else ""
        equipped_str = f" ⚔️[{item['equipped_slot']}]" if item.get('is_equipped') else ""
        lines.append(
            f"- **{item['item_name']}** x{item['quantity']} "
            f"[{item['category']}]{desc}{tags_str}{equipped_str}"
        )
    
    return "\n".join(lines)


def get_equipment_history(
    slot: str = None,
    days: int = 7
) -> str:
    """Get equipment change history.
    
    Args:
        slot: Slot filter (optional, shows specific slot only)
        days: Number of days to retrieve (default: 7)
    
    Returns:
        Formatted equipment history
    
    Examples:
        get_equipment_history()  # All slots, last 7 days
        get_equipment_history(slot="weapon", days=30)  # Weapon slot, last 30 days
    """
    persona = get_current_persona()
    db = EquipmentDB(persona)
    
    history = db.get_equipment_history(slot, days)
    
    if not history:
        slot_str = f" for slot '{slot}'" if slot else ""
        return f"📜 No equipment history found{slot_str} in the last {days} days"
    
    # Format output
    lines = [f"📜 **Equipment History** (last {days} days):\n"]
    for entry in history:
        action_icon = "⚔️" if entry["action"] == "equip" else "🔓"
        item_str = entry["item_name"] if entry["item_name"] else "(unequipped)"
        lines.append(
            f"{action_icon} {entry['timestamp'][:10]} - "
            f"{entry['slot']}: {entry['action']} '{item_str}'"
        )
    
    return "\n".join(lines)
