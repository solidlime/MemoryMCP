"""
MCPツール/リソースの登録を一箇所にまとめるモジュール。
memory_mcp.py 側の関数は素の関数（@mcp.tool を外す）として保持し、
ここで mcp.tool()(func) および mcp.resource()(func) により登録する。

Phase 2024-11-01: ツール整理
- LLM用ツール: 会話中に使用するツール（MCPツールとして登録）
- 管理者用ツール: メンテナンス作業用（admin_tools.py + ダッシュボードから実行）
"""

from typing import Any

def register_tools(mcp: Any) -> None:
    # 遅延importして循環依存を回避
    
    # Phase 35: Unified tool interface (context reduction)
    from tools.unified_tools import memory, item
    from tools.context_tools import get_context
    
    # === LLM用ツール（会話中に使用） ===
    
    # Context: Unified context retrieval (CALL EVERY RESPONSE)
    # Combines: persona state, time tracking, memory statistics
    mcp.tool()(get_context)
    
    # Phase 35: Unified memory interface
    # Single tool with operation parameter: create, read, update, delete, search, stats
    # Replaces: create_memory, update_memory, search_memory, delete_memory
    mcp.tool()(memory)
    
    # Phase 35: Unified item interface
    # Single tool with operation parameter: add, remove, equip, update, search, history, memories, stats
    # Replaces: add_to_inventory, remove_from_inventory, equip_item, update_item, 
    #           search_inventory, get_equipment_history, analyze_item
    mcp.tool()(item)
    
    # === 管理者用ツールはMCPから除外 ===
    # 以下のツールは admin_tools.py CLIコマンド または ダッシュボードから実行：
    # - clean_memory (重複行削除)
    # - rebuild_vector_store_tool (ベクトルストア再構築)
    # - migrate_sqlite_to_qdrant_tool (SQLite→Qdrant移行)
    # - migrate_qdrant_to_sqlite_tool (Qdrant→SQLite移行)
    # - detect_duplicates (重複検知)
    # - merge_memories (メモリマージ)
    # - generate_knowledge_graph (知識グラフ生成)


def register_resources(mcp: Any) -> None:
    from src.resources import (
        get_memory_info,
        get_memory_metrics,
        get_memory_stats,
        get_cleanup_suggestions,
    )
    mcp.resource("memory://info")(get_memory_info)
    mcp.resource("memory://metrics")(get_memory_metrics)
    mcp.resource("memory://stats")(get_memory_stats)
    # Phase 21: Cleanup Suggestions
    mcp.resource("memory://cleanup")(get_cleanup_suggestions)

