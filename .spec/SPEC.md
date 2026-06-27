# SPEC - 技術仕様・要件定義 v9

> 元PLAN: `.spec/PLAN.md` v9。@oracle レビュー反映済み。

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
  - nous の `depends_on` に `searxng` 追加
  - SearXNG デフォルトURL: `http://searxng:8080`

- [x] **A-2 (改)**: 単一sandboxコンテナ + 言語非依存イメージ
  - ベース: ubuntu:22.04
  - ランタイム: python3, nodejs, golang-go, rust (rustup経由), gcc/g++, bash
  - 単一固定コンテナ名 `sandbox`、ペルソナ別Linuxユーザー分離
  - `llm_sandbox` 依存廃止、`docker exec` ベース実行
  - データ永続: `{host_root}/memory/{persona}/sandbox/` → `/home/{persona}/` にマウント
  - パッケージ: pip --user / npm --global でペルソナ別永続化

- [ ] **A-3**: NOUS_SEARXNG_URL 環境変数化
  - 環境変数 `NOUS_SEARXNG_URL` で上書き可能
  - chat_config.py のデフォルト値を env var に
  - docker-compose.yml に `SEARXNG_URL=http://searxng:8080`

- [ ] **A-4**: 本番ビルド + 全起動確認
  - `docker compose up` で qdrant + searxng + nous 全起動
  - sandbox イメージ自動ビルド確認
  - agent-browser Chrome 起動確認（--no-sandbox フラグ検証）
  - CI docker.yml が新Dockerfileでビルド通るか確認

- [ ] **A-5**: Docker security hardening
  - sandbox: `read_only: true`, `cap_drop: [ALL]`, `tmpfs: /tmp`
  - nous: `read_only: true`（書き込みボリュームのみ rw）
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

- [ ] **B-4**: `_NOUS_TOOL_NAMES` フィルタ修正
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
  - 環境変数: `NOUS_TOOL_DESCRIPTION_OVERRIDE`
  - 形式: `tool_name=new_description` (カンマ区切り)
  - `register_tools()` で上書き

### 柱C: sandbox マルチ言語対応

- [x] **C-1 (改)**: 単一コンテナ sandbox 方式
  - service.py: llm_sandbox → docker exec 全面書換 (962→520行)
  - user_manager.py: persona別Linuxユーザー作成・削除
  - ペルソナ作成時にsandboxユーザー自動作成 (ensure_sandbox_user)

- [x] **C-2**: JavaScript セッション追加
  - docker exec 経由で node 実行
  - ルーティング: `javascript`/`js`/`node` → node 実行

- [x] **C-3**: Go セッション追加
  - docker exec 経由で go run 実行

- [x] **C-4**: Rust セッション追加
  - docker exec 経由で rustc 実行

- [x] **C-5**: Bash ネイティブ実行化
  - docker exec 経由で直接 bash 実行
  - `!` プレフィックス除去ロジックは service.py 側で維持

- [x] **C-6**: `allowed_languages` 更新 + `get_supported_languages` 追加
  - settings.py: `["python", "javascript", "bash", "go", "rust"]` — go, rust 追加済み
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

### 柱E: 環境変数依存削減 + WebUI設定完全化 (2026-06-28)

> **背景**: 現状 `RuntimeConfigManager` の優先順位は env > JSON override > default。環境変数が設定されたキーは WebUI から変更不可。APIキーは `os.environ.get()` 直読みで RuntimeConfigManager 非経由。
> **方針**: WebUI 優先のみ。env/override 切替トグルは不要。

- [ ] **E-1**: WebUI優先の設定システム（RuntimeConfigManager 改修）
  - `get_effective_value()` の優先順位を `json_override > env > default` → `json_override > default` に変更
  - 環境変数は「初回起動時の初期値」としてのみ使用し、WebUI 設定後は無視
  - 起動時: env var → json_override に一度だけコピー（json_override が空の場合のみ）
  - 既存の `SETTINGS_META` / ホットリロード / コールバック機構は維持

- [ ] **E-2**: LLM APIキーを Settings に統合（RuntimeConfigManager 管轄化）
  - `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `OPENROUTER_API_KEY` の直読み廃止
  - `Settings` クラスに `llm_api_keys` セクション追加
  - `chat_config.py` / `use_cases.py` / `_tools_skill.py` の直読み箇所を `RuntimeConfigManager` 経由に変更
  - `config_overrides.json` に平文保存（当面暗号化不要）

- [ ] **E-3**: SearXNG URL / agent-browser パス の RuntimeConfigManager 管轄化
  - `NOUS_SEARXNG_URL` / `SEARXNG_URL` の直読み (`os.environ.get()`) を `RuntimeConfigManager` 経由に統一
  - `NOUS_AGENT_BROWSER_PATH` / `AGENT_BROWSER_PATH` の直読みも同様に統一
  - chat_config.py, builtin.py, main.py の直読み箇所を修正

- [ ] **E-4**: WebUI 設定ダッシュボード拡充
  - 既存 `static/settings.js` を全設定カテゴリ対応に拡張
  - 環境変数由来の設定は `source: "env"` 表示 + WebUI値で上書き可能なトグル
  - LLM APIキー設定欄追加（パスワードフィールド）
  - 設定変更後にホットリロード状態を表示（モデル再読込中など）

### 柱F: opencode-mem プラグインパターン採用 (2026-06-28)

> **背景**: `ZeR020/opencode-mem0` のソースコード調査で Nous に即採用価値のある7パターンを発見。Phase 1 で3パターンを導入。
> **対象プラグイン**: `plugins/opencode-memory-sync/src/index.ts`

- [ ] **F-1**: `chat.message` フックで synthetic part 注入
  - `output.parts.unshift()` でメモリコンテキストを注入（既存は tool result の出力のみ）
  - `synthetic: true` フラグで再注入防止（`isNonSyntheticUserMessages` フィルタ）
  - 注入条件: `injectOn === "always"` または compaction 直後の最初のユーザーメッセージ
  - 注入コンテキスト整形: Profile + Project Knowledge + 関連メモリ（タグ検索 or 全文検索）
  - 検索API: Nous MCP の `memory_search` ツールを使用

- [ ] **F-2**: `session.compacted` イベントで compaction recovery
  - `session.compacted` イベントリスナー追加
  - compaction 後に `memory_search` で最新メモリを取得し再注入
  - `compaction.memoryLimit` (デフォルト 10) で上限制御
  - `noReply: true` で「メモリ注入のみのターン」生成（オプション）

- [ ] **F-3**: warmup 非同期化（fire-and-forget）
  - Global Symbol (`Symbol.for("nous.memory-sync.warmedup")`) で重複防止
  - warmup 処理（embedding model load + index rebuild）を IIFE で非同期実行
  - タイムアウト 30s 設定、text-only フォールバック

### 柱G: Sandbox コンテナのホストマウント永続化修正 (2026-06-28)

> **背景**: docker-compose.yml の sandbox サービスに `default` と `config` の2ペルソナのみ静的マウント。他ペルソナの sandbox データはコンテナ writable layer のみで再起動時に消失。
> **方針**: 全 `/home` を一括バインドマウント。静的マウント廃止 + テストペルソナのハードコード除去。

- [ ] **G-1**: sandbox コンテナの全 `/home` 一括バインドマウント
  - docker-compose.yml の sandbox サービス volumes を `- ./data/memory:/home` の1行に変更
  - `default` / `config` の静的マウント行を削除
  - 全ペルソナの sandbox データ (`/home/{persona}/`) がホストに永続化される
  - 注意: `useradd -m` が `/home/{persona}` を作るのでパス構造は一致

- [ ] **G-2**: `config` ペルソナのハードコード除去
  - docker-compose.yml の `config` マウント行削除（G-1で自動解決）
  - Python コードベースに `"config"` ペルソナ参照がないことを確認（調査済み: 0件）

- [ ] **G-3**: `default` ペルソナのハードコード監査・削減
  - `default` ペルソナはシステムプライマリとして維持（削除不可は正当）
  - docker-compose.yml のマウント行削除（G-1で自動解決）
  - 設定のデフォルト値としての利用箇所は許容（`settings.py`, `middleware.py` 等）

### 柱H: Dockerイメージの GHCR 配布 + CI 修正 (2026-06-28)

> **背景**: Dockerfile がプロジェクトリネーム (`memory_mcp` → `nous`) に追従しておらずビルド不能。
> docker-compose.yml の nous サービスは `image: nous:latest`（ローカル）で GHCR からプルしていない。
> GitHub Actions `docker.yml` はワークフローとして存在するが Dockerfile のパス修正が必要。

- [ ] **H-1**: Dockerfile の `memory_mcp` → `nous` 修正
  - `APP_HOME`: `/opt/memory-mcp` → `/opt/nous`
  - `MEMORY_MCP_DATA_ROOT` → `NOUS_DATA_ROOT=/opt/nous/data`
  - `COPY memory_mcp/` → `COPY nous/`
  - `CMD ["python", "-m", "memory_mcp.main"]` → `CMD ["python", "-m", "nous.main"]`

- [ ] **H-2**: docker-compose.yml の nous サービスを GHCR イメージに変更
  - `image: nous:latest` → `image: ghcr.io/solidlime/nous:latest`
  - `build:` セクション不要（CI がビルド担当）
  - `env_file: .env` は維持

- [ ] **H-3**: GitHub Actions `docker.yml` の修正
  - COPY パスが `nous/` になっているか確認
  - イメージ名: `ghcr.io/${{ github.repository_owner }}/nous` (小文字)
  - トリガー・タグ戦略は現状のまま維持

### 柱I: default ペルソナ廃止 + 初期セットアップ画面 (2026-06-28)

> **背景**: `default` ペルソナがシステム前提としてハードコードされている。ユーザーにとって意味のない名前であり、本来はユーザー自身に決めさせるべき。
> **方針**: `default` の新規作成を廃止。ペルソナ未作成の状態を許容し、WebUI 初回アクセス時にセットアップを促す。

- [ ] **I-1**: Settings.default_persona → None
  - `settings.py`: `default_persona: str = "default"` → `str | None = None`
  - 起動時にペルソナ未作成なら空のまま

- [ ] **I-2**: MCP ツールのペルソナ未指定エラー
  - `middleware.py`: persona 未指定 → エラー `"No persona configured. Create one at the WebUI dashboard."`
  - `chat_config.py`: persona 未指定 → エラー
  - エラーコード: `PERSONA_REQUIRED`

- [ ] **I-3**: WebUI 初期セットアップ画面
  - `GET /dashboard` → APIでペルソナ一覧取得 → 0件ならセットアップ HTML
  - セットアップ画面: ペルソナ名入力 → `POST /api/personas` → 作成成功 → `/dashboard/{new_persona}` にリダイレクト
  - 既存ペルソナがある場合: 従来通り選択画面または最後に使ったペルソナへ

- [ ] **I-4**: default 削除禁止コード除去
  - `persona.py:294`: `if persona == "default":` 削除禁止 → 削除
  - `sections/persona.py`: フロントエンドの default 削除禁止表示除去

- [ ] **I-5**: 後方互換
  - 既存 DB の `default` ペルソナはそのまま残る（破壊しない）
  - `PERSONA` / `NOUS_DEFAULT_PERSONA` 環境変数を設定していれば従来通り動作
  - MCP クライアントが `PERSONA=default` を送ってきた場合、存在すれば使う・なければエラー

---

## 非機能要件

- **パフォーマンス**: sandbox イメージビルド時間 10分以内、コンテナ起動 30秒以内
- **セキュリティ**: sandbox コンテナは read_only + cap_drop ALL、全コンテナ no-new-privileges
- **後方互換性**: 既存 MCP クライアントとの互換性維持（B-5はMCP→dict形式統一で破壊的変更なし）
- **テスト**: 全変更後 1360+ tests がパスすること、新規コードにはテスト追加
- **CI**: docker.yml / ci.yml 両方を通すこと

## 技術構成

- **言語・フレームワーク**: Python 3.14, FastMCP, asyncio
- **インフラ・環境**: Docker Compose (Qdrant + SearXNG + nous)
- **sandbox**: docker-py, 単一 ubuntu:22.04 コンテナ + Linuxユーザー分離
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
