"""
Association Generation Module for Memory MCP.

Phase 28.2: Automatic memory association based on semantic similarity.
Implements the "related_keys" functionality to create memory chains.
"""

import json
from typing import List, Dict, Optional, Tuple
from config_utils import load_config
from persona_utils import get_current_persona


def find_similar_memories(
    query_content: str, 
    top_k: int = 3,
    exclude_keys: Optional[List[str]] = None
) -> List[Dict]:
    """
    Find semantically similar memories using Qdrant.
    
    Args:
        query_content: Content to search for similar memories
        top_k: Number of similar memories to return (default: 3)
        exclude_keys: List of memory keys to exclude from results
    
    Returns:
        List of dicts with keys: 'key', 'score', 'content', 'emotion', 'emotion_intensity'
    """
    from vector_utils import embeddings, _get_qdrant_adapter, initialize_rag_sync
    
    # Ensure RAG is initialized
    if not embeddings:
        print("🔄 Initializing RAG for association search...")
        initialize_rag_sync()
    
    # Import again after initialization
    from vector_utils import embeddings
    
    if not embeddings:
        print("⚠️  RAG initialization failed, cannot find similar memories")
        return []
    
    try:
        persona = get_current_persona()
        adapter = _get_qdrant_adapter(persona)
        
        # Query embedding
        query_embedding = embeddings.embed_query(query_content)
        
        # Search similar memories (get extra to account for exclusions)
        search_k = top_k + len(exclude_keys) if exclude_keys else top_k
        results = adapter.similarity_search_with_score_by_vector(
            query_embedding, 
            k=search_k
        )
        
        # Filter and format results
        similar_memories = []
        for doc, score in results:
            key = doc.metadata.get("key")
            
            # Skip excluded keys
            if exclude_keys and key in exclude_keys:
                continue
            
            # Skip if already have enough results
            if len(similar_memories) >= top_k:
                break
            
            similar_memories.append({
                "key": key,
                "score": float(score),
                "content": doc.page_content,
                "emotion": doc.metadata.get("emotion", "neutral"),
                "emotion_intensity": doc.metadata.get("emotion_intensity", 0.0),
                "importance": doc.metadata.get("importance", 0.5)
            })
        
        return similar_memories
    
    except Exception as e:
        print(f"⚠️  Failed to find similar memories: {e}")
        return []


def calculate_emotion_context(similar_memories: List[Dict]) -> Dict:
    """
    Calculate emotion context from similar memories.
    
    Args:
        similar_memories: List of similar memory dicts
    
    Returns:
        Dict with 'average_emotion_intensity', 'dominant_emotion', 'emotion_boost'
    """
    if not similar_memories:
        return {
            "average_emotion_intensity": 0.0,
            "dominant_emotion": "neutral",
            "emotion_boost": 0.0
        }
    
    # Calculate average emotion intensity
    intensities = [m.get("emotion_intensity", 0.0) for m in similar_memories]
    avg_intensity = sum(intensities) / len(intensities) if intensities else 0.0
    
    # Find dominant emotion
    emotions = [m.get("emotion", "neutral") for m in similar_memories]
    emotion_counts = {}
    for emotion in emotions:
        emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
    
    dominant_emotion = max(emotion_counts.items(), key=lambda x: x[1])[0] if emotion_counts else "neutral"
    
    # Calculate emotion boost for importance
    # High emotion intensity in related memories suggests this is an important topic
    emotion_boost = avg_intensity * 0.2  # Max +0.2 to importance
    
    return {
        "average_emotion_intensity": avg_intensity,
        "dominant_emotion": dominant_emotion,
        "emotion_boost": emotion_boost
    }


def generate_associations(
    new_key: str,
    new_content: str,
    emotion_intensity: float = 0.0,
    base_importance: float = 0.5
) -> Tuple[List[str], float]:
    """
    Generate associations for a new memory.
    
    This is the core function of Phase 28.2 Association Generation Module.
    
    Args:
        new_key: Key of the new memory
        new_content: Content of the new memory
        emotion_intensity: Emotion intensity of the new memory
        base_importance: Base importance score
    
    Returns:
        Tuple of (related_keys, adjusted_importance)
    """
    # Find similar memories (exclude the new memory itself)
    similar_memories = find_similar_memories(
        new_content, 
        top_k=3, 
        exclude_keys=[new_key]
    )
    
    # Extract related keys
    related_keys = [m["key"] for m in similar_memories]
    
    # Calculate emotion context
    emotion_context = calculate_emotion_context(similar_memories)
    
    # Adjust importance based on:
    # 1. Own emotion intensity
    # 2. Emotion intensity of related memories
    importance_adjustment = 0.0
    
    # Own emotion contributes directly
    importance_adjustment += emotion_intensity * 0.2
    
    # Related memories' emotion context contributes
    importance_adjustment += emotion_context["emotion_boost"]
    
    # Cap adjustment to prevent exceeding 1.0
    adjusted_importance = min(1.0, base_importance + importance_adjustment)
    
    # Log association generation
    if related_keys:
        print(f"🔗 Generated {len(related_keys)} associations for {new_key}")
        print(f"   Related: {related_keys}")
        print(f"   Emotion context: {emotion_context['dominant_emotion']} (avg intensity: {emotion_context['average_emotion_intensity']:.2f})")
        print(f"   Importance: {base_importance:.2f} → {adjusted_importance:.2f} (+{importance_adjustment:.2f})")
    
    return related_keys, adjusted_importance


def update_related_keys(key: str, related_keys: List[str]) -> bool:
    """
    Update the related_keys field for an existing memory.
    
    Args:
        key: Memory key to update
        related_keys: List of related memory keys
    
    Returns:
        True if successful, False otherwise
    """
    import sqlite3
    from persona_utils import get_db_path
    
    try:
        db_path = get_db_path()
        related_keys_json = json.dumps(related_keys, ensure_ascii=False)
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE memories SET related_keys = ? WHERE key = ?',
                (related_keys_json, key)
            )
            conn.commit()
        
        return True
    
    except Exception as e:
        print(f"❌ Failed to update related_keys for {key}: {e}")
        return False
