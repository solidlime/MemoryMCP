# PLAN: Docker本番構築 + 全ツール統合 + 機能拡張 2026-06-27 (v8)

> **前回レビュー反映**: @oracle 指摘6件を全反映（B-5分割、agent-browser WSL2、A-2軽量化、D-1/D-3縮小、D-2/.well-known削除、優先順位再編）

## 根拠
v7 でツール機能改善・UI/UX改善・テスト充実は完了 (1134 tests, 0 fail)。
ドッグフーディングで判明した根本問題 + @librarian による30+プロジェクト比較調査 + @explorer による全ツールMCP監査の結果から、
以下の4領域での改善が必要。

## 目標
**`docker compose up` 一発で全機能が利用可能になること。**
**外部MCPクライアントからも全ツールが利用可能になること。**

## 4本柱
- **柱A**: Docker Compose 完全自動デプロイ (SearXNG、sandbox多言語イメージ、browserセットアップ、security hardening、healthチェック)
- **柱B**: MCPツール全登録 + 名前統一 + 二重実装解消 (未登録5ツールのMCP化、名前統一、memory系二重実装の一本化)
- **柱C**: sandbox マルチ言語対応 (Node.js、Bashネイティブ、Go/Rust)
- **柱D**: 新機能追加 (PDF OCR、Agent Skills標準移行、メモリ4-tier lifecycle基本、ツール説明カスタマイズ)

## 優先順位と依存関係（改訂版）
```
柱A (Docker) ────── 最優先。他全柱の前提環境
柱B-1〜B-4 (MCP登録・名前統一) ──── 柱Aと並行可
柱D-1/D-2 (PDF/Skills) ──── 柱Bから独立。並行可
柱B-5 (二重実装解消) ──── 柱B-1完了後。D-3の前提
柱C (sandbox多言語) ── 柱A-2のDockerfile改修に依存
柱D-3/D-4 (lifecycle/検索) ── 柱B-5完了後
```

---

## 柱A: Docker Compose 完全自動デプロイ

### A-1. docker-compose.yml に SearXNG サービス追加
- `searxng/searxng:latest` イメージ、ポート8080（内部）
- ボリューム: `./data/searxng:/etc/searxng` で設定永続化
- 環境変数 `SEARXNG_BASE_URL` 設定
- memory-mcp の `depends_on` に searxng 追加 (condition: service_healthy)
- SearXNG URL デフォルト値を `http://searxng:8080` に変更

### A-2. Dockerfile.sandbox 多言語ランタイム追加
- **Node.js 22.x LTS** 追加 (~50MB増)
- **Go 1.22+** 追加 (~150MB増) — ステートレス実行のみ
- **Rust + rust-script** 追加 (~200MB増) — ステートレス実行のみ
- **Tesseract OCR + jpn** 追加 (~200MB増) — PDF OCR用 (D-1で使用)
- ベースイメージ: python:3.11-slim-bullseye 維持
- マルチステージビルドで最終イメージサイズ最小化
- ⚠️ 合計約600MB増 → ビルド時間・pull時間実用性を検証。Go/Rustはビルド時間が長いため、許容できない場合はイメージ分割（python+node+tesseract と go+rust を別イメージ）を検討

### A-3. 環境変数による SearXNG URL 設定
- `MEMORY_MCP_SEARXNG_URL` 環境変数で上書き可能に
- docker-compose.yml で `SEARXNG_URL=http://searxng:8080` 設定
- chat_config.py のデフォルト値変更（`http://nas:11111` → env var）

### A-4. 本番ビルド + 全起動確認
- `docker compose up` で qdrant + searxng + memory-mcp 全起動
- sandbox イメージ自動ビルド確認
- agent-browser 自動セットアップ確認
- **agent-browser のコンテナ内 Chrome 起動確認（`--no-sandbox` フラグ伝搬検証）** ← WSL2ブロッカー対処
- healthcheck が全サービスで機能するか確認
- CI ワークフロー (docker.yml) が更新後の Dockerfile でビルド通るか確認

### A-5. Docker security hardening
- sandbox コンテナ: `read_only: true`, `cap_drop: [ALL]`, `tmpfs: /tmp`
- memory-mcp: `read_only: true` (書き込み必要なボリュームのみ rw)
- 全コンテナ: `no-new-privileges: true`
- nginx (使用時) の `proxy_buffering off` 確認 (SSE 対応)

### A-6. `/health` エンドポイント追加
- FastMCP の `custom_route` で `/health` 実装
- Qdrant / SearXNG / sandbox の到達性チェックを含む
- docker-compose の healthcheck に使用

---

## 柱B: MCPツール全登録 + 名前統一 + 二重実装解消

### B-1. 未登録5ツールの MCP `@mcp.tool()` 追加
以下のツールを `tools.py` に `@mcp.tool()` として追加:
- **browser**: `builtin._handle_browser` を呼ぶ MCP ラッパー
- **search**: `builtin._handle_search` を呼ぶ MCP ラッパー
- **image_generate**: `builtin._handle_image_generate` を呼ぶ MCP ラッパー
- **read_pdf**: `builtin._handle_read_pdf` を呼ぶ MCP ラッパー
- **list_skills**: `builtin._handle_list_skills` を呼ぶ MCP ラッパー

→ **委譲パターン**: 新たに実装を作らず、builtin 実装を MCP ラッパーから委譲呼出し。
→ 必要なのは `_resolve_persona()` + `AppContextRegistry.get()` の解決と、パラメータのマッピングのみ。

### B-2. `execute_code` → `sandbox` 名前統一
- definitions.py: ToolDefinition 名を `sandbox` に変更
- builtin.py: `_BUILTIN_DISPATCH` キーを `sandbox` に変更
- chat.js: ツール呼出しを `sandbox` に統一
- テストのツール名参照も全更新

### B-3. `context_update` と `update_context` の統合
- 現在: MCPに`update_context`(20+パラメータ)、Builtinに`context_update`(4パラメータ)
- 方針: `context_update` を削除し、`update_context` に一本化
- definitions.py: `context_update` → `update_context` に名称変更、パラメータを MCP 側に合わせる
- builtin.py: `_handle_context_update_builtin` を `_tool_update_context` に委譲
- `_MEMORY_MCP_TOOL_NAMES` から `context_update` 削除

### B-4. `_MEMORY_MCP_TOOL_NAMES` フィルタ修正
- `web_search` → `search` に修正
- 追加: `image_generate`, `read_pdf`, `list_skills` (MCP登録後は重複防止のため)
- B-2/B-3 完了後に名前の一貫性を確認

### B-5. memory_create / memory_search / memory_update 二重実装解消
> ⚠️ **@oracle 指摘反映**: 元のPLANは単純な委譲を想定していたが、MCP側は文字列、Builtin側はdictを返すという**戻り値形式の根本的不整合**がある。単純委譲では全memory操作が破壊される。2フェーズに分割して安全に移行する。

**クリティカルな不整合**:
| ツール | MCP 戻り値 | Builtin 戻り値 |
|--------|-----------|----------------|
| memory_create | `"Memory created: {key}"` (str) | `{"status": "ok", "key": mem.key}` (dict) |
| memory_search | 整形済み文字列 (str) | `{"status": "ok", "memories": [...]}` (dict) |
| memory_update | `"Memory updated: {key}"` (str) | `{"status": "ok", "key": mem_key}` (dict) |

`_handle_mcp_dispatch()` (builtin.py) は `result.get("ok")` で dict を期待 → 文字列だと `AttributeError`。

#### B-5-1. 戻り値形式の統一（先に実施）
- MCP の `_tool_memory_create/search/update` の戻り値を dict 形式に統一
- `{"ok": True/Falsy, "key": ..., "memories": [...], "error": "..."}` の契約に揃える
- 既存MCPクライアントが文字列を期待している場合の後方互換性は、MCPプロトコルがJSONを前提としているため破壊的変更にはならない（文字列もJSONとして有効）
- Builtin 側の `_handle_memory_create/search/update_builtin` の戻り値形式に MCP 側を合わせるのが安全方向

#### B-5-2. 実装の統合（B-5-1完了後）
- B-5-1 で戻り値が統一された後、builtin → MCP 委譲に切り替え
- `builtin.py` の `_handle_memory_*_builtin` を削除し、`_BUILTIN_DISPATCH` から `_tool_memory_*` を直接呼ぶ
- `memory_update` の query→key 解決ロジックは `_tool_memory_update` に移植（`memory_key` と `query` 両方を受け入れる後方互換シグネチャ）

### B-6. ツール説明の環境変数カスタマイズ (`qdrant/mcp-server-qdrant` パターン)
- `MEMORY_MCP_TOOL_DESCRIPTION_OVERRIDE` 環境変数
- 形式: `tool_name=new_description` (カンマ区切り)
- `register_tools()` でツール登録時に読み取り・上書き
- LLM コンテキスト最適化のため（冗長な説明を短縮可能に）

---

## 柱C: sandbox マルチ言語対応

### C-1. Dockerfile.sandbox 多言語ランタイム
- A-2 と同一タスク。Node.js + Go + Rust + Tesseract を追加。

### C-2. service.py に JavaScript セッション追加
- `_ensure_javascript_started()` メソッド追加
- llm_sandbox の `InteractiveSandboxSession(lang="javascript")` を使用
- sandbox execute のルーティング: `javascript` / `js` / `node` → JS セッション

### C-3. service.py に Go セッション追加
- `_execute_stateless(code, "go")` で対応
- `go run` でステートレス実行（毎回新規コンテナ）
- Dockerfile に golang が必要 (C-1 で対応済み)

### C-4. service.py に Rust セッション追加
- `_execute_stateless(code, "rust")` で対応
- `rust-script` 経由で単一ファイル実行（cargoプロジェクト不要）
- Dockerfile に rustc + cargo + rust-script が必要 (C-1 で対応済み)

### C-5. Bash をネイティブ実行に修正
- 現在: Python の subprocess.run() でラップ（`!` プレフィックス除去あり）
- 修正: `_execute_stateless(code, "bash")` に直接ルーティング
- `!` プレフィックス除去ロジックは service.py 側で維持

### C-6. `allowed_languages` を実態に合わせる
- settings.py: `["python", "javascript", "bash"]` → `["python", "javascript", "bash", "go", "rust"]`
- definitions.py のツール定義 language description 更新
- `get_supported_languages` ツール追加（llm-sandbox 公式パターン）
  - LLM が自分で「どの言語が使えるか」を発見できる
  - Zero-Context Discovery パターン

---

## 柱D: 新機能追加

### D-1. PDF OCR 対応 (`read_pdf` ツール強化)
- 現在: PyMuPDF + pdfplumber でテキスト抽出。**既に動作中。**
- 追加:
  - **Tesseract OCR** (日本語対応: tesseract-ocr-jpn) によるスキャンPDF対応
  - **フォールバック連鎖**: PyMuPDF → pdfplumber → Tesseract OCR
  - **画像抽出**: ページ埋め込み画像の base64 出力 (マルチモーダルLLM向け)
- テーブル抽出は既存の pdfplumber で十分。Camelot は追加しない（Java必須で過剰依存）。
- Dockerfile (A-2) に `tesseract-ocr`, `tesseract-ocr-jpn` 追加
- 依存: `pytesseract`

### D-2. Agent Skills 標準移行（基本部分のみ）
- 既存の `plugins/` を Agent Skills 標準 (`SKILL.md` 形式) に移行
- フロントマター: `name` (1-64文字, a-z0-9-), `description` (1-1024文字)
- Progressive Disclosure 3段階:
  - 起動時: ~100 tokens (スキル名+短い説明のみ)
  - アクティブ時: <5000 tokens (SKILL.md 本文)
  - 必要時: 参照ファイル
- `list_skills` ツールの出力を SKILL.md フロントマターから生成
- `invoke_skill` ツールを SKILL.md ベースの読み込みに変更
- `.well-known/agent-skills/index.json` は**将来のフェーズ**に先送り

### D-3. メモリ 4-tier lifecycle 統合（基本部分のみ）
> ⚠️ **@oracle 指摘反映**: 元PLANの4hは控えめすぎ（実質8-12h）。LRU shield / active_days / `as_of` / chain-aware pruning はフェーズ2に先送りし、基本の4-tier状態遷移のみに絞る。

参考: `dustinspace217/mcp-memory-server`, `YourMemory`
- 現在: active / archived の2状態（`tags` で表現）
- 追加:
  - **Active**: 通常の記憶（tags: `active`）
  - **Superseded**: 新しい情報で置き換えられた記憶（保持、検索対象外。tags: `superseded`）
  - **Tombstoned**: 削除された記憶（30日間の猶予期間後に物理削除。tags: `tombstoned`）
  - **Hard-deleted**: 物理削除済み（DBレコード削除）
- 実装: DBスキーマに `lifecycle_status` カラム追加（active/superseded/tombstoned）
- **後方互換**: 既存の tags ベースの active/archived 表現は `lifecycle_status` にマッピング

**先送り（フェーズ2）**:
- `as_of` パラメータ（時系列クエリ）
- LRU shield（6ヶ月アクセス保護）
- active_days / chain-aware pruning
- 自動 Superseding（重複検出時に古い記憶を自動 Supersede）

### D-4. メモリ検索のハイブリッド化強化
- 現在: Qdrant ベクトル検索 + SQLite キーワード
- 追加:
  - **FTS5 全文検索インデックス**を memory テーブルに追加
  - **KNN (Qdrant) + FTS5 (SQLite) + キーワード の3-signal ハイブリッド**
  - **RRF (Reciprocal Rank Fusion)** で3信号の結果を統合
  - **RRF 重みパラメータ**: `vector_weight`, `keyword_weight` でバランス調整可
  - **Similarity flag**: cosine ≥ 0.85 で `similarity_flag=true` (Yarlan1503 パターン)
- 後方互換: 既存の検索クエリはそのまま動作

---

## 全タスク一覧と優先度・依存関係・規模（改訂版）

| # | タスク | 優先度 | 依存 | 規模 | 柱 |
|---|--------|--------|------|------|-----|
| A-1 | SearXNG docker-compose化 | 🔴 | なし | 小 (30m) | A |
| A-2 | Dockerfile.sandbox多言語化 | 🔴 | なし | 中 (2h) | A/C |
| A-3 | SearXNG環境変数化 | 🟡 | A-1 | 小 (15m) | A |
| A-4 | 本番ビルド+全起動確認 | 🔴 | A-1,A-2 | 中 (1h) | A |
| A-5 | Docker security hardening | 🟡 | A-1 | 小 (15m) | A |
| A-6 | /health エンドポイント | 🟡 | なし | 小 (30m) | A |
| B-1 | 5ツールMCP登録 | 🔴 | なし | 中 (2h) | B |
| B-2 | sandbox名統一 | 🟡 | なし | 小 (30m) | B |
| B-3 | context_update統合 | 🟡 | なし | 中 (1h) | B |
| B-4 | フィルタ修正 | 🟡 | B-2 | 小 (5m) | B |
| B-5-1 | memory戻り値形式統一 | 🔴 | B-1 | 中 (1.5h) | B |
| B-5-2 | memory実装統合（委譲） | 🟡 | B-5-1 | 中 (2h) | B |
| B-6 | ツール説明カスタマイズ | 🟢 | なし | 小 (30m) | B |
| C-2 | JSセッション追加 | 🔴 | A-2 | 中 (2h) | C |
| C-3/C-4 | Go/Rustセッション追加 | 🟢 | A-2 | 中 (2h) | C |
| C-5 | Bashネイティブ化 | 🟡 | なし | 小 (1h) | C |
| C-6 | allowed_languages修正 | 🟡 | C-2~C-5 | 小 (5m) | C |
| D-1 | PDF OCR対応 | 🟢 | なし | 中 (2h) | D |
| D-2 | Agent Skills標準移行 | 🟢 | なし | 大 (4h) | D |
| D-3 | 4-tier lifecycle基本 | 🟢 | B-5-2 | 大 (6h) | D |
| D-4 | 検索ハイブリッド強化 | 🟢 | D-3 | 大 (4h) | D |

---

---

## 柱E: MemoryMCP スキルパッケージとして配布（次回以降）

> **発案**: 2026-06-27。MemoryMCPをAIエージェント向けのスキルパッケージとして配布し、
> Opencode等のMCPサーバ登録時の連携精度を向上させる。

### E-1. SKILL.md 作成
- MemoryMCPの全20ツールの使い方・ユースケース・ベストプラクティスを記述
- Agent Skills標準形式（フロントマター: name, description）
- Progressive Disclosure: 起動時~100 tokens / アクティブ時<5000 tokens
- AIエージェントが「このサーバで何ができるか」を事前理解できるように

### E-2. Opencode向けMCPサーバ設定テンプレート
- `opencode.json` の `mcpServers` セクションに追加する設定例
- 環境変数テンプレート込み
- ワンコマンド/ワンクリック登録を目指す

### E-3. pipパッケージ + CLI エントリポイント
- `pip install memory-mcp` でインストール可能に
- `memory-mcp serve` コマンドでサーバー起動
- `memory-mcp register` でOpencode等に自動登録（可能であれば）

### E-4. スキルディスカバリ
- AIエージェントがMemoryMCPの存在を自動検出できる仕組み
- `.well-known/agent-skills/` またはMCPプロトコルのserver info活用

---

## スコープ外（本PLAN対象外、別案件）
- 画像生成 プロバイダ追加（現状の DALL-E + Stability で十分）
- 外部 API フォールバック（Brave Search API 等）→ SearXNG 自己ホストで十分
- chat.js テストフレームワーク導入
- マルチアーキテクチャビルド (arm64)
- Playwright 移行（agent-browser CLI で十分）
- D-3 拡張（LRU shield / as_of / active_days / chain-aware pruning / 自動Superseding）
- D-2 `.well-known/agent-skills/index.json`（将来フェーズ）
- D-1 Camelot テーブル抽出（pdfplumberで十分）
