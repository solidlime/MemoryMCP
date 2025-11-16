#!/usr/bin/env python3
"""
SQLite Schema Migration Tool
Migrates old memory databases to include new columns (importance, equipped_items, etc.)
"""

import sqlite3
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config_utils import load_config

def migrate_database(db_path: str):
    """Migrate a single database to the latest schema."""
    print(f"🔍 Checking database: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"⚠️  Database not found: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get current columns
    cur.execute("PRAGMA table_info(memories)")
    columns = {col[1]: col[2] for col in cur.fetchall()}
    
    print(f"📋 Current columns: {list(columns.keys())}")
    
    migrations_applied = []
    
    # Define migrations
    migrations = [
        ("importance", "ALTER TABLE memories ADD COLUMN importance REAL DEFAULT 0.5"),
        ("emotion", "ALTER TABLE memories ADD COLUMN emotion TEXT DEFAULT 'neutral'"),
        ("emotion_intensity", "ALTER TABLE memories ADD COLUMN emotion_intensity REAL DEFAULT 0.5"),
        ("physical_state", "ALTER TABLE memories ADD COLUMN physical_state TEXT DEFAULT 'normal'"),
        ("mental_state", "ALTER TABLE memories ADD COLUMN mental_state TEXT DEFAULT 'calm'"),
        ("environment", "ALTER TABLE memories ADD COLUMN environment TEXT DEFAULT 'unknown'"),
        ("relationship_status", "ALTER TABLE memories ADD COLUMN relationship_status TEXT DEFAULT 'normal'"),
        ("action_tag", "ALTER TABLE memories ADD COLUMN action_tag TEXT DEFAULT NULL"),
        ("related_keys", "ALTER TABLE memories ADD COLUMN related_keys TEXT DEFAULT '[]'"),
        ("summary_ref", "ALTER TABLE memories ADD COLUMN summary_ref TEXT DEFAULT NULL"),
        ("equipped_items", "ALTER TABLE memories ADD COLUMN equipped_items TEXT DEFAULT NULL"),
    ]
    
    # Apply migrations
    for column_name, migration_sql in migrations:
        if column_name not in columns:
            print(f"  ➕ Adding column: {column_name}")
            try:
                cur.execute(migration_sql)
                migrations_applied.append(column_name)
            except sqlite3.OperationalError as e:
                print(f"  ⚠️  Failed to add {column_name}: {e}")
    
    # Special migration: Update old emotion_intensity 0.0 → 0.5
    if "emotion_intensity" in columns:
        cur.execute("UPDATE memories SET emotion_intensity = 0.5 WHERE emotion_intensity = 0.0")
        updated_count = cur.rowcount
        if updated_count > 0:
            print(f"  🔄 Updated {updated_count} records: emotion_intensity 0.0 → 0.5")
            migrations_applied.append(f"updated_emotion_intensity({updated_count})")
    
    conn.commit()
    conn.close()
    
    if migrations_applied:
        print(f"✅ Migrations applied: {', '.join(migrations_applied)}")
        return True
    else:
        print("✅ Database already up-to-date")
        return False

def migrate_all_personas():
    """Migrate all persona databases."""
    cfg = load_config()
    data_dir = cfg.get("data_dir", "./data")
    memory_root = os.path.join(data_dir, "memory")
    
    if not os.path.exists(memory_root):
        print(f"❌ Memory directory not found: {memory_root}")
        return
    
    print(f"🔍 Scanning for persona databases in: {memory_root}")
    
    # Find all persona directories
    personas = [d for d in os.listdir(memory_root) if os.path.isdir(os.path.join(memory_root, d))]
    
    if not personas:
        print("⚠️  No persona directories found")
        return
    
    print(f"📂 Found {len(personas)} persona(s): {', '.join(personas)}\n")
    
    migrated_count = 0
    for persona in personas:
        db_path = os.path.join(memory_root, persona, "memory.sqlite")
        print(f"\n{'='*60}")
        print(f"Persona: {persona}")
        print(f"{'='*60}")
        
        if migrate_database(db_path):
            migrated_count += 1
    
    print(f"\n{'='*60}")
    print(f"🎉 Migration complete!")
    print(f"   Total personas: {len(personas)}")
    print(f"   Migrated: {migrated_count}")
    print(f"   Already up-to-date: {len(personas) - migrated_count}")
    print(f"{'='*60}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate SQLite memory databases to latest schema")
    parser.add_argument("--persona", type=str, help="Migrate specific persona only")
    parser.add_argument("--db-path", type=str, help="Migrate specific database file")
    
    args = parser.parse_args()
    
    if args.db_path:
        migrate_database(args.db_path)
    elif args.persona:
        cfg = load_config()
        data_dir = cfg.get("data_dir", "./data")
        db_path = os.path.join(data_dir, "memory", args.persona, "memory.sqlite")
        migrate_database(db_path)
    else:
        migrate_all_personas()
