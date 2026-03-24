# MEMORY

## プロジェクト概要

## 学習した知識・教訓

### get_context 出力調整（2026-03-23）
- `memory_preview_length` デフォルトは `src/utils/config_utils.py` の `DEFAULT_CONFIG` で管理（100→200に変更済み）
- 記憶タイムスタンプはUTC保存 → `format_datetime_for_display()` でJST変換が必要（修正済み）
- Memory Blocks（block_write/block_read/block_list/block_delete）は廃止済み。DBレイヤー(`memory_blocks_db.py`)は保持
- Promises & Goals は `context_tags=['promise'/'goal']` のタグベース実装
- get_context のメイン実装は `tools/context_tools.py`、オペレーション処理は `tools/handlers/context_handlers.py`

### X-Persona ヘッダー対応（2025-07-18）
- FastMCPのContextからHTTPヘッダーには直接アクセス不可（MCPプロトコル層の情報のみ）
- 解決策: `contextvars.ContextVar` + ASGIミドルウェア（`PersonaMiddleware`）でリクエストスコープにペルソナを注入
- FastMCPへのミドルウェア追加はサブクラス化（`MemoryFastMCP`）で`streamable_http_app()`/`sse_app()`をオーバーライドし`add_middleware()`する
- ペルソナ優先順位: Bearer token > X-Persona header > PERSONA env > MEMORY_MCP_DEFAULT_PERSONA env > "default"
- `middleware.py` の `get_current_persona()` が全レイヤー共通のペルソナ解決エントリポイント
- routes.py のHTTPルートでは `_resolve_persona_from_request()` がpath param > header > env のフォールバックを提供

