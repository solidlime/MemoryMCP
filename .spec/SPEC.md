# SPEC - 技術仕様・要件定義 v8

> 元PLAN: `.spec/PLAN.md` v8。@oracle レビュー反映済み。

## 目標
- **`docker compose up` 一発で全機能が利用可能になること。**
- **外部MCPクライアントからも全ツールが利用可能になること。**

---

## 機能要件

### 柱A: Docker Compose 完全自動デプロイ

- [ ] **A-1**: docker-compose.yml に SearXNG サービス追加
  - イメージ: `searxng/searxng:latest`
  - ポート: 8080（内部ネットワーク）
  - ボリューム: `./data/searxng:/etc/searxng`
  - 環境変数: `SEARXNG_BASE_URL=http://localhost:8080/`
  - memory-mcp の `depends_on` に `searxng` 追加
  - SearXNG デフォルトURL: `http://searxng:8080`

- [ ] **A-2**: Dockerfile.sandbox 多言語ランタイム追加
  - 追加ランタイム: Node.js 22.x LTS, Go 1.22+, Rust + rust-script, Tesseract OCR + jpn
  - ベースイメージ: `python:3.11-slim-bullseye` 維持
  - マルチステージビルドでサイズ最小化
  - 合計約600MB増 → 実用性検証

- [ ] **A-3**: MEMORY_MCP_SEARXNG_URL 環境変数化
  - 環境変数 `MEMORY_MCP_SEARXNG_URL` で上書き可能
  - chat_config.py のデフォルト値を env var に
  - docker-compose.yml に `SEARXNG_URL=http://searxng:8080`

- [ ] **A-4**: 本番ビルド + 全起動確認
  - `docker compose up` で qdrant + searxng + memory-mcp 全起動
  - sandbox イメージ自動ビルド確認
  - agent-browser Chrome 起動確認（--no-sandbox フラグ検証）
  - CI docker.yml が新Dockerfileでビルド通るか確認

- [ ] **A-5**: Docker security hardening
  - sandbox: `read_only: true`, `cap_drop: [ALL]`, `tmpfs: /tmp`
  - memory-mcp: `read_only: true`（書き込みボリュームのみ rw）
  - 全コンテナ: `no-new-privileges: true`

- [ ] **A-6**: `/health` エンドポイント追加
  - FastMCP `custom_route` で `/health` 実装
  - Qdrant / SearXNG / sandbox の到達性チェック
  - docker-compose healthcheck で使用

### 柱B: MCPツール全登録 + 名前統一 + 二重実装解消

- [ ] **B-1**: 未登録5ツールの MCP `@mcp.tool()` 追加
  - browser, search, image_generate, read_pdf, list_skills を MCP 登録
  - **委譲パターン**: builtin 実装を MCP ラッパーから呼ぶ。重複実装禁止
  - `tools.py` に各 `@mcp.tool()` 関数追加

- [ ] **B-2**: `execute_code` → `sandbox` 名前統一
  - definitions.py: ツール名 `sandbox`
  - builtin.py: `_BUILTIN_DISPATCH` キー `sandbox`
  - chat.js: ツール呼出 `sandbox`
  - テストのツール名参照全更新

- [ ] **B-3**: `context_update` → `update_context` 統合
  - `context_update` (builtin) を削除、`update_context` (MCP側) に一本化
  - definitions.py の名称変更・パラメータ拡充
  - `_BUILTIN_DISPATCH` から `_tool_update_context` を呼ぶ

- [ ] **B-4**: `_MEMORY_MCP_TOOL_NAMES` フィルタ修正
  - `web_search` → `search`
  - `image_generate`, `read_pdf`, `list_skills` 追加（MCP登録後の重複防止）

- [ ] **B-5-1**: memory_create/search/update 戻り値形式統一
  - MCP 側の戻り値（現在文字列）を dict 形式に統一
  - 契約: `{"ok": True/False, "key": "...", "memories": [...], "error": "..."}`
  - Builtin 側の形式に MCP 側を合わせる（安全方向）

- [ ] **B-5-2**: memory_create/search/update 実装統合（委譲）
  - B-5-1 の形式統一後、builtin → MCP 委譲に切り替え
  - `_handle_memory_*_builtin` 関数削除
  - `memory_update` の query→key 解決ロジックを `_tool_memory_update` に移植
  - 後方互換シグネチャ: `memory_key` と `query` 両方受け入れ

- [ ] **B-6**: ツール説明環境変数カスタマイズ
  - 環境変数: `MEMORY_MCP_TOOL_DESCRIPTION_OVERRIDE`
  - 形式: `tool_name=new_description` (カンマ区切り)
  - `register_tools()` で上書き

### 柱C: sandbox マルチ言語対応

- [ ] **C-2**: JavaScript セッション追加
  - `service.py` に `_ensure_javascript_started()` 追加
  - llm_sandbox `InteractiveSandboxSession(lang="javascript")`
  - ルーティング: `javascript`/`js`/`node` → JS セッション

- [ ] **C-3**: Go セッション追加
  - `_execute_stateless(code, "go")` でステートレス実行
  - `go run` 使用。毎回新規コンテナ

- [ ] **C-4**: Rust セッション追加
  - `_execute_stateless(code, "rust")` でステートレス実行
  - `rust-script` 経由で単一ファイル実行

- [ ] **C-5**: Bash ネイティブ実行化
  - 現在: Python subprocess.run() ラップ → `_execute_stateless(code, "bash")` に直接ルーティング
  - `!` プレフィックス除去ロジックは service.py 側で維持

- [ ] **C-6**: `allowed_languages` 更新 + `get_supported_languages` 追加
  - settings.py: `["python", "javascript", "bash", "go", "rust"]`
  - definitions.py: language description 更新
  - `get_supported_languages` ツール追加（Zero-Context Discovery）

### 柱D: 新機能追加

- [ ] **D-1**: PDF OCR 対応
  - Tesseract OCR (tesseract-ocr-jpn) によるスキャンPDF対応
  - フォールバック連鎖: PyMuPDF → pdfplumber → Tesseract OCR
  - 画像抽出: ページ埋め込み画像の base64 出力
  - テーブル抽出は pdfplumber で十分。Camelot 不要

- [ ] **D-2**: Agent Skills 標準移行（基本）
  - `plugins/` → `SKILL.md` 形式に移行
  - フロントマター: `name`, `description`
  - Progressive Disclosure 3段階
  - `list_skills` / `invoke_skill` を SKILL.md ベースに
  - `.well-known/` は将来フェーズ

- [ ] **D-3**: メモリ 4-tier lifecycle 基本
  - 状態: Active → Superseded → Tombstoned → Hard-deleted
  - DBスキーマに `lifecycle_status` カラム追加
  - 後方互換: 既存 tags ベース表現 → lifecycle_status にマッピング
  - 先送り: as_of, LRU shield, active_days, chain-aware pruning, 自動Superseding

- [ ] **D-4**: メモリ検索ハイブリッド強化
  - SQLite FTS5 全文検索インデックス追加
  - KNN (Qdrant) + FTS5 (SQLite) + キーワード の3-signal ハイブリッド
  - RRF (Reciprocal Rank Fusion) で結果統合
  - RRF 重みパラメータ: `vector_weight`, `keyword_weight`
  - Similarity flag: cosine ≥ 0.85

---

## 非機能要件

- **パフォーマンス**: sandbox イメージビルド時間 10分以内、コンテナ起動 30秒以内
- **セキュリティ**: sandbox コンテナは read_only + cap_drop ALL、全コンテナ no-new-privileges
- **後方互換性**: 既存 MCP クライアントとの互換性維持（B-5はMCP→dict形式統一で破壊的変更なし）
- **テスト**: 全変更後 1134+ tests がパスすること、新規コードにはテスト追加
- **CI**: docker.yml / ci.yml 両方を通すこと

## 技術構成

- **言語・フレームワーク**: Python 3.12, FastMCP, asyncio
- **インフラ・環境**: Docker Compose (Qdrant + SearXNG + memory-mcp)
- **sandbox**: llm_sandbox 0.3.x, Docker sibling container
- **ブラウザ**: agent-browser CLI v0.30.x
- **検索**: SearXNG (自己ホスト)
- **DB**: SQLite (メモリ), Qdrant (ベクトル)
- **画像生成**: OpenAI DALL-E + Stability (既存)
- **PDF**: PyMuPDF + pdfplumber + Tesseract OCR

## データ構造・インターフェース

### B-5 戻り値統一契約
```python
# 成功時
{"ok": True, "key": "mem_xxx", "content": "..."}

# メモリ検索成功時
{"ok": True, "memories": [{"key": "mem_xxx", "content": "...", "score": 0.95}, ...]}

# 失敗時
{"ok": False, "error": "error message"}
```

### D-3 lifecycle_status スキーマ
```sql
ALTER TABLE memories ADD COLUMN lifecycle_status TEXT DEFAULT 'active';
-- 値: 'active', 'superseded', 'tombstoned'
-- 既存 tags からのマッピング:
--   tagsに'archived' → lifecycle_status='tombstoned'
--   tagsに'active' or なし → lifecycle_status='active'
```

### D-4 FTS5 インデックス
```sql
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content, key, tags,
    content='memories', content_rowid='rowid'
);
```
