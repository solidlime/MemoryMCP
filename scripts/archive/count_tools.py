#!/usr/bin/env python3
"""
Count tools before and after consolidation
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Before consolidation
before_tools = [
    "get_context",
    "create_memory",
    "update_memory",
    "search_memory",
    "delete_memory",
    "add_to_inventory",
    "remove_from_inventory",
    "equip_item",
    "update_item",
    "search_inventory",
    "get_equipment_history",
    "analyze_item",
]

# After consolidation
after_tools = [
    "get_context",
    "memory",  # Replaces: create_memory, update_memory, search_memory, delete_memory (+ stats operation)
    "item",    # Replaces: add_to_inventory, remove_from_inventory, equip_item, update_item, 
               #           search_inventory, get_equipment_history, analyze_item (+ memories, stats operations)
]

print("=" * 60)
print("🔧 Tool Consolidation Analysis")
print("=" * 60)

print(f"\n📊 Before consolidation: {len(before_tools)} tools")
for i, tool in enumerate(before_tools, 1):
    print(f"  {i:2d}. {tool}")

print(f"\n📊 After consolidation: {len(after_tools)} tools")
for i, tool in enumerate(after_tools, 1):
    print(f"  {i:2d}. {tool}")

reduction = len(before_tools) - len(after_tools)
percentage = (reduction / len(before_tools)) * 100

print(f"\n✨ Reduction: {reduction} tools ({percentage:.1f}%)")
print(f"   {len(before_tools)} → {len(after_tools)} tools")

print("\n" + "=" * 60)
print("💡 Context Savings:")
print("   - Each tool definition includes full schema information")
print("   - Consolidation reduces repetitive parameter definitions")
print("   - Estimated context reduction: ~70-80%")
print("=" * 60)
