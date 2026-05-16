# MEMORY

## プロジェクト概要

## 学習した知識・教訓

### get_context 出力調整（2026-03-23）
- `memory_preview_length` デフォルトは `src/utils/config_utils.py` の `DEFAULT_CONFIG` で管理（100→200に変更済み）
- 記憶タイムスタンプはUTC保存 → `format_datetime_for_display()` でJST変換が必要（修正済み）
- Memory Blocks（block_write/block_read/block_list/block_delete）は**廃止されていない・現役**。MCPツール経由で利用可能、DBテーブル `memory_blocks` も稼働中。HTTP API: `GET/POST /api/blocks/{persona}`、`DELETE /api/blocks/{persona}/{block_name}` を追加済み（routes.py末尾）。WebUI Overview タブにCRUD UI付き
- Promises & Goals は memory タグで管理: `tags=["goal","active"]` / `["promise","active"]` 方式。`update_context(append_goals/append_promises/remove_goals/remove_promises)` が推奨API。`persona_info={"goals":...}` 方式は廃止済み
- get_context のメイン実装は `memory_mcp/api/mcp/tools.py` （unified_tools.py 経由で各 handler を呼ぶ）

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
- **Persona emoji `\\U0001fXXXX` は JS 非対応**: Python の 8桁 Unicode エスケープ(`\\U`) は JavaScript で解釈されない。`\\uXXXX`(4桁) か実際のUnicode文字を使うこと
- **vis-network tooltip は DOM 要素を渡す**: `title` に HTML文字列を渡すと plain text で描画される。`document.createElement('div')` に innerHTML をセットして返す必要がある

### Goals/Promises タグ管理移行（2026-03-28）
- v009マイグレーション: goals/promises テーブルを memories テーブルに移行・DROP
- タグ規約: `["goal","active"]`/`["goal","achieved"]`/`["goal","cancelled"]`, `["promise","active"]`/`["promise","fulfilled"]`/`["promise","cancelled"]`
- `LegacyImporter._import_persona_context()` が `current_goals`/`active_promises` を memories に INSERT OR IGNORE
- `_import_goals`/`_import_promises` は goals/promises テーブルが存在しないため silent 0 を返す（Exception catch）
- `import_from_dir()` で全インポート後に実際のDB件数を再クエリして `counts["memories"]` を更新（165→167 for herta.zip）
- E2Eテストの `PERSONA_EXPECTED_COUNTS["herta"]` = 167（マイグレーション後のDB件数）
- `test_auto_import.py` の `result["herta"]["memories"]` も 167 に更新

