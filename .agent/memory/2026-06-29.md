# MEMORY

## プロジェクト概要
Nous: 日本語特化の永続記憶 MCP サーバー。SQLite + Qdrant + Ebbinghaus 忘却曲線。WebUIダッシュボード付き。
3レイヤー構造（L1:MCP拡張, L2:EventBus基盤, L3:OpenCode Plugin）。

## 学習した知識・教訓

### sandbox_context pip_packages + auto_emotion（2026-06-29）
- `_tool_sandbox_context()` は常にJSONを返す設計に。sandbox無効時もスケルトンJSON（pip_packages:[]含む）を返し、エラー文字列を返さない
- `session.get_context()` は既に pip3 list --user --format=json をパースして pip_packages を返す（service.py L453-468）。_tool_sandbox_context はそれをそのまま利用
- `_tool_memory_create()` の auto_emotion フラグ: 現状常にTrue（emotionパラメータ未実装のため）。将来 explicit emotion 指定を追加したら False に分岐

### CSS/JS 静的ファイル分離（2026-06-21）
- chat.py: 2714行のモノリスから `<style>` (586行) と JS (1710行) を抽出、417行に縮小
- 静的ファイルサーブ: `mcp.custom_route("/static/{filepath:path}")` で実装。FastMCPは `.mount()` 未対応
- Python文字列からの抽出はWSL Pythonスクリプトで。PowerShellのヒアドキュメントは `<` 記号でパースエラー → `write` ツールで.py保存→WSLで実行
- テスト更新: `render_chat_js()` → ファイル読込 `_read_chat_js()` に切替。E402に注意

### ブラウザ自動テスト（2026-06-21）
- `agent-browser` CLI: PowerShellでは `@` エスケープ必須 (`'@eN'`)。長時間 `wait` はデーモン破壊
- WSLコマンド: `wsl -d Ubuntu -- bash -c "..."` 形式。複雑JSONは一時ファイル経由
- Nousサーバー: `.venv/bin/python -m nous.main`。`pkill` で停止

### browser / search チャットツール（2026-06-21）
- **browser ツール**: `builtin.py::_handle_browser()` — agent-browser CLI経由で汎用ブラウザ操作。open/snapshot/click/fill/get/wait/scroll/close。web_searchは完全削除
- **search ツール**: `builtin.py::_handle_search()` — httpxでSearXNG JSON API (/search?format=json) 呼出。外部bot検出回避
- 検索エンジンCAPTCHA: DuckDuckGo/Google/Brave/Mojeek ×。SearXNG自己ホストで回避
- agent-browser eval: 戻り値は自動JSONシリアライズ → JS側で `JSON.stringify()` すると二重エンコードバグ
- チャットツール定義: `definitions.py` の ToolDefinition + `builtin.py` のハンドラ + `_BUILTIN_DISPATCH` の3点セット必須
- DBマイグレーション: カラム追加時は `save()` に `ALTER TABLE ADD COLUMN IF NOT EXISTS` 動的追加 + 移行ファイル + `__init__.py` 登録

### CIデバッグ教訓（2026-06-21）
- ruff format: `tests/` も対象。`__init__.py` が空でもチェックされる
- Bandit: シェルインジェクションは `# nosec B602` を正確な行に。subprocess+shellはB602、subprocess引数はB603
- カバレッジ: 外部プロセス呼出は `# pragma: no cover`。`--cov-fail-under` は現実的な値に

### コードベース健全化リファクタリング（2026-06-20）
- tools.py 分割: TOOL_DISPATCH + @mcp.tool() ラッパーのみ残す（2107→431行）、7カテゴリファイルに分割
- `normalize_importance()` 統一: `max(0.0,min(1.0))` 5箇所→value_objects.pyに集約
- `_VALID_EMOTIONS`: API層→domain/value_objects.pyに移動
- E402修正: `logger = getLogger()` が import より前に来るとruffエラー→import群の後に移動
- SIM105: `try/except PermissionError: pass` → `contextlib.suppress(PermissionError)`

### emotion_type → emotion 全層統一（2026-06-20）
- Pydantic v2で `Field(alias="emotion_type")` + `populate_by_name=True` 必須
- 6層の修正箇所: DB schema→domain entity→API model→MCP param→LLM prompt→frontend JS

### EventBus + SSE 基盤（2026-06-17）
- EventBus: asyncio Queueベースのpub/sub。全20 MCPツールにtool.calledイベント追加済み

### Chat ロールバック（2026-06-17）
- POST /api/chat/{persona}/sessions/{session_id}/rollback {keep_until: N}。存在しないセッションは404

### WSL2 + Docker バインドマウント（2026-06-07）
- uid合わせ。絶対パス指定。自前Dockerfile: `FROM python:3.11-slim-bullseye`

### 画像E2Eパイプライン（2026-06-08）
- OpenAI互換: `content: [{type: text}, {type: image_url}]`。DOMPurify: img許可設定追加

### コミットワークフロー
- SSHリモート: `git remote set-url origin git@github.com:solidlime/Nous.git`
- HTTPSが認証失敗する場合のフォールバック
- `ruff check → 0 errors` を維持。pytest: 1085 pass / 1 fail (test_settings既存バグ)

### MCP Capabilities 業界調査 (2026-06-27)
詳細: `docs/mcp_research_2026-06-27.md` (35+プロジェクト調査)

#### 画像生成パターン
- **Capability Discovery Protocol**: 各プロバイダーの `discover_capabilities()` が起動時に能力返却。ルーターが enum ではなく capability サーフェスに問い合わせる
- **環境変数プレフィックス**: `<SERVER>_<PROVIDER>_<FIELD>` 命名規則が業界標準
- **画像返却**: base64 MCP `ImageContent` が最も一般的（MemoryMCPは準拠済み）
- **Hexagonal Architecture**: Domain/Application/Infrastructure/McpHost 6レイヤー分離で新プロバイダー追加が容易
- **fail-fast startup + stderr分離 + FluentValidation** の3点セット

#### PDF処理パターン
- **ライブラリフォールバック連鎖**: テキスト抽出は PyMuPDF→pdfplumber→pypdf、テーブルは Camelot→pdfplumber→Tabula
- **OCR判定閾値**: ページテキスト ≥ 30文字 → native、< 30文字 → OCR fallback
- **キャッシュ戦略**: SQLiteに メタデータ・ページ単位テキスト・画像path保存。base64より軽量
- **コアロジック分離**: `pdf_utils.py` をMCP非依存に分離（テスト容易性）
- **必須システム依存**: tesseract-ocr, tesseract-ocr-jpn, ghostscript, default-jre-headless, poppler-utils, pandoc
- **エンジン選択**: "native" / "auto" / "smart" / "ocr" / "force_ocr" を LLMに選択させる

#### Skills/Plugins 標準
- **Agent Skills 標準** (https://agentskills.io/specification): `SKILL.md` 形式が業界標準
- **フロントマター**: `name` (1-64文字, a-z0-9-) + `description` (1-1024文字) 必須
- **Progressive Disclosure (3段階)**: 起動時name/description (~100 tokens) → アクティブ時SKILL.md全体 (<5000 tokens) → 必要に応じて参照ファイル
- **Claude Code Issue #21545**: 全MCPツールのfull schemaロードで30-40%コンテキスト消費 → lazy-load 必須要件
- **Anthropic code-execution**: 150K→2K tokens (98.7%削減) の `search_tools` パターン
- **`/well-known/agent-skills/index.json`**: 外部スキル発見の業界標準化進行中

#### Memory/Persistence パターン
- **4-tier lifecycle**: Active → Superseded → Tombstoned → Hard-deleted (NousのEbbinghausに統合候補)
- **ハイブリッド検索 (RRF)**: KNN (vector) + FTS5 (BM25) → RRF でマージが業界標準
- **WAL + 5秒 busy_timeout + CASCADE delete** が並行アクセスの最低条件
- **時系列クエリ `as_of` パラメータ**: 過去時点のグラフ状態を復元
- **エンティティ名正規化**: 大文字小文字・区切り文字を無視した一致
- **size cap + 6-month LRU shield** が長期運用で必須
- **active_days 概念**: ユーザー活動期間のみカウント（休暇で記憶喪失しない）
- **chain-aware pruning**: グラフ隣接が高い記憶は連鎖して延命
- **embedding失敗時の graceful degradation**: LIKE-onlyフォールバック
- **Tool description カスタマイズ環境変数**: LLMパフォーマンス直結
- **FSRS (power-law) > Ebbinghaus (exponential)**: 人間の記憶に正確だが実装複雑度高

#### Docker デプロイパターン
- **`depends_on with condition: service_healthy`**: 依存サービスのヘルスチェック後に起動
- **DooD vs DinD**: socket マウント = root-level ホストアクセス権（特権昇格ベクトル）。信頼できるイメージのみ
- **Docker MCP Toolkit のリソース制限**: 1 CPU / 2 GB が参考値
- **nginx + SSE の落とし穴**: `proxy_buffering off` 必須（デフォルトでリアルタイム性が壊れる）
- **Hardening 3点セット**: `read_only: true` + `tmpfs: /tmp` + `cap_drop: [ALL]`
- **Health check endpoint `/health`**: FastMCP の `custom_route` で実装
- **Image signing + SBOM**: エンタープライズ要件

#### Nous 現状評価
| 領域 | 現状 | 業界標準 | 評価 |
|---|---|---|---|
| 画像生成 | OpenAI互換content配列 | base64 ImageContent | ◎ 標準準拠 |
| PDF | 無し | フォールバック連鎖+OCR | △ 機会あり |
| スキル | plugins/着手 | SKILL.md標準 | ○ 進行中 |
| メモリ | SQLite+Qdrant+Ebbinghaus | SQLite+4-tier+RRF | ◎ 高レベル |
| Docker | sandbox着手 | DooD+secrets+healthcheck | ◎ 良好 |

### 4-tier lifecycle 論理削除（2026-06-27）
- `lifecycle_status TEXT DEFAULT 'active'` カラム追加 (v028 migration)
- `"active"` tag は Goal/Promise status 専用。lifecycle_status とは独立管理
- `memory_delete` は論理削除 (tombstone) に変更: `lifecycle_status = "tombstoned"`
- Qdrant ポイントは物理削除（tombstone時に delete）
- 全 SELECT クエリで `WHERE lifecycle_status != 'tombstoned'` フィルタ
- `find_by_key()` は tombstoned も取得可能（リカバリ用）
- `_active_where()` 静的メソッドでフィルタ統一
- `sqlite3.Row.get()` は Python 3.14 でも未実装 → `row["col"] if "col" in row.keys()` で代替
- InMemory test repos にも `tombstone()` 追加必須

### item_* 7ツール → item 1ツール統合（2026-06-29）
- `_tool_item(operation, ...)` 統合関数: operation="add/remove/equip/unequip/update/search/history" で分岐
- `_tools_item.py` に `_tool_item()` 追加、既存 sub-tool を呼び出すだけの薄いディスパッチャ
- `tools.py` に `item` ツール登録 + `TOOL_DISPATCH["item"]` 追加
- 旧7ツールは **完全削除済み**（`_tools_item.py` の内部関数は維持、`_tool_item()` が呼出）
- `definitions.py` の `_NOUS_TOOL_NAMES` に `"item"` 追加、旧7名削除
- テスト: 旧ツールテスト削除、統合ツールテスト8件のみ（全 operation + unknown）
- デザインパターン: `sandbox_files(operation=...)` と同一設計

#### 次アクション候補
1. **PDF capability**: PyMuPDF+pdfplumber+Tesseract-jpn フォールバック
2. **Agent Skills 標準正式移行**: 既存 plugins/ を SKILL.md 形式統一
3. **4-tier lifecycle 統合**: Ebbinghaus に active/superseded/tombstoned/hard-deleted
4. **KNN+FTS5+RRF**: Qdrant 維持しつつ SQLite FTS5 も活用
5. **Docker hardening 強化**: sandbox image に `read_only+cap_drop` 追加
6. **Health check `/health`**: FastMCP custom_route で実装
7. **`as_of` パラメータ**: 時系列クエリ対応
8. **Tool description カスタマイズ環境変数**: `NOUS_TOOL_*_DESCRIPTION`

### OpenCode Memory Plugin 業界調査 (2026-06-28)
詳細: 調査レポート（本セッション出力）参照

#### opencode-mem エコシステム全体像
- **デファクト**: `tickernelz/opencode-mem` (977★, npm v2.17.3, weekly DL 3.3K, 96 forks, 65 versions)
- **注目フォーク**:
  - `ZeR020/opencode-mem0` — 7-factor scoring + STM/LTM (Ebbinghaus curve) + hybrid search
  - `clopca/open-mem` — multi-platform (OpenCode/Claude/Cursor/MCP) + 知識グラフ + AGENTS.md auto-gen
  - `LautaroSanz/opencode-mem` — claude-mem の OpenCode 移植 (Bun MCP server + worker)
  - `csuwl/opencode-memory-plugin` — OpenClaw 9ファイル記憶モデル
  - `transportrefer/opencode-memory-plugin` — Markdown-only (ベクトル無し)
  - `jdormit/opencode-memsearch` — `nicobako/memsearch` ベース、daemon modeで 5-10s → 50ms
- **PyPI 兄弟**: `opencode-memory` (FAISS+OpenAI), `openmem-engine` (BM25+グラフ+競合的活性化), `opencode-semantic-memory` (FTS5+ベクトル+GitLab ingest)

#### 共通アーキテクチャパターン
- **Hooks**: `chat.message` + `experimental.session.compacting` + `experimental.chat.system.transform` + `tool.execute.after`
- **コンテナタグ**: `opencode_project_<sha16>` (cwd の git remote or project root) / `opencode_user_<sha16>` (git config user.email)。shadow shard 問題を回避するため subpath export (`opencode-mem/tags`) で正規化
- **API キー解決 3形式**: `sk-...` / `file://path` / `env://VAR` (secret-resolver pattern)
- **公開 subpath エクスポート**: 3rd party plugin が同じ shard に書ける
- **WebUI ポート**: 4747 が業界標準（opencode-mem）、3737 (open-mem)

#### 採用候補アイデア
- **🔴 Priority 1** (短期):
  - `experimental.chat.system.transform` で progressive disclosure 注入
  - `chatMessage.enabled/maxMemories/injectOn` 設定 (opencode-mem 互換)
  - コンテナタグ `nous_project_<sha>` / `nous_user_<sha>` + `nous/tags` subpath
  - `experimental.session.compacting` 再注入 (compaction.memoryLimit)
- **🟡 Priority 2** (認知科学):
  - **7-factor scoring** (recency 20%, frequency 15%, importance, utility 20%, novelty, confidence 10%, interference) — ZeR020
  - **STM/LTM auto-promotion** (strength > 0.7 AND access > 3 → LTM, Ebbinghaus curve)
  - **Memory Economics footer** (compression ratio 表示)
  - **Conflict resolution** (interference > 0.3 で警告 + tombstone)
- **🟢 Priority 3** (設計刷新):
  - `MemoryEngine` interface 抽出 (clopca/open-mem の ports-and-adapters)
  - Multi-platform adapters (Nous MCP の強みを更に生かす)
  - AGENTS.md auto-generation (dispersed / single mode)
  - Knowledge graph (entities + relationships) — Goal/Promise 関係の表現

#### opencode-mem の落とし穴（避けるべき）
- **shadow shard**: タグ文字列規約違反で silent filter
- **warmup 70秒ハング**: embedding モデルロード → fire-and-forget 必須
- **LLM 圧縮が opaque**: type 判定を LLM 任せにすると再現性下がる
- **deduplication 閾値 0.9 が緩い**: ほぼ同内容しか統合されない

#### Nous 既存 L3 プラグイン (`opencode-memory-sync`, 91行)
- `chat.message` → session.started
- `tool.execute.before/after` → tool.called / tool.result
- `experimental.session.compacting` → session.compact
- `dispose` → session.stopped
- 全てを `POST /api/events/ingest` で Nous MCP に送信するだけの **イベント取得器**
- AI 圧縮・自動注入・スコープ・重複排除は未実装 → 拡張の余地大量
