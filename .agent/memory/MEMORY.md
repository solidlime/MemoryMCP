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

### WebUI E2E バグ修正（2026-03-26）
- **showSkeleton バグ**: `base.py` の `showSkeleton()` が `[id$="-content"]` の innerHTML をスケルトンで置換 → graph/import-export/personas タブの静的 HTML（#graph-container, #persona-grid, #export-preview）が消滅し、load 関数がサイレント失敗していた。修正: これら3タブは `showSkeleton` をスキップ（自前のローディング状態を持つため）
- **Memory モーダル非表示バグ**: `memories.py` の `openMemModal` override が `overlay.classList.add('show')` を呼んでいなかった → CSS transition で opacity:0 のまま（display:flex でも見えない）。base.py のオリジナルには `classList.add('show')` がある
- **conftest.py URL バグ**: `dashboard_url` fixture が `/dashboard/{persona}` を返していた → 404。正しくはルート `/`。ダッシュボードは SPA でペルソナは `#persona-select` ドロップダウンで選択する
- **`#chart-emotions` 未表示は正常**: emotion データなし時は canvas を "No emotion data" div に置換 → テストでの false positive に注意
