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
    from tools.crud_tools import create_memory, update_memory, delete_memory
    from tools.search_tools import search_memory

    from tools.context_tools import get_context
    from tools.equipment_tools import (
        add_to_inventory, remove_from_inventory, 
        equip_item, 
        update_item, 
        search_inventory, get_equipment_history
    )
    from tools.item_memory_tools import (
        analyze_item
    )
    # from tools.summarization_tools import summarize_last_week, summarize_last_day  # 管理者ツールに移行

    # === LLM用ツール（会話中に使用） ===
    
    # Context: Unified context retrieval (CALL EVERY RESPONSE)
    # Combines: persona state, time tracking, memory statistics
    mcp.tool()(get_context)
    
    # Phase 28.5: Unified search interface
    # - create_memory: 新規作成専用（RAG検索なし、高速）
    # - update_memory: 更新専用（RAG検索あり、類似度0.80以上で更新）
    # - search_memory: 統合検索（semantic/keyword/related modes）
    # - delete_memory: 削除専用（自然言語クエリ対応）
    mcp.tool()(create_memory)
    mcp.tool()(update_memory)
    mcp.tool()(search_memory)
    mcp.tool()(delete_memory)
    
    # 所持品管理ツール（Phase 32）
    mcp.tool()(add_to_inventory)
    mcp.tool()(remove_from_inventory)
    mcp.tool()(equip_item)
    mcp.tool()(update_item)
    mcp.tool()(search_inventory)
    mcp.tool()(get_equipment_history)
    
    # アイテム-記憶関連付けツール（Phase 34: 装備品自動記録）
    mcp.tool()(analyze_item)
    
    # Phase 28.4: 自己要約（メタメモリ）→ 管理者ツールに移行
    # mcp.tool()(summarize_last_week)  # ❌ LLM用ツールから除外
    # mcp.tool()(summarize_last_day)   # ❌ LLM用ツールから除外
    # ✅ admin_tools.py + ダッシュボードから実行可能
    
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

