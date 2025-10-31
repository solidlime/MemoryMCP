"""
MCPツール/リソースの登録を一箇所にまとめるモジュール。
memory_mcp.py 側の関数は素の関数（@mcp.tool を外す）として保持し、
ここで mcp.tool()(func) および mcp.resource()(func) により登録する。
"""

from typing import Any

def register_tools(mcp: Any) -> None:
    # 遅延importして循環依存を回避
    import memory_mcp as impl

    # ツール群
    mcp.tool()(impl.list_memory)
    mcp.tool()(impl.create_memory)
    mcp.tool()(impl.update_memory)
    mcp.tool()(impl.read_memory)
    mcp.tool()(impl.delete_memory)
    mcp.tool()(impl.search_memory)
    mcp.tool()(impl.clean_memory)
    mcp.tool()(impl.search_memory_rag)
    mcp.tool()(impl.get_time_since_last_conversation)
    mcp.tool()(impl.get_persona_context)
    mcp.tool()(impl.rebuild_vector_store_tool)
    mcp.tool()(impl.find_related_memories)
    mcp.tool()(impl.detect_duplicates)
    mcp.tool()(impl.merge_memories)
    # Phase 19: AI Assist
    mcp.tool()(impl.analyze_sentiment)
    # Phase 20: Knowledge Graph
    mcp.tool()(impl.generate_knowledge_graph)


def register_resources(mcp: Any) -> None:
    import memory_mcp as impl
    mcp.resource("memory://info")(impl.get_memory_info)
    mcp.resource("memory://metrics")(impl.get_memory_metrics)
    mcp.resource("memory://stats")(impl.get_memory_stats)

