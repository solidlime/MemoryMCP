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
    from tools.crud_tools import get_memory_stats, create_memory, update_memory, read_memory, delete_memory
    from tools.search_tools import search_memory, search_memory_rag
    from tools.analysis_tools import find_related_memories, analyze_sentiment
    from tools.context_tools import get_time_since_last_conversation, get_persona_context

    # === LLM用ツール（会話中に使用） ===
    
    # Phase 25: list_memory廃止 → get_memory_stats のみ
    mcp.tool()(get_memory_stats)
    
    # 基本的なCRUD操作
    mcp.tool()(create_memory)
    mcp.tool()(update_memory)
    mcp.tool()(read_memory)
    mcp.tool()(delete_memory)
    
    # 検索・分析
    mcp.tool()(search_memory)
    mcp.tool()(search_memory_rag)
    mcp.tool()(find_related_memories)
    mcp.tool()(analyze_sentiment)
    
    # コンテキスト情報
    mcp.tool()(get_time_since_last_conversation)
    mcp.tool()(get_persona_context)
    
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

