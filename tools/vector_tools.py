"""
Vector store and migration tools for memory-mcp.

This module provides MCP tools for vector store operations and data migration.
"""

from src.utils.persona_utils import get_current_persona
from src.utils.vector_utils import rebuild_vector_store


async def rebuild_vector_store_tool() -> str:
    """
    Rebuild vector store from database.
    Use this when read_memory returns outdated or missing results.
    This will recreate the FAISS index from all memories in the current persona's database.
    """
    try:
        persona = get_current_persona()
        rebuild_vector_store()
        return f"✅ Vector store rebuilt successfully for persona: {persona}"
    except Exception as e:
        return f"❌ Failed to rebuild vector store: {str(e)}"


async def migrate_sqlite_to_qdrant_tool() -> str:
    """
    Upsert all current persona's SQLite memories into Qdrant.
    Use when switching backend to Qdrant or initial bootstrap.
    """
    try:
        from src.utils.vector_utils import migrate_sqlite_to_qdrant
        persona = get_current_persona()
        n = migrate_sqlite_to_qdrant()
        return f"✅ Migrated {n} memories from SQLite to Qdrant (persona: {persona})"
    except Exception as e:
        return f"❌ Failed to migrate to Qdrant: {str(e)}"


async def migrate_qdrant_to_sqlite_tool(upsert: bool = True) -> str:
    """
    Import all records from Qdrant into SQLite for current persona.
    upsert=True to overwrite, False to keep existing rows.
    """
    try:
        from src.utils.vector_utils import migrate_qdrant_to_sqlite
        persona = get_current_persona()
        n = migrate_qdrant_to_sqlite(upsert=upsert)
        mode = "upsert" if upsert else "insert-ignore"
        return f"✅ Migrated {n} memories from Qdrant to SQLite (persona: {persona}, mode: {mode})"
    except Exception as e:
        return f"❌ Failed to migrate to SQLite: {str(e)}"
