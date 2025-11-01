"""
Analysis utilities for Memory MCP Server.
Provides knowledge graph generation, time-series analysis, and other analytical features.
"""

import os
import re
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from typing import List, Dict, Tuple, Optional

import networkx as nx
from pyvis.network import Network

from persona_utils import get_db_path


# ============================================================================
# Phase 20: Knowledge Graph Generation
# ============================================================================

def extract_links_from_memories(persona: str | None = None) -> Dict[str, List[str]]:
    """
    Extract [[links]] from all memories.
    
    Args:
        persona: Persona name (default: current persona from context)
    
    Returns:
        Dict mapping memory keys to lists of links found in that memory
    """
    link_pattern = r'\[\[([^\]]+)\]\]'
    memory_links = {}
    
    try:
        db_path = get_db_path(persona=persona)
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT key, content FROM memories')
            rows = cursor.fetchall()
            
            for key, content in rows:
                links = re.findall(link_pattern, content)
                if links:
                    memory_links[key] = links
                    
        return memory_links
        
    except Exception as e:
        print(f"Error extracting links: {e}")
        return {}


def build_knowledge_graph(
    min_count: int = 2,
    min_cooccurrence: int = 1,
    remove_isolated: bool = True,
    persona: str | None = None
) -> nx.Graph:
    """
    Build knowledge graph from memory links.
    
    Args:
        min_count: Minimum link occurrence count to include
        min_cooccurrence: Minimum co-occurrence count for edges
        remove_isolated: Remove nodes with no edges
        persona: Persona name (default: current persona from context)
        
    Returns:
        NetworkX graph with nodes (links) and edges (co-occurrences)
    """
    # Extract links from all memories
    memory_links = extract_links_from_memories(persona=persona)
    
    # Count link occurrences
    link_counter = Counter()
    for links in memory_links.values():
        link_counter.update(links)
    
    # Filter by minimum count
    valid_links = {link for link, count in link_counter.items() if count >= min_count}
    
    # Build co-occurrence matrix
    cooccurrence = defaultdict(int)
    memory_count = defaultdict(set)  # Track which memories contain each link
    
    for memory_key, links in memory_links.items():
        # Filter to valid links
        valid_memory_links = [link for link in links if link in valid_links]
        
        # Track memories for each link
        for link in valid_memory_links:
            memory_count[link].add(memory_key)
        
        # Count co-occurrences
        for i, link1 in enumerate(valid_memory_links):
            for link2 in valid_memory_links[i+1:]:
                # Use sorted tuple to avoid duplicates
                pair = tuple(sorted([link1, link2]))
                cooccurrence[pair] += 1
    
    # Build NetworkX graph
    G = nx.Graph()
    
    # Add nodes with attributes
    for link in valid_links:
        G.add_node(
            link,
            count=link_counter[link],
            memories=list(memory_count[link])
        )
    
    # Add edges with weights
    for (link1, link2), weight in cooccurrence.items():
        if weight >= min_cooccurrence:
            G.add_edge(link1, link2, weight=weight)
    
    # Remove isolated nodes if requested
    if remove_isolated:
        isolated = list(nx.isolates(G))
        G.remove_nodes_from(isolated)
    
    return G


def export_graph_json(G: nx.Graph) -> str:
    """
    Export graph as JSON.
    
    Returns:
        JSON string with nodes and edges
    """
    data = {
        "nodes": [
            {
                "id": node,
                "label": node,
                "count": G.nodes[node].get("count", 0),
                "memories": G.nodes[node].get("memories", [])
            }
            for node in G.nodes()
        ],
        "edges": [
            {
                "source": edge[0],
                "target": edge[1],
                "weight": G.edges[edge].get("weight", 1)
            }
            for edge in G.edges()
        ],
        "stats": {
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "density": nx.density(G),
            "avg_degree": sum(dict(G.degree()).values()) / G.number_of_nodes() if G.number_of_nodes() > 0 else 0
        }
    }
    
    return json.dumps(data, indent=2, ensure_ascii=False)


def export_graph_html(
    G: nx.Graph,
    output_path: str,
    title: str = "Knowledge Graph"
) -> str:
    """
    Export graph as interactive HTML using PyVis.
    
    Args:
        G: NetworkX graph
        output_path: Path to save HTML file
        title: Graph title
        
    Returns:
        Path to saved HTML file
    """
    # Create PyVis network
    net = Network(
        height="800px",
        width="100%",
        bgcolor="#ffffff",
        font_color="#000000",
        notebook=False
    )
    
    # Set physics options for better layout
    net.set_options("""
    {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -50,
          "centralGravity": 0.01,
          "springLength": 200,
          "springConstant": 0.08
        },
        "maxVelocity": 50,
        "solver": "forceAtlas2Based",
        "timestep": 0.35,
        "stabilization": {"iterations": 150}
      }
    }
    """)
    
    # Add nodes with size based on count
    for node in G.nodes():
        count = G.nodes[node].get("count", 1)
        size = 10 + (count * 5)  # Base size + count scaling
        
        net.add_node(
            node,
            label=node,
            title=f"{node}\n出現回数: {count}",
            size=size,
            color="#97C2FC"
        )
    
    # Add edges with width based on weight
    for edge in G.edges():
        weight = G.edges[edge].get("weight", 1)
        width = 1 + (weight * 2)  # Base width + weight scaling
        
        net.add_edge(
            edge[0],
            edge[1],
            width=width,
            title=f"共起回数: {weight}"
        )
    
    # Save to file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    net.save_graph(output_path)
    
    return output_path


# ============================================================================
# Duplicate Detection and Memory Merging
# ============================================================================

def detect_duplicate_memories(threshold: float = 0.85, max_pairs: int = 50) -> List[Dict]:
    """
    Detect duplicate or highly similar memory pairs using embeddings similarity.
    
    Args:
        threshold: Similarity threshold (0.0-1.0). Default 0.85 means 85% similar or more
        max_pairs: Maximum number of duplicate pairs to return (default: 50)
        
    Returns:
        List of duplicate pairs sorted by similarity score
    """
    # Delegate to vector_utils implementation
    from vector_utils import detect_duplicate_memories as _detect_duplicates
    return _detect_duplicates(threshold=threshold, max_pairs=max_pairs)


def merge_memories(
    memory_keys: List[str],
    merged_content: Optional[str] = None,
    keep_all_tags: bool = True,
    delete_originals: bool = True
) -> str:
    """
    Merge multiple memories into a single consolidated memory.
    
    Args:
        memory_keys: List of memory keys to merge (minimum 2)
        merged_content: Content for merged memory. If None, contents are concatenated
        keep_all_tags: If True, combine tags from all memories
        delete_originals: If True, delete original memories after merge
        
    Returns:
        New merged memory key
    """
    from core import load_memory_from_db, save_memory_to_db, delete_memory_from_db, generate_auto_key
    from datetime import datetime
    
    if not memory_keys or len(memory_keys) < 2:
        raise ValueError("At least 2 memory keys are required for merging")
    
    # Load all memories
    memories = []
    all_tags = set()
    for key in memory_keys:
        memory = load_memory_from_db(key)
        if not memory:
            raise ValueError(f"Memory not found: {key}")
        memories.append(memory)
        
        # Collect tags
        if memory.get("tags"):
            all_tags.update(memory["tags"])
    
    # Create merged content
    if merged_content is None:
        # Concatenate all contents with separators
        content_parts = [m["content"] for m in memories]
        merged_content = "\n\n".join(content_parts)
    
    # Prepare merged memory data
    merged_tags = list(all_tags) if keep_all_tags else memories[0].get("tags", [])
    
    # Use earliest created_at as timestamp
    created_dates = [datetime.fromisoformat(m["created_at"]) for m in memories]
    earliest_date = min(created_dates)
    
    # Generate new key
    new_key = generate_auto_key()
    
    # Save merged memory
    merged_memory = {
        "key": new_key,
        "content": merged_content,
        "tags": merged_tags,
        "created_at": earliest_date.isoformat()
    }
    save_memory_to_db(merged_memory)
    
    # Delete originals if requested
    if delete_originals:
        for key in memory_keys:
            delete_memory_from_db(key)
    
    return new_key

