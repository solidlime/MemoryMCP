#!/usr/bin/env python3
"""
Migrate all memories from local SQLite to production MCP server
"""
import sqlite3
import json
import requests
from datetime import datetime

LOCAL_DB = "memory/nilou/memory.sqlite"
PROD_MCP_URL = "http://nas:26262/mcp"
PERSONA = "nilou"

def get_local_memories():
    """Get all memories from local SQLite"""
    conn = sqlite3.connect(LOCAL_DB)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT key, content, created_at, updated_at, tags 
        FROM memories 
        ORDER BY created_at
    ''')
    memories = []
    for row in cursor.fetchall():
        memories.append({
            'key': row[0],
            'content': row[1],
            'created_at': row[2],
            'updated_at': row[3],
            'tags': json.loads(row[4]) if row[4] else []
        })
    conn.close()
    return memories

def create_memory_via_mcp(content, tags=None):
    """Create memory via MCP server"""
    # Note: This won't work with current MCP protocol via curl
    # We'll use direct API if available, or need to use MCP client
    print(f"Would create: {content[:80]}...")
    print(f"  Tags: {tags}")
    return True

def main():
    print("🔄 Starting memory migration...")
    memories = get_local_memories()
    print(f"📊 Found {len(memories)} memories to migrate")
    
    for i, mem in enumerate(memories, 1):
        print(f"\n[{i}/{len(memories)}] Migrating {mem['key']}...")
        print(f"  Content: {mem['content'][:80]}...")
        print(f"  Tags: {mem['tags']}")
        print(f"  Created: {mem['created_at']}")
        
        # TODO: Implement actual MCP client call
        # For now, just print what would be migrated
    
    print("\n✅ Migration plan generated!")
    print(f"📝 Total: {len(memories)} memories")
    print("\n⚠️  Note: Actual migration requires MCP client implementation")

if __name__ == "__main__":
    main()
