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

from typing import Optional
from core.equipment_db import EquipmentDB
from core.persona_context import get_current_persona, load_persona_context, save_persona_context


def add_to_inventory(
    item_name: str,
    description: str = None,
    quantity: int = 1,
    category: str = "misc"
) -> str:
    """Add item to inventory.
    
    Args:
        item_name: Item name
        description: Item description (optional)
        quantity: Quantity to add (default: 1)
        category: Category (weapon, armor, consumable, clothing, accessory, misc)
    
    Returns:
        Result message
    
    Examples:
        add_to_inventory("Health Potion", "Restores HP", 5, "consumable")
        add_to_inventory("Steel Sword", "Sharp blade", 1, "weapon")
    """
    persona = get_current_persona()
    db = EquipmentDB(persona)
    
    item_id = db.add_to_inventory(item_name, quantity, description, category)
    
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
    item_name: str,
    slot: str
) -> str:
    """Equip item from inventory.
    
    Item remains in inventory. Updates persona_context.json current_equipment.
    Logs to equipment history.
    
    Args:
        item_name: Item name to equip
        slot: Equipment slot (weapon, armor, clothing, accessory, etc.)
    
    Returns:
        Result message
    
    Examples:
        equip_item("Steel Sword", "weapon")
        equip_item("Leather Armor", "armor")
    """
    persona = get_current_persona()
    db = EquipmentDB(persona)
    
    # Check if item exists in database
    item = db.get_item_by_name(item_name)
    if not item:
        return f"❌ Item '{item_name}' not found in database"
    
    inventory = db.get_inventory()
    if not any(i["item_name"] == item_name for i in inventory):
        return f"❌ Item '{item_name}' not in inventory. Add it first with add_to_inventory()"
    
    # Update persona_context
    context = load_persona_context(persona)
    if "current_equipment" not in context:
        context["current_equipment"] = {}
    
    old_item = context["current_equipment"].get(slot)
    context["current_equipment"][slot] = item_name
    save_persona_context(context, persona)
    
    # Log to history
    db.log_equipment_change(slot, item_name, "equip")
    
    if old_item:
        return f"✅ Equipped '{item_name}' to {slot} (replaced '{old_item}')"
    else:
        return f"✅ Equipped '{item_name}' to {slot}"


def unequip_item(slot: str) -> str:
    """Unequip item.
    
    Item remains in inventory. Removes from persona_context.json.
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
    
    # Remove from persona_context
    context = load_persona_context(persona)
    if "current_equipment" not in context or slot not in context["current_equipment"]:
        return f"❌ No item equipped in slot '{slot}'"
    
    old_item = context["current_equipment"].pop(slot)
    save_persona_context(context, persona)
    
    # Log to history
    db.log_equipment_change(slot, None, "unequip")
    
    return f"✅ Unequipped '{old_item}' from {slot}"


def update_item_info(
    item_name: str,
    description: str = None,
    category: str = None
) -> str:
    """Update item information.
    
    Args:
        item_name: Item name to update
        description: New description (optional)
        category: New category (optional)
    
    Returns:
        Result message
    
    Examples:
        update_item_info("Steel Sword", description="A very sharp blade")
        update_item_info("Health Potion", category="consumable")
        update_item_info("Magic Ring", "Increases mana", "accessory")
    """
    persona = get_current_persona()
    db = EquipmentDB(persona)
    
    success = db.update_item_info(item_name, description, category)
    
    if success:
        updates = []
        if description is not None:
            updates.append("description")
        if category is not None:
            updates.append("category")
        return f"✅ Updated {', '.join(updates)} for '{item_name}'"
    else:
        return f"❌ Item '{item_name}' not found"


def change_equipment_slot(
    item_name: str,
    new_slot: str
) -> str:
    """Change equipment slot for equipped item.
    
    Args:
        item_name: Item name currently equipped
        new_slot: New equipment slot
    
    Returns:
        Result message
    
    Examples:
        change_equipment_slot("Steel Sword", "accessory")
        change_equipment_slot("Magic Ring", "weapon")
    """
    persona = get_current_persona()
    db = EquipmentDB(persona)
    
    # Find current slot
    context = load_persona_context(persona)
    if "current_equipment" not in context:
        return f"❌ Item '{item_name}' is not equipped"
    
    old_slot = None
    for slot, equipped_item in context["current_equipment"].items():
        if equipped_item == item_name:
            old_slot = slot
            break
    
    if not old_slot:
        return f"❌ Item '{item_name}' is not equipped"
    
    if old_slot == new_slot:
        return f"⚠️ Item '{item_name}' is already in slot '{new_slot}'"
    
    # Move to new slot
    context["current_equipment"].pop(old_slot)
    old_item_in_new_slot = context["current_equipment"].get(new_slot)
    context["current_equipment"][new_slot] = item_name
    save_persona_context(context, persona)
    
    # Log changes
    db.log_equipment_change(old_slot, None, "unequip")
    db.log_equipment_change(new_slot, item_name, "equip")
    
    if old_item_in_new_slot:
        return f"✅ Moved '{item_name}' from {old_slot} to {new_slot} (replaced '{old_item_in_new_slot}')"
    else:
        return f"✅ Moved '{item_name}' from {old_slot} to {new_slot}"


def search_inventory(
    query: str = None,
    category: str = None
) -> str:
    """Search inventory.
    
    Args:
        query: Search keyword (partial match on item name, optional)
        category: Category filter (weapon, armor, consumable, clothing, accessory, misc)
    
    Returns:
        Formatted inventory list
    
    Examples:
        search_inventory()  # Show all
        search_inventory(category="weapon")  # Weapons only
        search_inventory(query="sword")  # Items containing "sword"
    """
    persona = get_current_persona()
    db = EquipmentDB(persona)
    
    inventory = db.get_inventory(category)
    
    # Filter by query
    if query:
        inventory = [
            item for item in inventory 
            if query.lower() in item["item_name"].lower() or 
               (item["description"] and query.lower() in item["description"].lower())
        ]
    
    if not inventory:
        return "📦 Inventory is empty"
    
    # Format output
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
