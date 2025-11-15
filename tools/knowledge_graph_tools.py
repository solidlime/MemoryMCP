"""
Knowledge Graph Tools for Memory MCP
Generates interactive knowledge graphs from memory [[links]]
"""

from datetime import datetime

# Utility imports
from src.utils.persona_utils import get_current_persona
from src.utils.logging_utils import log_progress


async def generate_knowledge_graph(
    format: str = "json",
    min_count: int = 2,
    min_cooccurrence: int = 1,
    remove_isolated: bool = True
) -> str:
    """
    Generate knowledge graph from memory [[links]].
    
    Args:
        format: Output format ('json' or 'html')
        min_count: Minimum link occurrence count (default: 2)
        min_cooccurrence: Minimum co-occurrence count for edges (default: 1)
        remove_isolated: Remove nodes with no connections (default: True)
        
    Returns:
        JSON string or HTML file path
    """
    try:
        import os
        from src.utils.analysis_utils import build_knowledge_graph, export_graph_json, export_graph_html
        from src.utils.persona_utils import get_current_persona, get_db_path
        
        persona = get_current_persona()
        log_progress(f"🔍 Generating knowledge graph for persona: {persona}...")
        
        # Build graph
        G = build_knowledge_graph(
            min_count=min_count,
            min_cooccurrence=min_cooccurrence,
            remove_isolated=remove_isolated,
            persona=persona
        )
        
        if G.number_of_nodes() == 0:
            return "⚠️ No links found matching the criteria. Try lowering min_count parameter."
        
        # Export based on format
        if format.lower() == "html":
            # Get persona memory directory
            db_path = get_db_path()
            persona_dir = os.path.dirname(db_path)
            
            # HTML file path (single file per persona)
            output_path = os.path.join(persona_dir, f"knowledge_graph.html")
            
            # Remove old graph file if exists
            if os.path.exists(output_path):
                os.remove(output_path)
            
            file_path = export_graph_html(G, output_path, title=f"Knowledge Graph - {persona}")
            
            result = f"✅ Knowledge graph generated!\n\n"
            result += f"📊 Statistics:\n"
            result += f"   - Total nodes (links): {G.number_of_nodes()}\n"
            result += f"   - Total edges (connections): {G.number_of_edges()}\n"
            result += f"   - Average connections per node: {sum(dict(G.degree()).values()) / G.number_of_nodes():.2f}\n\n"
            result += f"📁 HTML file saved to: {file_path}\n"
            result += f"💡 Open this file in a web browser to explore the interactive graph!\n"
            
            log_progress(f"✅ Knowledge graph HTML saved: {file_path}")
            return result
            
        else:  # JSON format
            json_data = export_graph_json(G)
            
            result = f"✅ Knowledge graph generated (JSON format)!\n\n"
            result += f"📊 Statistics:\n"
            result += f"   - Total nodes (links): {G.number_of_nodes()}\n"
            result += f"   - Total edges (connections): {G.number_of_edges()}\n\n"
            result += f"📋 JSON Data:\n"
            result += json_data
            
            log_progress(f"✅ Knowledge graph JSON generated: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
            return result
        
    except Exception as e:
        log_progress(f"❌ Knowledge graph generation failed: {e}")
        return f"❌ Error generating knowledge graph: {str(e)}"
