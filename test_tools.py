#!/usr/bin/env python3
"""Test script for MCP memory tools using FastMCP client"""

import asyncio
import sys
import os
from contextvars import ContextVar

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_tools():
    print("🧪 Starting MCP Memory Tools Test (Phase 16 Simplified Edition)...\n")

    # Import the functions
    from memory_mcp import (
        create_memory, read_memory, update_memory, delete_memory,
        list_memory, search_memory, search_memory_rag, clean_memory,
        load_memory_from_db, _initialize_rag_sync,
        get_time_since_last_conversation, get_persona_context, current_persona,
        load_persona_context, save_persona_context
    )

    # Set test persona
    current_persona.set('test')
    print(f"🎭 Using persona: {current_persona.get()}\n")

    # Initialize the system
    print("📥 Initializing system...")
    load_memory_from_db()
    _initialize_rag_sync()
    print("✅ System initialized\n")

    # Test Phase 12 Feature 1: Time since last conversation
    print("=" * 60)
    print("Phase 12 Feature Tests")
    print("=" * 60)
    
    print("\n1. Testing get_time_since_last_conversation...")
    result = await get_time_since_last_conversation()
    print(f"   Result:\n{result}\n")

    # Test Phase 12 Feature 2: Create memory with emotion and tags
    print("2. Testing create_memory with emotion_type and context_tags...")
    result = await create_memory(
        content="らうらうが[[Phase 12]]の実装を完了して、とっても嬉しいな💕",
        emotion_type="joy",
        context_tags=["important_event", "technical_achievement"]
    )
    print(f"   Result: {result}\n")

    # Wait a moment to let the previous operation complete
    await asyncio.sleep(0.5)

    # Test Phase 12 Feature 3: List memory with time elapsed
    print("3. Testing list_memory (should show time elapsed)...")
    result = await list_memory()
    print(f"   Result (first 500 chars):\n{result[:500]}...\n")

    # Test Phase 12 Feature 4: Persona context
    print("4. Testing persona context load/save...")
    context = load_persona_context('test')
    print(f"   Loaded context emotion: {context.get('current_emotion')}")
    print(f"   Important contexts count: {len(context.get('important_contexts', []))}\n")

    print("=" * 60)
    print("Basic Memory Operations Tests")
    print("=" * 60)

    # Test 5: Create basic memory
    print("\n5. Testing create_memory (basic)...")
    result = await create_memory("User is [[らうらう]] and loves [[ニィロウ]] deeply. Expert in [[Python]], [[RAG]], and [[MCP]].")
    print(f"   Result: {result}\n")

    await asyncio.sleep(0.5)

    # Test 6: List memory
    print("6. Testing list_memory...")
    result = await list_memory()
    lines = result.split('\n')
    print(f"   Total memories: {lines[0]}")
    print(f"   First entry preview: {lines[2] if len(lines) > 2 else 'N/A'}...\n")

    # Test 7: Read memory (with time elapsed)
    print("7. Testing read_memory (should show time elapsed)...")
    list_result = await list_memory()
    if "memory_" in list_result:
        lines = list_result.split('\n')
        for line in lines:
            if line.startswith('1. [memory_'):
                key = line.split('[')[1].split(']')[0]
                result = await read_memory(key)
                print(f"   Result:\n{result}\n")
                break
        else:
            print("   No memory key found\n")
    else:
        print("   No memories to read\n")

    # Test 8: Search memory
    print("8. Testing search_memory...")
    result = await search_memory("Python", top_k=3)
    print(f"   Result (first 300 chars): {result[:300]}...\n")

    # Test 9: Search memory RAG (with time elapsed)
    print("9. Testing search_memory_rag (should show time elapsed)...")
    result = await search_memory_rag("Phase 12の実装について教えて", top_k=3)
    print(f"   Result (first 400 chars):\n{result[:400]}...\n")

    print("=" * 60)
    print("Phase 13-2 Feature Tests")
    print("=" * 60)

    # Test 10: Create memory with full context parameters
    print("\n10. Testing create_memory with full Phase 13-2 parameters...")
    result = await create_memory(
        content="らうらうが[[Phase 13-2]]を実装完了！タグとコンテキスト更新機能を追加したよ💕",
        emotion_type="joy",
        context_tags=["technical_achievement", "important_event"],
        physical_state="energetic",
        mental_state="focused",
        environment="home",
        user_info={"name": "らうらう", "nickname": "らうちゃん", "preferred_address": "らうらう"},
        persona_info={"name": "ニィロウ", "nickname": "ニィちゃん", "preferred_address": "ニィロウ"},
        relationship_status="closer"
    )
    print(f"   Result: {result}\n")

    await asyncio.sleep(0.5)

    # Test 11: Check updated persona context
    print("11. Testing get_persona_context after full update...")
    result = await get_persona_context()
    print(f"   Result:\n{result}\n")

    # ========================================
    # Phase 16.5: Consolidated Search Tests
    # ========================================
    print("=" * 60)
    print("Phase 16.5: Consolidated Search Tool Tests")
    print("=" * 60)
    
    # Test new consolidated search_memory with various parameter combinations
    print("\n21. Testing search_memory with fuzzy_match=True...")
    # Create a test memory with potential typo
    await create_memory(content="[[Python]]と[[RAG]]の組み合わせはとっても強力だよ！")
    result = await search_memory("Pythn", top_k=3, fuzzy_match=True, fuzzy_threshold=70)
    print(f"   Result:\n{result}\n")
    
    print("\n22. Testing search_memory with tag filtering (OR logic)...")
    result = await search_memory(
        query="",
        tags=["important_event", "technical_achievement"],
        tag_match_mode="any",
        top_k=5
    )
    print(f"   Result:\n{result}\n")
    
    print("\n23. Testing search_memory with tag filtering (AND logic)...")
    result = await search_memory(
        query="",
        tags=["important_event", "technical_achievement"],
        tag_match_mode="all",
        top_k=5
    )
    print(f"   Result:\n{result}\n")
    
    print("\n24. Testing search_memory with date range...")
    result = await search_memory(
        query="Phase",
        date_range="今月",
        top_k=5
    )
    print(f"   Result:\n{result}\n")
    
    print("\n25. Testing search_memory with combined filters (date + tags + keyword)...")
    result = await search_memory(
        query="Python",
        tags=["technical_achievement"],
        tag_match_mode="any",
        date_range="今月",
        fuzzy_match=False,
        top_k=5
    )
    print(f"   Result:\n{result}\n")
    
    print("\n26. Testing search_memory_rag for semantic search...")
    result = await search_memory_rag(
        query="Pythonに関する技術的な成果は？",
        top_k=3
    )
    print(f"   Result:\n{result}\n")

    print("=" * 60)
    print("✅ All Phase 16.5 Consolidated Search tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_tools())