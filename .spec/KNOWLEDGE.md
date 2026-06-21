# KNOWLEDGE - ドメイン知識・調査結果

## 業務・ドメイン知識
- Hindsight (vectorize-io/hindsight) はエージェント向け長期記憶システム。Retain/Recall/Reflect の3操作モデル
- MemoryMCP は Hindsight の主要機能の半分以上を既に実装済み（hybrid search, RRF, cross-encoder, reflection, entity extraction）
- ギャップとして date_range 検索フィルタ、重要度自動評価、関係性自動抽出、メンタルモデル抽象化を特定

## 調査・リサーチ結果
- Hindsight 公式: https://hindsight.vectorize.io
- Hindsight GitHub: https://github.com/vectorize-io/hindsight (13.2k stars)
- MemoryMCP の検索パイプライン: MCP tool → SearchQuery → SearchEngine → Strategies → SQLite/Qdrant
- LLM 基盤: infrastructure/llm/ 配下に Anthropic/OpenAI/OpenRouter の3プロバイダ対応

## 技術的な知見

### P1: date_range 検索統合
- `parse_date_range()` は日本語相対日時表現（昨日、先週、7d等）を解析済み
- 検索パイプラインの各層（Protocol → Strategy → Repository → Engine）に date_from/date_to を追加
- Qdrant は payload に created_at がないため、アダプタ層でポストフィルタ（fetch_limit×3 → 日付フィルタ → top_k）
- SQLite は `created_at` カラムに既存インデックス（v007 migration）あり

### P2+P3: 記憶エンリッチメント
- 1回のLLM呼出で importance + entity relations を同時抽出（コスト最適化）
- MemoryService.create_memory() 内で best-effort で実行（例外時も作成は継続）
- importance 明示指定時（≠0.5）は完全スキップ
- type_classifier + entity_extractor の結果をLLMプロンプトに注入しトークン削減
- JSON structured output で確実なパース

### P4: メンタルモデル抽象化
- type_classifier のタイプタグ（decision/preference/milestone/problem/emotional）を利用して記憶をグループ化
- 同一タイプの記憶が N 件（デフォルト3）蓄積されたら LLM でパターン抽象化
- タイプ別に最終抽象化時刻をメタ記憶で管理し、重複実行を防止
- Reflection（24h全記憶）とは異なり、タイプ特化・蓄積トリガーの設計

## 決定事項と理由
- **P2+P3 統合**: 別々のLLM呼出より1回に統合する方がコスト効率が良い。importanceとrelationは同じ記憶から抽出するため情報の重複が多い
- **P2 即時処理**: バッチ処理より即時処理の方がシンプル。importance は作成時に決まるべき情報
- **P4 バッチ処理**: メンタルモデルは複数記憶の蓄積を待つ必要があるため、バッチ（トリガー）方式が自然
- **Qdrant ポストフィルタ方式**: payload に created_at を追加するには全upsert箇所の修正と再構築が必要。アダプタ層フィルタの方が低侵襲

## フロントエンド改善（2026-05-15）で得た知見

### chat.py 構造
- 2190行→1910行に削減（死にコード280行削除）
- CSSは12-416行、JSは約700行以降に分離（Python文字列リテラル内）
- 設定パネルHTMLは `<details>` アコーディオン化（10セクション→9セクション）
- Sandbox panel JSは完全に削除。`sandboxLog`/`sandboxRunBlock`/`sandboxAddArtifact`/`renderCodeBlock` はコードブロックRunボタン用に保持
- `MEMORY_TOOL_NAMES` はMCPツール5個→builtin含む17個に拡張

### バックエンド連携
- `extract_max_tokens` と `enable_memory_tools` は既に `ChatConfig` に存在（UI追加のみで可）
- `debug_mode` は `ChatConfig` に新規追加
- `/api/chat/{persona}/tool` エンドポイントを新規追加（builtin tool直接実行用）
- `promise_cancel` を `builtin.py` + `definitions.py` に追加（`goal_cancel` 同パターン）
- `memory_search` builtin上限を10→200に

### テスト修正
- sandboxターミナル履歴（ArrowUp/ArrowDown）テストをCoding Agent移行に合わせて更新
- sandboxInstallPackages/sandboxResetテストをsandboxRunBlockに変更
- `search_memory` の `mode` パラメータ削除に伴いテストの `mode="keyword"` を `mode="hybrid"` に

### F020: メモリタイムライン可視化（2026-05-15）
- vis-timeline standalone UMD ビルドを使用（vis-data, moment.js 内包）
- データソース: `GET /api/observations/{persona}` から最大5ページ取得しクライアント側フィルタ
- 21種感情色マッピング + 絵文字。重要度でフォントサイズ変動（0.65rem + imp*0.2）
- showSkeleton スキップ対象（#tl-loading で自前ローディング管理）
- ダッシュボードタブ順: overview→analytics→memories→**timeline**→graph→…→admin
- Alt+1〜0 ショートカット（Alt+4=Timeline）

---

## コンテキスト圧縮実装（2026-06-09）で得た知見

### アーキテクチャ
- **パイプライン位置**: `PrepareStep → PromptBuildStep → CompressStep → InferenceStep → PostProcessStep`
- **CompressStep は PromptBuildStep と InferenceStep の間に差し込む**。system_prompt と session_messages の両方を動的圧縮
- **`max_window_turns` 廃止の判断**: Pydantic v2 の `@property` + `@field_validator` の名前衝突問題で断念。後方互換を保つため Pydantic field として残し（default 100、validator 1-500）、内部で `max_stored_messages` と併存

### TokenCounter 設計
- **tiktoken 優先 + CJKヒューリスティックの2段階**: 高精度が必要な時は tiktoken、それ以外は軽量ヒューリスティック
- **ヒューリスティックの罠**: ひらがなは CJK Unicode 範囲（U+4E00-U+9FFF）に含まれない。ひらがなは U+3040-U+30FF。テストでは漢字を使う必要あり
- **モデル別最大コンテキスト**: 全モデルを辞書にハードコード。未定義は 128K をデフォルト。OpenRouter の `provider/model` プレフィックスは `split('/', 1)[1]` で除去

### 圧縮戦略
- **3段階圧縮**: システムプロンプトトリミング→ツール結果クリア→会話履歴トランケート。前段が効けば後段スキップ
- **システムプロンプト圧縮はLLM不要**: 単純なセクション分割＋行数制限で動作。4モード（auto/light/normal/aggressive）で記憶保持数・スキル説明長を調整
- **ツール結果クリア**: 古い `role=tool` メッセージの content を `[cleared]` に置換。`tool_call_id` は Anthropic の validation に必要なので維持
- **LLMベースの会話要約は未実装**: 現行はトランケートのみ。summarizer.py を再利用して後日追加可能

### ChatConfig 設計
- **Pydantic v2 の制約**: `@property` と Pydantic field は同名不可。`max_window_turns` を property 化する案は v2 で型エラー。Pydantic field として残しつつ validator 範囲を 1-500 に拡大
- **SQLite CRUD の `len(row) > N` フォールバック**: 新カラム追加時、既存DBとの互換性を保つため `row[29] if len(row) > 29 else default` パターンを使用
- **save() の VALUES プレースホルダー数**: 新カラム追加時、`?` の数をパラメータ数と一致させる必要あり。不一致時は SQLite が `OperationalError`

### 並列ツール実行
- **`asyncio.gather` で一括実行**: すべてのツール呼出を先に yield して UI に進行表示、その後 gather で並列実行
- **`enable_parallel_tools` フラグ**: デバッグ用に逐次実行にもフォールバック可能。デフォルト True
- **SSE 順序**: ToolCallSSE（全件）→ ToolResultSSE（全件）。従来の ToolCallSSE→ToolResultSSE 交互出力から変更

### テスト戦略
- **CompressStep は `config.context_max_tokens` で制御**: テストでは tiny budget（200 tokens）を設定し動作確認。get_model_max_tokens() のハードコード値（128K）に依存しないよう `context_max_tokens` を優先
- **TokenCounter の CJK 検出**: テスト文字列は漢字（`今日天気`）を使用。ひらがなは ASCII ブランチに落ちる
- **ChatConfig の後方互換**: `max_window_turns` の get/save 確認、property でないことの確認、model_dump に含まれないことの確認

---

## コードベース健全化リファクタリング（2026-06-20）

### tools.py 分割
- `_split_tools.py` スクリプトで自動分割。7ファイル（_tools_memory/persona/item/sandbox/goal/skill/helpers）に分割
- tools.py は TOOL_DISPATCH + @mcp.tool() ラッパー + _resolve_persona のみを残す（2107→431行）
- テストの mock_app_context に `event_bus = AsyncMock()` が必要（_tools_memory が EventBus を使用するため）

### normalize_importance 統一
- `max(0.0, min(1.0, ...))` が5箇所に散在 → `normalize_importance()` で統一（value_objects.py）
- 呼出元: memory_enricher, domain/memory/service, domain/chat_config, domain/persona/service
- chat_config.py の Pydantic field_validator 内でも問題なく使用可能

### DEPRECATED endpoint 削除
- `/api/stats/{persona}` → `/api/dashboard/{persona}`（stats は `data["stats"]` にネスト）
- `/api/recent/{persona}` → `/api/observations/{persona}?mode=recent&per_page=N`
- `/api/chat/{persona}/sandbox/tree` → `/api/chat/{persona}/sandbox/files?recursive=true`
- テストのアサーションを新レスポンス形式に合わせて修正必要（特に dashboard のネスト構造）

### ruff クリーンアップ
- `use_cases.py` の E402: `logger = getLogger()` が import より前に来ていた → import 群の後に移動
- `sandbox/service.py` の SIM105: `try/except PermissionError: pass` → `contextlib.suppress(PermissionError)`
- W293（空白行スペース）は `ruff --fix` で自動修正可能

### emotion_type → emotion 全層統一
- **DB不一致**: `memories.emotion` と `emotion_history.emotion_type` でカラム名が異なっていた（emotion_history側はDBマイグレーション未着手で後回し）
- **バリデーション不一致**: `_VALID_EMOTIONS`（22感情）と `ALLOWED_EMOTIONS`（22感情）が8感情で不一致。`_EMOTION_KEYWORD_MAP` に envy/gratitude/contempt を追加し25感情に統一。`ALLOWED_EMOTIONS` は `_VALID_EMOTIONS` から派生するよう修正
- **ドメイン層**: `EmotionRecord.emotion_type` → `emotion` にリネーム（entity + repo + service 全参照更新）
- **API後方互換**: Pydanticモデルで `Field(alias="emotion_type")` + `populate_by_name=True` を設定し、`emotion` と `emotion_type` 両方の入力を受け付ける
- **変換ロジック削除**: HTTP/MCP/LLMの全レイヤーに散在していた `emotion_type`→`emotion` 手動変換（10箇所以上）を削除
- **フロントエンドJS**: sections/ 配下4ファイル（memories, timeline, knowledge_graph, analytics）の全 `emotion_type` → `emotion`
- **テスト**: Pydantic v2 では `Field(alias=...)` はデフォルトで canonical 名を受け付けないため `populate_by_name=True` が必須。テストのAPIリクエストで `emotion_type`→`emotion` に変更したらこの問題が表面化
- **学習**: 全層統一には (1)DBカラム (2)domain entity (3)API input/output model (4)MCPパラメータ (5)フロントエンドJS (6)テスト の6層を漏れなく変更する必要がある。後方互換が不要なら alias なしの単純リネームがベスト

---

## chat.py CSS/JS 静的ファイル分離（2026-06-21）

### 抽出戦略
- chat.py の `<style>` (13-600行) と JS (1003-2714行) を Python 文字列から static/ に抽出
- Python のヒアドキュメント編集は行数が多すぎるため不可 → WSL内でPythonスクリプトで文字列操作
- PowerShell のヒアドキュメント制約: `<link` がリダイレクト演算子として解釈 → `write` ツールで `.py` 保存→WSLで実行
- 結果: 2714行 → 417行 (82%削減)

### 静的ファイルサーブ
- FastMCP は `mount()` 非対応 → `mcp.custom_route("/static/{filepath:path}")` で自作
- パストラバーサル対策: `os.path.normpath` + `..` チェック
- テスト互換性: `mcp.streamable_http_app()` のフローを壊さない。`create_app()` の戻り値型維持

### テスト移行
- `render_chat_js()` がJSコードを返さなくなった（`<script src>` のみ）
- → `_read_chat_js()` ヘルパーで `static/chat.js` を直接読込
- E402: 関数定義の後に import を置くと ruff エラー → import 群の後に関数定義を移動
- pytest: 46 pass (test_chat_service.py)、1085 pass (全体)

### ブラウザテスト知見
- agent-browser: PowerShell環境では `@eN` をシングルクォートでエスケープ必須
- `wait --load` はデーモン破壊リスク → `wait N` (ms) + `snapshot` のポーリング方式
- sandbox グローバル無効化: `MEMORY_MCP_SANDBOX__ENABLED=false` がWindows環境変数で設定
- WSL内コマンド: `wsl -d Ubuntu -- bash -c "..."` でPowerShell→WSLブリッジ
- 複雑なJSONはWSL内で一時ファイル→curl が安全
