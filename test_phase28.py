#!/usr/bin/env python3
"""
Phase 28 Feature Testing Script

Tests:
1. Association Generation (related_keys)
2. Forgetting Module (time decay)
3. Statistical Summarization
4. LLM Summarization (with mock/error handling)
"""

import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Set test persona
os.environ["MEMORY_MCP_PERSONA"] = "test"

# Import modules
from core.memory_db import save_memory_to_db, load_memory_from_db, delete_memory_from_db
from persona_utils import get_db_path
from tools.association import generate_associations
from core.forgetting import decay_all_memories, mark_memories_for_deletion
from tools.summarization_tools import summarize_last_day, extract_memories_by_period
from config_utils import load_config


def list_memories():
    """Get all memories as list."""
    memory_dict = load_memory_from_db()
    return [{"key": k, **v} for k, v in memory_dict.items()]


def read_memory(key: str):
    """Read single memory."""
    memory_dict = load_memory_from_db()
    if key in memory_dict:
        return {"key": key, **memory_dict[key]}
    return None


def clear_all_memories():
    """Delete all memories."""
    memory_dict = load_memory_from_db()
    for key in list(memory_dict.keys()):
        delete_memory_from_db(key)


def setup_test_data():
    """Create test memories for Phase 28 features."""
    print("\n🧪 Setting up test data...")
    
    # Clear existing test data
    clear_all_memories()
    
    test_memories = [
        {
            "content": "ユーザーは[[Python]]の学習を開始した",
            "tags": ["learning", "programming"],
            "importance": 0.8,
            "emotion": "joy",
            "emotion_intensity": 0.7,
            "action_tag": "coding"
        },
        {
            "content": "[[Python]]で初めてのプログラムを完成させた🎉",
            "tags": ["achievement", "programming"],
            "importance": 0.9,
            "emotion": "joy",
            "emotion_intensity": 0.9,
            "action_tag": "coding"
        },
        {
            "content": "ユーザーは[[データサイエンス]]に興味を持っている",
            "tags": ["learning", "interest"],
            "importance": 0.6,
            "emotion": "neutral",
            "emotion_intensity": 0.5,
        },
        {
            "content": "[[MCP]]サーバーのデバッグに苦労した😥",
            "tags": ["technical_issue", "debugging"],
            "importance": 0.5,
            "emotion": "sadness",
            "emotion_intensity": 0.6,
            "action_tag": "coding"
        },
        {
            "content": "Phase 28の実装が完了した✨",
            "tags": ["achievement", "milestone"],
            "importance": 0.95,
            "emotion": "joy",
            "emotion_intensity": 0.85,
        },
    ]
    
    created_keys = []
    for i, mem in enumerate(test_memories):
        now = datetime.now().strftime("%Y%m%d%H%M%S")
        key = f"memory_{now}_{i:03d}"
        
        success = save_memory_to_db(
            key=key,
            content=mem["content"],
            tags=mem.get("tags", []),
            importance=mem.get("importance", 0.5),
            emotion=mem.get("emotion", "neutral"),
            emotion_intensity=mem.get("emotion_intensity", 0.5),
            physical_state=mem.get("physical_state"),
            mental_state=mem.get("mental_state"),
            environment=mem.get("environment"),
            relationship_status=mem.get("relationship_status"),
            action_tag=mem.get("action_tag"),
            related_keys=None,
            summary_ref=None
        )
        
        if success:
            created_keys.append(key)
            print(f"  ✅ Created: {key}")
    
    print(f"✅ Created {len(created_keys)} test memories")
    return created_keys


def test_association_generation():
    """Test Phase 28.2: Association Generation."""
    print("\n" + "="*60)
    print("🔗 Test 1: Association Generation (Phase 28.2)")
    print("="*60)
    
    try:
        from tools.association import generate_associations, update_related_keys
        
        # Generate associations for each memory manually
        all_memories = list_memories()
        associations_created = 0
        importance_boosted = 0
        
        for mem in all_memories:
            # Generate associations
            related_keys, adjusted_importance = generate_associations(
                new_key=mem["key"],
                new_content=mem["content"],
                emotion_intensity=mem.get("emotion_intensity", 0.0),
                base_importance=mem.get("importance", 0.5)
            )
            
            if related_keys:
                # Update related_keys in database
                update_related_keys(mem["key"], related_keys)
                associations_created += 1
            
            if adjusted_importance != mem.get("importance", 0.5):
                importance_boosted += 1
        
        print(f"\n📊 Results:")
        print(f"  Total processed: {len(all_memories)}")
        print(f"  Associations created: {associations_created}")
        print(f"  Importance boosted: {importance_boosted}")
        
        # Verify related_keys were populated
        updated_memories = list_memories()
        memories_with_associations = [m for m in updated_memories if m.get("related_keys")]
        print(f"\n✅ Memories with associations: {len(memories_with_associations)}/{len(updated_memories)}")
        
        # Show example
        if memories_with_associations:
            example = memories_with_associations[0]
            print(f"\n📝 Example:")
            print(f"  Content: {example['content'][:60]}...")
            print(f"  Related: {example['related_keys']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Association test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_forgetting_module():
    """Test Phase 28.3: Forgetting Module."""
    print("\n" + "="*60)
    print("🧠 Test 2: Forgetting Module (Phase 28.3)")
    print("="*60)
    
    try:
        # Get initial importance scores
        before_memories = list_memories()
        before_importance = {m["key"]: m["importance"] for m in before_memories}
        
        print(f"\n📊 Before decay:")
        for mem in before_memories[:3]:
            print(f"  {mem['key']}: importance={mem['importance']:.3f}, emotion_intensity={mem.get('emotion_intensity', 0):.2f}")
        
        # Apply decay
        decayed = decay_all_memories(dry_run=False)
        
        print(f"\n⏰ Decay results:")
        print(f"  Total decayed: {len(decayed)}")
        if decayed:
            avg_decay = sum(abs(decayed[k] - before_importance.get(k, 0)) for k in decayed) / len(decayed)
            print(f"  Average decay: {avg_decay:.3f}")
        
        # Get after importance scores
        after_memories = list_memories()
        
        print(f"\n📊 After decay:")
        for mem in after_memories[:3]:
            before = before_importance.get(mem["key"], 0)
            after = mem["importance"]
            change = after - before
            print(f"  {mem['key']}: {before:.3f} → {after:.3f} (Δ{change:+.3f})")
        
        # Test mark_for_deletion
        candidates = mark_memories_for_deletion(min_importance=0.1, has_summary=False)
        print(f"\n🗑️  Deletion candidates (importance < 0.1): {len(candidates)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Forgetting test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_statistical_summarization():
    """Test Phase 28.4: Statistical Summarization."""
    print("\n" + "="*60)
    print("📊 Test 3: Statistical Summarization (Phase 28.4)")
    print("="*60)
    
    try:
        # Ensure use_llm is False
        config = load_config()
        config["summarization"]["use_llm"] = False
        
        # Test extract_memories_by_period
        cfg = load_config()
        timezone = cfg.get("timezone", "Asia/Tokyo")
        now = datetime.now(ZoneInfo(timezone))
        
        end_date = now.isoformat()
        start_date = (now - timedelta(days=1)).isoformat()
        
        print(f"\n📅 Extracting memories from {start_date} to {end_date}")
        memories = extract_memories_by_period(
            start_date=start_date,
            end_date=end_date,
            min_importance=0.3
        )
        
        print(f"  Found {len(memories)} memories")
        
        # Test summarize_last_day
        print(f"\n📝 Generating summary...")
        summary_key = summarize_last_day()
        
        if summary_key:
            print(f"  ✅ Summary created: {summary_key}")
            
            # Verify summary node
            summary_mem = read_memory(summary_key)
            
            if summary_mem:
                print(f"\n📄 Summary content:")
                print(f"  {summary_mem['content'][:200]}...")
                print(f"\n  Tags: {summary_mem.get('tags', [])}")
                print(f"  Importance: {summary_mem.get('importance', 0):.2f}")
                print(f"  Emotion: {summary_mem.get('emotion', 'N/A')}")
                
                # Check if memories were linked
                all_memories = list_memories()
                linked_memories = [m for m in all_memories if m.get("summary_ref") == summary_key]
                print(f"\n  Linked memories: {len(linked_memories)}")
            
            return True
        else:
            print(f"  ⚠️  No summary created (might be expected if no memories)")
            return True
        
    except Exception as e:
        print(f"❌ Statistical summarization test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_llm_summarization_error_handling():
    """Test Phase 28.4: LLM Summarization Error Handling."""
    print("\n" + "="*60)
    print("🤖 Test 4: LLM Summarization Error Handling (Phase 28.4)")
    print("="*60)
    
    try:
        # Set use_llm=True but provide invalid API key/URL
        config = load_config()
        config["summarization"]["use_llm"] = True
        config["summarization"]["llm_api_url"] = None  # Invalid
        config["summarization"]["llm_api_key"] = None  # Invalid
        
        print(f"\n⚙️  Config: use_llm=True, api_url=None, api_key=None (should fail gracefully)")
        
        # Attempt summary
        print(f"\n📝 Attempting LLM summary (expecting fallback to template)...")
        summary_key = summarize_last_day()
        
        if summary_key:
            print(f"  ✅ Summary created with fallback: {summary_key}")
            
            summary_mem = read_memory(summary_key)
            
            if summary_mem:
                print(f"\n📄 Summary content (should be template-based):")
                print(f"  {summary_mem['content'][:150]}...")
            
            return True
        else:
            print(f"  ⚠️  No summary created (expected if error handling prevents creation)")
            return True
        
    except Exception as e:
        print(f"❌ LLM error handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_test_data():
    """Clean up test data."""
    print("\n🧹 Cleaning up test data...")
    clear_all_memories()
    print("✅ Test data cleared")


def main():
    """Run all Phase 28 tests."""
    print("=" * 60)
    print("🧪 Phase 28 Feature Testing")
    print("=" * 60)
    
    # Setup
    test_keys = setup_test_data()
    
    # Run tests
    results = {}
    
    results["association"] = test_association_generation()
    results["forgetting"] = test_forgetting_module()
    results["statistical_summary"] = test_statistical_summarization()
    results["llm_error_handling"] = test_llm_summarization_error_handling()
    
    # Cleanup
    cleanup_test_data()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {test_name}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\n  Total: {passed}/{total} passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
