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
    import memory_mcp as impl

    # === LLM用ツール（会話中に使用） ===
    
    # 基本的なCRUD操作
    mcp.tool()(impl.list_memory)
    mcp.tool()(impl.create_memory)
    mcp.tool()(impl.update_memory)
    mcp.tool()(impl.read_memory)
    mcp.tool()(impl.delete_memory)
    
    # 検索・分析
    mcp.tool()(impl.search_memory)
    mcp.tool()(impl.search_memory_rag)
    mcp.tool()(impl.find_related_memories)
    mcp.tool()(impl.analyze_sentiment)
    
    # コンテキスト情報
    mcp.tool()(impl.get_time_since_last_conversation)
    mcp.tool()(impl.get_persona_context)
    
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
    import memory_mcp as impl
    mcp.resource("memory://info")(impl.get_memory_info)
    mcp.resource("memory://metrics")(impl.get_memory_metrics)
    mcp.resource("memory://stats")(impl.get_memory_stats)
    # Phase 21: Cleanup Suggestions
    mcp.resource("memory://cleanup")(impl.get_cleanup_suggestions)

