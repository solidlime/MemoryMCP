# Memory MCP Server

MCP (Model Context Protocol) 準拠の永続メモリサーバー。RAG検索とメタデータフィルタリングで、Personaごとの記憶を管理します。

## 特徴

- **永続メモリ**: SQLite (データ) + Qdrant (ベクトルインデックス)
- **Personaサポート**: `Authorization: Bearer <persona>` でPersona分離
- **高精度RAG検索**:
  - セマンティック検索（埋め込み + Reranker）
  - ハイブリッド検索（セマンティック70% + キーワード30%）
  - 時間フィルタリング（「昨日」「先週」などの自然言語対応）
  - メタデータエンリッチメント（タグ、感情、環境、状態を埋め込みに含める）
- **リッチコンテキスト**: 重要度・感情・状態・環境・行動タグなど15カラムで記録
- **自動整理**:
  - アイドル時の重複検知（類似度90%以上）
  - 自動マージ（類似度95%以上、オプション）
  - 自動要約スケジューラー（日次/週次、デフォルト有効）
  - ベクトルストア自動リビルド
- **優先度スコアリング**: 重要度 × 時間減衰 × アクセス頻度の複合スコア
- **Webダッシュボード**: 統計・日次推移・知識グラフの可視化
- **最適化Docker**: 2.65GB (CPU版PyTorch)
- **統合API**: 3つの統合ツールで簡潔なインターフェース (75%削減)
- **GitHub Copilot Skills対応**: トークン消費80〜90%削減 🚀

## MCPツール API

### 公開ツール (3つ)

#### 1. `get_context()`
現在のペルソナの状態、時刻、メモリ統計を取得。**毎回のレスポンス時に呼び出すこと**。

#### 2. `memory(operation, ...)`
統合メモリ操作インターフェース。

**Operations:**
- `create`: 新規メモリ作成
- `update`: メモリ更新
- `delete`: メモリ削除
- `search`: 統合検索（semantic/keyword/hybrid/related/smart）
- `check_routines`: 現在時刻の繰り返しパターン検出
- `anniversary`: 記念日管理（追加/削除/一覧）
- `stats`: メモリ統計取得

**検索モード:**
- `semantic`: セマンティック検索（デフォルト、RAG）
- `keyword`: キーワード検索（Fuzzy対応）
- `hybrid`: ハイブリッド検索（semantic 70% + keyword 30%）
- `related`: 関連記憶検索（指定記憶と類似）
- `smart`: スマート検索（曖昧なクエリを自動的にコンテキスト拡張）

**時間フィルタリング:**
- 自然言語対応: 「今日」「昨日」「先週」「今週」「今月」「3日前」
- 日付範囲指定: `date_range="2025-11-01,2025-11-15"`
- semantic/hybrid/keywordモード全対応

**例:**
```python
# 作成
memory(operation="create", content="User likes strawberry",
       emotion_type="joy", importance=0.8)

# 記念日タグ付き作成
memory(operation="create", content="初めて一緒に映画を見た日",
       emotion_type="joy", importance=0.9,
       context_tags=["first_time", "anniversary"])

memory(operation="create", content="プロジェクトのリリース完了",
       emotion_type="accomplishment", importance=0.85,
       context_tags=["milestone", "technical_achievement"])

# セマンティック検索（デフォルト）
memory(operation="search", query="好きな食べ物", mode="semantic", top_k=5)

# キーワード検索
memory(operation="search", query="Python", mode="keyword", fuzzy_match=True)

# ハイブリッド検索（semantic 70% + keyword 30%）
memory(operation="search", query="プロジェクト", mode="hybrid")

# 時間フィルタリング
memory(operation="search", query="成果", mode="semantic", date_range="昨日")
memory(operation="search", query="", mode="keyword", date_range="先週")

# タグ検索
memory(operation="search", query="", mode="keyword",
       search_tags=["technical_achievement"], tag_match_mode="all")

# スマート検索（曖昧クエリ自動拡張、日英対応）
memory(operation="search", query="いつものあれ", mode="smart")  # 日本語
memory(operation="search", query="the usual", mode="smart")  # English
memory(operation="search", query="約束", mode="smart")  # 自動でpromiseタグ追加

# ルーティンチェック
memory(operation="check_routines")  # 現在時刻の繰り返しパターン検出
memory(operation="check_routines", mode="detailed")  # 詳細：時間帯別パターン分析

# 記念日管理
memory(operation="anniversary")  # 一覧表示
memory(operation="anniversary", content="結婚記念日",
       persona_info={"date": "10-28", "recurring": True})  # 追加
memory(operation="anniversary", content="結婚記念日")  # 削除

# 身体感覚記録
memory(operation="sensation")  # 現在の感覚表示
memory(operation="sensation", persona_info={
    "fatigue": 0.3, "warmth": 0.8, "arousal": 0.6,
    "touch_response": "sensitive", "heart_rate_metaphor": "elevated"
})  # 感覚更新

# 感情変化追跡
memory(operation="emotion_flow")  # 履歴表示
memory(operation="emotion_flow", emotion_type="love", emotion_intensity=0.95)  # 記録

# 状況分析（情報提供）
memory(operation="situation_context")  # 現在の状況分析と類似記憶
```

#### 3. `item(operation, ...)`
統合アイテム/装備操作インターフェース。

**Operations:**
- `add`: インベントリにアイテム追加
- `remove`: インベントリからアイテム削除
- `equip`: アイテム装備（指定スロットのみ）
- `unequip`: アイテム装備解除（単一/複数スロット）
- `update`: アイテムメタデータ更新
- `search`: インベントリ検索
- `history`: 装備変更履歴取得
- `memories`: アイテムを含むメモリ検索
- `stats`: アイテム使用統計

**例:**
```python
# 追加
item(operation="add", item_name="Health Potion", quantity=5)

# 装備
item(operation="equip", equipment={"weapon": "Sword", "armor": "Shield"})

# 装備解除（単一）
item(operation="unequip", slots="weapon")

# 装備解除（複数）
item(operation="unequip", slots=["weapon", "armor"])

# 検索
item(operation="search", category="weapon")

# 装備履歴（特定スロット）
item(operation="history", history_slot="weapon", days=30)
```

### 内部実装

個別のツール実装は `tools/` ディレクトリに保存されていますが、MCPインターフェースとしては上記3つの統合ツールのみが公開されています。

## GitHub Copilot Skills 🚀

MCPツールをGitHub Copilot Skillsとして利用可能です。**トークン消費を80〜90%削減**できます。

### セットアップ

1. VS Codeで `chat.useClaudeSkills: true` を設定
2. プロジェクトを開くだけ（`.github/skills/` が自動認識される）

### 利用可能なスキル

- **memory-operation**: 記憶の作成・検索・更新・削除
- **memory-context**: 約束・目標・感情・身体感覚の管理
- **item-management**: アイテムの追加・装備・検索
- **context-status**: 状態確認・ルーティンチェック

詳細: [.github/skills/README.md](.github/skills/README.md)

### トークン削減効果

| 方式 | トークン消費 | 削減率 |
|------|------------|--------|
| MCPツール（従来） | 5,000〜10,000トークン/リクエスト | - |
| Skills（新方式） | 500〜1,000トークン/リクエスト | **80〜90%削減** |

Skillsでは説明文のみがコンテキストに常駐し、フルコンテンツは呼び出し時のみロードされます。

## プロジェクト構成 (簡易)

主要なコード/ドキュメントの配置:

- `memory_mcp.py` — サーバーのエントリポイント (MCP起動/ワーカー起動/ツール登録)
- `src/` — アプリケーションのユーティリティ、リソース、ダッシュボード、設定ユーティリティ
- `core/` — メモリの永続化・更新・検索などのコアロジック
- `tools/` — MCPツール（CRUD、検索、分析ツールなど）
- `scripts/` — ローカルテストやスタートアップ用のスクリプト（`test_local_environment.sh` など）
- `data/` — 実行時データディレクトリ (persona 毎の SQLite、ログ、キャッシュ)
- `Dockerfile` / `docker-compose.yml` — コンテナ実行設定

これらの配置はプロジェクトの主要な作業フローを示し、`src/` と `tools/` がロジックの中心になっています。

## クイックスタート

### Docker (推奨)

```bash
docker run -d --name memory-mcp -p 26262:26262 \
  -v $(pwd)/data:/data \
  ghcr.io/solidlime/memory-mcp:latest
```

アクセス: `http://localhost:26262`

### MCP クライアント設定

**推奨 (Authorization Bearer)**:
```json
{
  "mcpServers": {
    "memory-mcp": {
      "url": "http://127.0.0.1:26262/mcp",
      "headers": {
        "Authorization": "Bearer default"
      }
    }
  }
}
```

---

### Git ヒストリーの完全抹消 (大容量ファイルが履歴に残っている場合)

誤ってキャッシュや出力ファイルをコミットしてしまった場合、履歴から完全に削除するには `git-filter-repo` または `BFG` を使ってリポジトリの履歴を書き換える必要があります。

このリポジトリでは過去に履歴削除用の補助スクリプトが追加されたことがありますが、現在は同等のスクリプトが存在しないか移動している可能性があります。
履歴置換を行う場合は公式ドキュメントやコミュニティガイドを参照し、必ずバックアップとチームへの告知を行ってください。

使うときの基本手順:

1. 作業コピーをバックアップ（`git clone` して別名のバックアップリポジトリを作る）
2. すべてのコラボレーターにブランチの強制書換えを行うことを事前に通知
3. スクリプトを実行し、出力メッセージの指示にしたがい `git push --force --all` / `git push --force --tags` を行う

注意: 履歴書き換えは破壊的なので、チームでの確認と同期が必要です。書き換え後、他の開発者はリポジトリを再クローンするか、`git fetch` の後に適切なリベース操作をしてください。

Persona切り替えは `Bearer <persona名>` で行います。

**レガシー (X-Persona)**:
```json
{
  "mcpServers": {
    "memory-mcp": {
      "url": "http://127.0.0.1:26262/mcp",
      "headers": {
        "X-Persona": "default"
      }
    }
  }
}
```

接続トラブルは `logs` のログや `scripts/test_local_environment.sh` を参照して問題切り分けしてください。

## 設定ファイル

### 設定ファイルの例

このディレクトリには設定ファイルの例が含まれています。

#### セットアップ

1. `data/config.json` を作成:
  - `data` ディレクトリに `config.json` を新規作成し、READMEの「設定例」セクションを参考に設定を追記してください。

2. `data/config.json` をあなたの設定で編集

3. 実際の `data/config.json` はgitignoredで、あなたの個人設定を含みます

#### デフォルトの場所

-- **例**: （このリポジトリでは `config/config.json.example` は提供していないため） `data/config.json` を作成してください
- **実際**: `data/config.json` (gitignored, 実行時に作成)

#### 環境変数

`MEMORY_MCP_` プレフィックスを使って任意の設定値を環境変数で上書きできます:

```bash
export MEMORY_MCP_EMBEDDINGS_MODEL=cl-nagoya/ruri-v3-30m
export MEMORY_MCP_QDRANT_URL=http://localhost:6333
export MEMORY_MCP_SERVER_PORT=26262
```

完全な設定ドキュメントは [README.md](../README.md) を参照してください。

## 設定

### 優先順位

1. デフォルト値 (コード内)
2. 環境変数 (`MEMORY_MCP_*`)
3. **config.json (最優先)**

**注**:
- 設定ファイルパスは `DATA_DIR/config.json` に固定
- ログファイルパスは `DATA_DIR/logs/memory_operations.log` に固定
- `server_host` / `server_port` は環境変数が最優先 (Docker互換性のため)

### 全設定項目

| 環境変数 | config.json | デフォルト | 説明 |
|---------|------------|----------|------|
| `MEMORY_MCP_DATA_DIR` | - | `./` (Docker: `/data`) | データディレクトリ |
| `MEMORY_MCP_CONFIG_PATH` | - | `data/config.json` | 設定ファイルパス |
| `MEMORY_MCP_LOG_FILE` | - | `data/logs/memory_operations.log` | ログファイルパス |
| `MEMORY_MCP_EMBEDDINGS_MODEL` | `embeddings_model` | `cl-nagoya/ruri-v3-30m` | 埋め込みモデル |
| `MEMORY_MCP_EMBEDDINGS_DEVICE` | `embeddings_device` | `cpu` | デバイス (cpu/cuda) |
| `MEMORY_MCP_RERANKER_MODEL` | `reranker_model` | `hotchpotch/japanese-reranker-xsmall-v2` | Rerankerモデル |
| `MEMORY_MCP_RERANKER_TOP_N` | `reranker_top_n` | `5` | Reranker候補数 |
| `MEMORY_MCP_SENTIMENT_MODEL` | `sentiment_model` | `cardiffnlp/twitter-xlm-roberta-base-sentiment` | 感情分析モデル |
| `MEMORY_MCP_SERVER_HOST` | `server_host` | `0.0.0.0` | サーバーホスト |
| `MEMORY_MCP_SERVER_PORT` | `server_port` | `26262` | サーバーポート |
| `MEMORY_MCP_TIMEZONE` | `timezone` | `Asia/Tokyo` | タイムゾーン |
| `MEMORY_MCP_RECENT_MEMORIES_COUNT` | `recent_memories_count` | `5` | get_context表示件数 |
| `MEMORY_MCP_QDRANT_URL` | `qdrant_url` | `http://localhost:6333` | Qdrant接続URL |
| `MEMORY_MCP_QDRANT_API_KEY` | `qdrant_api_key` | `None` | Qdrant APIキー |
| `MEMORY_MCP_QDRANT_COLLECTION_PREFIX` | `qdrant_collection_prefix` | `memory_` | Qdrantコレクションプレフィックス |
| `MEMORY_MCP_SUMMARIZATION_ENABLED` | `summarization.enabled` | `True` | 要約機能有効化 |
| `MEMORY_MCP_SUMMARIZATION_USE_LLM` | `summarization.use_llm` | `False` | LLM要約 (False=統計要約) |
| `MEMORY_MCP_SUMMARIZATION_FREQUENCY_DAYS` | `summarization.frequency_days` | `1` | 要約頻度（日数） |
| `MEMORY_MCP_SUMMARIZATION_MIN_IMPORTANCE` | `summarization.min_importance` | `0.3` | 要約対象最小重要度 |
| `MEMORY_MCP_SUMMARIZATION_IDLE_MINUTES` | `summarization.idle_minutes` | `30` | 自動要約トリガーのアイドル分数 |
| `MEMORY_MCP_SUMMARIZATION_CHECK_INTERVAL_SECONDS` | `summarization.check_interval_seconds` | `3600` | 自動要約チェック間隔（秒） |
| `MEMORY_MCP_SUMMARIZATION_LLM_API_URL` | `summarization.llm_api_url` | `None` | LLM API URL |
| `MEMORY_MCP_SUMMARIZATION_LLM_API_KEY` | `summarization.llm_api_key` | `None` | LLM APIキー |
| `MEMORY_MCP_SUMMARIZATION_LLM_MODEL` | `summarization.llm_model` | `anthropic/claude-3.5-sonnet` | LLMモデル名 |
| `MEMORY_MCP_SUMMARIZATION_LLM_MAX_TOKENS` | `summarization.llm_max_tokens` | `500` | 最大トークン数 |
| `MEMORY_MCP_SUMMARIZATION_LLM_PROMPT` | `summarization.llm_prompt` | `None` | カスタム要約プロンプト |
| `MEMORY_MCP_VECTOR_REBUILD_MODE` | `vector_rebuild.mode` | `idle` | リビルドモード (idle/manual) |
| `MEMORY_MCP_VECTOR_REBUILD_IDLE_SECONDS` | `vector_rebuild.idle_seconds` | `30` | アイドル秒数 |
| `MEMORY_MCP_VECTOR_REBUILD_MIN_INTERVAL` | `vector_rebuild.min_interval` | `120` | 最小実行間隔（秒） |
| `MEMORY_MCP_AUTO_CLEANUP_ENABLED` | `auto_cleanup.enabled` | `True` | 自動クリーンアップ |
| `MEMORY_MCP_AUTO_CLEANUP_IDLE_MINUTES` | `auto_cleanup.idle_minutes` | `30` | アイドル分数 |
| `MEMORY_MCP_AUTO_CLEANUP_CHECK_INTERVAL_SECONDS` | `auto_cleanup.check_interval_seconds` | `300` | チェック間隔（秒） |
| `MEMORY_MCP_AUTO_CLEANUP_DUPLICATE_THRESHOLD` | `auto_cleanup.duplicate_threshold` | `0.90` | 重複検知閾値 |
| `MEMORY_MCP_AUTO_CLEANUP_MIN_SIMILARITY_TO_REPORT` | `auto_cleanup.min_similarity_to_report` | `0.85` | レポート最小類似度 |
| `MEMORY_MCP_AUTO_CLEANUP_AUTO_MERGE_ENABLED` | `auto_cleanup.auto_merge_enabled` | `False` | 自動マージ有効化 |
| `MEMORY_MCP_AUTO_CLEANUP_AUTO_MERGE_THRESHOLD` | `auto_cleanup.auto_merge_threshold` | `0.95` | 自動マージ閾値 |
| `MEMORY_MCP_AUTO_SUMMARIZATION_ENABLED` | `auto_summarization.enabled` | `True` | 自動要約スケジューラー |
| `MEMORY_MCP_AUTO_SUMMARIZATION_SCHEDULE_DAILY` | `auto_summarization.schedule_daily` | `True` | 日次要約有効化 |
| `MEMORY_MCP_AUTO_SUMMARIZATION_SCHEDULE_WEEKLY` | `auto_summarization.schedule_weekly` | `True` | 週次要約有効化 |
| `MEMORY_MCP_AUTO_SUMMARIZATION_DAILY_HOUR` | `auto_summarization.daily_hour` | `3` | 日次要約実行時刻（時） |
| `MEMORY_MCP_AUTO_SUMMARIZATION_WEEKLY_DAY` | `auto_summarization.weekly_day` | `0` | 週次要約実行曜日（0=月曜） |
| `MEMORY_MCP_AUTO_SUMMARIZATION_CHECK_INTERVAL_SECONDS` | `auto_summarization.check_interval_seconds` | `3600` | チェック間隔（秒） |
| `MEMORY_MCP_AUTO_SUMMARIZATION_MIN_IMPORTANCE` | `auto_summarization.min_importance` | `0.3` | 要約対象最小重要度 |
| `MEMORY_MCP_AUTO_CLEANUP_CHECK_INTERVAL_SECONDS` | `auto_cleanup.check_interval_seconds` | `300` | チェック間隔（秒） |
| `MEMORY_MCP_AUTO_CLEANUP_DUPLICATE_THRESHOLD` | `auto_cleanup.duplicate_threshold` | `0.90` | 重複判定閾値 |
| `MEMORY_MCP_AUTO_CLEANUP_MIN_SIMILARITY_TO_REPORT` | `auto_cleanup.min_similarity_to_report` | `0.85` | 報告最小類似度 |
| `MEMORY_MCP_AUTO_CLEANUP_MAX_SUGGESTIONS_PER_RUN` | `auto_cleanup.max_suggestions_per_run` | `20` | 実行あたり最大提案数 |
| `MEMORY_MCP_AUTO_CLEANUP_AUTO_MERGE_ENABLED` | `auto_cleanup.auto_merge_enabled` | `False` | 自動マージ有効化 |
| `MEMORY_MCP_AUTO_CLEANUP_AUTO_MERGE_THRESHOLD` | `auto_cleanup.auto_merge_threshold` | `0.95` | 自動マージ閾値 |

### 設定例

**config.json**:
```json
{
  "embeddings_model": "cl-nagoya/ruri-v3-30m",
  "embeddings_device": "cpu",
  "server_port": 26262,
  "qdrant_url": "http://localhost:6333",
  "vector_rebuild": {
    "mode": "idle",
    "idle_seconds": 30
  },
  \"auto_cleanup\": {
    \"enabled\": true,
    \"idle_minutes\": 30,
    \"auto_merge_enabled\": false,
    \"auto_merge_threshold\": 0.95
  }
}
```

## データ構造

### ディレクトリ構成

```
/data
├── memory/              # Persona別データ
│   ├── default/
│   │   ├── memory.sqlite
│   │   ├── inventory.sqlite
│   │   └── persona_context.json
│   └── example/
│       ├── memory.sqlite
│       ├── inventory.sqlite
│       └── persona_context.json
├── logs/
│   └── memory_operations.log
└── cache/               # HuggingFaceモデルキャッシュ
```

### SQLiteスキーマ (14カラム)

| カラム | 型 | デフォルト | 説明 |
|-------|-----|----------|------|
| `key` | TEXT | (必須) | 一意ID (`memory_YYYYMMDDHHMMSS`) |
| `content` | TEXT | (必須) | 記憶本文 |
| `created_at` | TEXT | (必須) | 作成日時 (ISO 8601) |
| `updated_at` | TEXT | (必須) | 更新日時 (ISO 8601) |
| `tags` | TEXT | `[]` | タグ配列 (JSON) |
| `importance` | REAL | `0.5` | 重要度 (0.0-1.0) |
| `emotion` | TEXT | `"neutral"` | 感情タグ |
| `emotion_intensity` | REAL | `0.5` | 感情強度 (0.0-1.0, デフォルト中程度) |
| `physical_state` | TEXT | `"normal"` | 身体状態 |
| `mental_state` | TEXT | `"calm"` | 精神状態 |
| `environment` | TEXT | `"unknown"` | 環境 |
| `relationship_status` | TEXT | `"normal"` | 関係性 |
| `action_tag` | TEXT | `NULL` | 行動タグ |
| `related_keys` | TEXT | `NULL` | 関連記憶キー (JSON配列) |
| `summary_ref` | TEXT | `NULL` | 要約記憶への参照キー |
| `equipped_items` | TEXT | `NULL` | 記憶作成時の装備品 (JSON) |

**注**: `equipped_items`は`create_memory()`時に自動的にEquipmentDBから取得され、記録されます。

### persona_context.json 拡張フィールド

`create_memory()`/`update_memory()`の`persona_info`引数で以下のフィールドを更新可能：

| フィールド | 型 | 説明 | 例 |
|----------|-----|------|-----|
| `current_equipment` | dict | 現在の装備 | `{"clothing": "casual shirt", "accessory": "watch"}` |
| `favorite_items` | list | お気に入りアイテム | `["notebook", "pen"]` |
| `active_promises` | list | 進行中の約束 | `[{"content": "Meeting at 10am", "date": "2025-11-15"}]` |
| `current_goals` | list | 現在の目標 | `["Learn Python", "Build project"]` |
| `preferences` | dict | 好み | `{"loves": ["coding", "coffee"], "dislikes": ["bugs"]}` |

これらのフィールドは`get_context()`で自動的に表示されます。

### Qdrantベクトルストア

- **コレクション名**: `memory_<persona>` (例: `memory_default`, `memory_alice`)
- **ベクトル**: `embeddings_model` で生成 (デフォルト: cl-nagoya/ruri-v3-30m)
- **自動リビルド**: dimension不一致を検出時に自動修復

## MCPツール

### 推奨タグ (英語統一)

記憶作成時には以下のタグを使用することを推奨します：

- **Technical**: `technical_achievement`, `bug_fix`, `code_refactor`, `learning`
- **Emotional**: `emotional_moment`, `intimate_moment`, `happy_moment`, `sad_moment`
- **Events**: `important_event`, `promise`, `plan`, `milestone`, `anniversary`, `first_time`
- **Relationship**: `relationship_update`, `conversation`, `disagreement`
- **Daily**: `daily_activity`, `routine`, `meal`, `rest`

**記念日カレンダー用タグ**（Dashboard Anniversary機能）：
- `anniversary`: 記念すべき日（誕生日、記念日など）
- `milestone`: 達成・成果の記録（プロジェクト完成、目標達成など）
- `first_time`: 初めての体験（初デート、初成功など）

タグを統一することで、検索やダッシュボードでの可視化が効果的になります。

### LLM用ツール (12個)

**セッション管理**:
- `get_context` - 総合コンテキスト取得 (ペルソナ状態・経過時間・記憶統計・現在装備)
  - **推奨**: 毎応答時に呼ぶことで最新状態を同期

**CRUD操作**:
- `create_memory` - 新規作成 (高速・RAG検索なし)
  ```python
  create_memory("User likes [[Python]]", importance=0.7, emotion="joy")
  ```
  - 装備品は自動的にDBから取得して記憶に記録

- `update_memory` - 既存更新 (自然言語クエリで自動検出)
  ```python
  update_memory("promise", content="Tomorrow at 10am", importance=0.9)
  ```
  - 類似度 ≥ 0.80: 更新 / < 0.80: 新規作成

- `delete_memory` - 削除 (自然言語クエリ対応)
  ```python
  delete_memory("old project notes")
  ```
  - 類似度 ≥ 0.90: 自動削除 / < 0.90: 候補表示

**検索**:
- `search_memory` - 統合検索 (semantic/keyword/related の3モード対応)
  ```python
  # セマンティック検索（デフォルト）
  search_memory("ユーザーの好きな食べ物", mode="semantic")

  # キーワード検索（Fuzzy対応・タグ・日付範囲）
  search_memory("Python", mode="keyword", fuzzy_match=True)
  search_memory("", mode="keyword", tags=["technical_achievement"])

  # 関連記憶検索
  search_memory(mode="related", memory_key="memory_20251031123045")
  ```
  - メタデータフィルタ・カスタムスコアリング対応
  - 装備品フィルタ (`equipped_item`) 対応

**装備管理**:
- `add_to_inventory` - アイテムを所持品に追加
- `remove_from_inventory` - アイテムを所持品から削除
- `equip_item` - バッチ装備変更 (一括リセット→装備)
  ```python
  # 全装備を一度リセットしてから指定アイテムを装備
  equip_item({"top": "囁きのシフォンドレス", "foot": "蓮花サンダル"})

  # 全装備解除
  equip_item({})
  ```
- `update_item` - アイテム情報更新（説明・カテゴリ・タグ・装備スロット変更）
- `search_inventory` - 所持品検索 (カテゴリ・キーワードフィルタ)
- `get_equipment_history` - 装備変更履歴取得
- `analyze_item` - アイテム分析（記憶検索 + 使用統計）
  ```python
  # アイテムに関する記憶と使用統計を取得
  analyze_item("白いドレス", mode="both")
  ```

装備システムはSQLite (`data/memory/{persona}/equipment.db`) で管理され、`current_equipment`は`persona_context.json`と同期されます。
記憶作成時には装備品が自動的にDBから取得され、`equipped_items`として記録されます。

### 管理ツール (8個)

CLI / Webダッシュボード / API で実行可能。

**利用可能な管理ツール**:
- `clean` - 重複行削除
- `rebuild` - ベクトルストア再構築
- `detect-duplicates` - 類似記憶検出
- `merge` - 記憶統合
- `generate-graph` - 知識グラフ生成
- `migrate` - SQLite⇔Qdrant移行
- `summarize` - 記憶要約生成
- `migrate-schema` - スキーママイグレーション (不足カラム追加)

**CLI例**:
```bash
python3 admin_tools.py rebuild --persona default
python3 admin_tools.py detect-duplicates --persona default --threshold 0.85
python3 admin_tools.py migrate-schema --persona default
# または全Personaを一括マイグレーション
python3 scripts/migrate_schema.py
```

**Webダッシュボード**: `http://localhost:26262/` → 🛠️ Admin Tools

詳細は元のREADMEまたは `python3 admin_tools.py --help` を参照してください。

## スキーママイグレーション

古いバージョンからアップデートした場合、データベーススキーマの更新が必要な場合があります。

### いつマイグレーションが必要か

以下のような症状がある場合、スキーママイグレーションを実行してください：

- Rebuildで「no such column: importance」エラーが出る
- 装備品情報がQdrantに保存されない
- emotion_intensityが常に0.0になる

### マイグレーション方法

**方法1: Webダッシュボード** (推奨)
```
http://localhost:26262/ → 🛠️ Admin Tools → 🔧 Migrate Schema
```

**方法2: CLI**
```bash
# 全Personaを一括マイグレーション
python3 scripts/migrate_schema.py

# 特定のPersonaのみ
python3 scripts/migrate_schema.py --persona nilou
python3 admin_tools.py migrate-schema --persona nilou
```

### マイグレーション内容

- 不足カラムを自動追加（importance, emotion_intensity, equipped_items等）
- 既存の`emotion_intensity=0.0`を0.5（中程度）に更新
- 安全で冪等（何度実行してもOK）

### マイグレーション後の推奨手順

1. スキーママイグレーション実行
2. Rebuild実行（装備品情報をQdrantに反映）
   ```bash
   python3 admin_tools.py rebuild --persona nilou
   ```

## Testing

# Testing Guide - Memory MCP

This document describes how to test Memory MCP locally before deploying to production.

## ⚠️ Important: Local Testing Only

**All tests MUST be run locally, never in production (NAS) environment.**

## Prerequisites

- Docker & Docker Compose (for Qdrant)
- Python 3.12+ with venv
- `jq` command (for JSON parsing in bash scripts)

```bash
# Install jq if needed
sudo apt-get install jq
```

## Quick Start

### 1. Full Environment Test (Recommended)

This script will:
- Start Qdrant container
- Launch MCP server in background
- Verify health endpoint
- Test MCP initialize
- Keep server running until you press Ctrl+C

```bash
./test_local_environment.sh
```

**Output:**
```
🧪 Memory MCP Local Environment Test
========================================

📦 Step 1: Starting Qdrant...
✅ Qdrant started
✅ Qdrant is healthy

🚀 Step 2: Starting MCP Server...
MCP Server PID: 12345
⏳ Waiting for server initialization...
✅ MCP Server initialized

🏥 Step 3: Health Check...
✅ Health check passed

🔌 Step 4: MCP Initialize Request...
✅ MCP Initialize successful

🎉 All tests passed!
```

**Cleanup:**
- Press `Ctrl+C` to stop server and Qdrant
- Automatic cleanup on exit

### 2. HTTP MCP Endpoint Test

After starting the server with `test_local_environment.sh`, run this in another terminal:

```bash
# Activate venv
source venv-rag/bin/activate

# Run HTTP endpoint tests
python test_mcp_http.py
```

**Output:**
```
🧪 MCP HTTP Endpoint Test Suite
============================================================

🏥 Testing health endpoint...
  ✅ Health: ok, Persona: default

🔌 Testing MCP initialize...
  ✅ Initialize: Memory Service v1.19.0

🔧 Testing tools/list...
  ✅ Found 12 tools:
     - get_context
     - create_memory
     - update_memory
     - search_memory
     - delete_memory
     - add_to_inventory
     - remove_from_inventory
     - equip_item
     - update_item
     - search_inventory
     - get_equipment_history
     - analyze_item

📋 Testing get_context...
  ✅ Session context retrieved

💾 Testing create_memory...
  ✅ Memory created: memory_20251103123456

🔍 Testing read_memory...
  ✅ Found 3 memories

🔎 Testing search_memory...
  ✅ Found 2 memories

🗑️  Testing delete_memory...
  ✅ Memory deleted successfully

📊 Test Summary
============================================================
✅ PASS - Health Check
✅ PASS - MCP Initialize
✅ PASS - List Tools
✅ PASS - Get Context
✅ PASS - Create Memory
✅ PASS - Read Memory
✅ PASS - Search Memory
✅ PASS - Delete Memory
------------------------------------------------------------
Total: 8/8 passed (100.0%)
```

## Manual Testing

### Start Components Individually

#### 1. Start Qdrant

```bash
docker-compose up -d qdrant

# Verify
curl http://localhost:6333/health
```

#### 2. Start MCP Server

```bash
source venv-rag/bin/activate
python memory_mcp.py
```

Wait for:
```
✅ RAG system initialized successfully
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:26262
```

#### 3. Test Health Endpoint

```bash
curl http://localhost:26262/health | jq .
```

Expected:
```json
{
  "status": "ok",
  "persona": "default",
  "time": "2025-11-03T12:34:56.789012"
}
```

#### 4. Test MCP Initialize

```bash
curl -X POST http://localhost:26262/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-Persona: default" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "test-client",
        "version": "1.0.0"
      }
    }
  }'
```

Expected response:
```
event: message
data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05",...}}
```

#### 5. Test Tool Calls

##### List Available Tools

```bash
curl -X POST http://localhost:26262/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-Persona: default" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
  }'
```

##### Call create_memory

```bash
curl -X POST http://localhost:26262/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-Persona: default" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "create_memory",
      "arguments": {
        "content_or_query": "Test memory from curl",
        "importance": 0.7
      }
    }
  }'
```

## Debugging

### View Server Logs

If using `test_local_environment.sh`:
```bash
tail -f /tmp/mcp_server_test.log
```

If running manually:
```bash
# Server logs are in stdout
# Or check operation logs:
tail -f data/logs/memory_operations.log
```

### Check Qdrant Status

```bash
# List running containers
docker ps | grep qdrant

# Check Qdrant collections
curl http://localhost:6333/collections | jq .

# View specific collection
curl http://localhost:6333/collections/memory_default | jq .
```

### Check Database

```bash
# SQLite database location
ls -la memory/default/memories.db

# Query database
sqlite3 memory/default/memories.db "SELECT COUNT(*) FROM memories;"
```

## Troubleshooting

### Error: "Qdrant container not running"

```bash
# Check Docker
docker ps -a | grep qdrant

# Restart
docker-compose restart qdrant
```

### Error: "Failed to initialize RAG system"

Check logs for specific model loading errors:

```bash
grep -i "failed to initialize" /tmp/mcp_server_test.log
```

Common causes:
- Missing `sentencepiece` dependency → `pip install sentencepiece`
- CUDA issues → Verify `embeddings_device=cpu` in config
- Network issues → Check HuggingFace model download

### Error: "Port already in use"

```bash
# Find process using port 26262
lsof -i :26262

# Kill if needed
kill -9 <PID>
```

### Error: "MCP initialize timeout"

- Server may still be loading models
- Wait for "Application startup complete" in logs
- Check for errors in initialization phase

## Test Coverage

| Component | Test Script | Coverage |
|-----------|-------------|----------|
| Qdrant Startup | `test_local_environment.sh` | ✅ |
| MCP Server Startup | `test_local_environment.sh` | ✅ |
| Health Endpoint | Both scripts | ✅ |
| MCP Initialize | Both scripts | ✅ |
| Tools List | `test_mcp_http.py` | ✅ |
| create_memory | `test_mcp_http.py` | ✅ |
| read_memory | `test_mcp_http.py` | ✅ |
| search_memory | `test_mcp_http.py` | ✅ |
| delete_memory | `test_mcp_http.py` | ✅ |
| get_context | `test_mcp_http.py` | ✅ |
