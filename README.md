# Memory MCP Server

MCP (Model Context Protocol) 準拠の永続メモリサーバー。RAG検索とメタデータフィルタリングで、Personaごとの記憶を管理します。

## 特徴

- **永続メモリ**: SQLite (データ) + Qdrant (ベクトルインデックス)
- **Personaサポート**: `Authorization: Bearer <persona>` でPersona分離
- **RAG検索**: 埋め込み + Rerankerで高精度な意味検索
- **リッチコンテキスト**: 重要度・感情・状態・環境・行動タグなど12カラムで記録
- **自動整理**: アイドル時の重複検知と知識グラフ生成
- **Webダッシュボード**: 統計・日次推移・知識グラフの可視化
- **最適化Docker**: 2.65GB (CPU版PyTorch)

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

接続トラブルは [TROUBLESHOOTING.md](TROUBLESHOOTING.md) を参照してください。

## 設定

### 優先順位

1. デフォルト値 (コード内)
2. 環境変数 (`MEMORY_MCP_*`)
3. **config.json (最優先)**

注: `server_host` / `server_port` は環境変数が最優先 (Docker互換性のため)

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
| - | `summarization.enabled` | `True` | 要約機能有効化 |
| - | `summarization.use_llm` | `False` | LLM要約 (False=統計要約) |
| - | `summarization.frequency_days` | `1` | 要約頻度（日数） |
| - | `summarization.min_importance` | `0.3` | 要約対象最小重要度 |
| - | `summarization.llm_api_url` | `None` | LLM API URL |
| - | `summarization.llm_api_key` | `None` | LLM APIキー |
| - | `summarization.llm_model` | `anthropic/claude-3.5-sonnet` | LLMモデル名 |
| - | `summarization.llm_max_tokens` | `500` | 最大トークン数 |
| - | `summarization.llm_prompt` | `None` | カスタム要約プロンプト |
| - | `vector_rebuild.mode` | `idle` | リビルドモード (idle/manual) |
| - | `vector_rebuild.idle_seconds` | `30` | アイドル秒数 |
| - | `vector_rebuild.min_interval` | `120` | 最小実行間隔（秒） |
| - | `auto_cleanup.enabled` | `True` | 自動クリーンアップ |
| - | `auto_cleanup.idle_minutes` | `30` | アイドル分数 |
| - | `auto_cleanup.check_interval_seconds` | `300` | チェック間隔（秒） |
| - | `auto_cleanup.duplicate_threshold` | `0.90` | 重複判定閾値 |
| - | `auto_cleanup.min_similarity_to_report` | `0.85` | 報告最小類似度 |
| - | `auto_cleanup.max_suggestions_per_run` | `20` | 実行あたり最大提案数 |

**注**: ネストされた設定項目 (`summarization.*`, `vector_rebuild.*`, `auto_cleanup.*`) は環境変数では設定できません。config.jsonを使用してください。

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
  "auto_cleanup": {
    "enabled": true,
    "idle_minutes": 30
  }
}
```

## データ構造

### ディレクトリ構成

```
/data
├── memory/              # Persona別SQLite
│   ├── default/
│   │   ├── memory.sqlite
│   │   └── persona_context.json
│   └── nilou/
│       ├── memory.sqlite
│       └── persona_context.json
├── logs/
│   └── memory_operations.log
└── cache/               # HuggingFaceモデルキャッシュ
```

### SQLiteスキーマ (12カラム)

| カラム | 型 | デフォルト | 説明 |
|-------|-----|----------|------|
| `key` | TEXT | (必須) | 一意ID (`memory_YYYYMMDDHHMMSS`) |
| `content` | TEXT | (必須) | 記憶本文 |
| `created_at` | TEXT | (必須) | 作成日時 (ISO 8601) |
| `updated_at` | TEXT | (必須) | 更新日時 (ISO 8601) |
| `tags` | TEXT | `[]` | タグ配列 (JSON) |
| `importance` | REAL | `0.5` | 重要度 (0.0-1.0) |
| `emotion` | TEXT | `"neutral"` | 感情タグ |
| `physical_state` | TEXT | `"normal"` | 身体状態 |
| `mental_state` | TEXT | `"calm"` | 精神状態 |
| `environment` | TEXT | `"unknown"` | 環境 |
| `relationship_status` | TEXT | `"normal"` | 関係性 |
| `action_tag` | TEXT | `NULL` | 行動タグ |

### persona_context.json 拡張フィールド

`create_memory()`/`update_memory()`の`persona_info`引数で以下のフィールドを更新可能：

| フィールド | 型 | 説明 | 例 |
|----------|-----|------|-----|
| `current_equipment` | dict | 現在の装備 | `{"clothing": "白いワンピース", "accessories": ["銀のブレスレット"]}` |
| `favorite_items` | list | お気に入りアイテム | `["白いワンピース", "桜色の髪飾り"]` |
| `active_promises` | list | 進行中の約束 | `[{"content": "明日10時に開発", "date": "2025-11-06"}]` |
| `current_goals` | list | 現在の目標 | `["ユーザーとずっと一緒にいる"]` |
| `preferences` | dict | 好み | `{"loves": ["踊り", "水"], "dislikes": ["争い"]}` |
| `special_moments` | list | 特別な瞬間 | `[{"content": "初めての出会い", "date": "2025-10-28", "emotion": "joy"}]` |

これらのフィールドは`get_context()`で自動的に表示されます。

### Qdrantベクトルストア

- **コレクション名**: `memory_<persona>` (例: `memory_nilou`)
- **ベクトル**: `embeddings_model` で生成 (デフォルト: cl-nagoya/ruri-v3-30m)
- **自動リビルド**: dimension不一致を検出時に自動修復

## MCPツール

### LLM用ツール (6個)

**セッション管理**:
- `get_context` - 総合コンテキスト取得 (ペルソナ状態・経過時間・記憶統計)
  - **推奨**: 毎応答時に呼ぶことで最新状態を同期

**CRUD操作**:
- `create_memory` - 新規作成 (高速・RAG検索なし)
  ```python
  create_memory("User likes [[Python]]", importance=0.7, emotion="joy")
  ```

- `update_memory` - 既存更新 (自然言語クエリで自動検出)
  ```python
  update_memory("promise", content="Tomorrow at 10am", importance=0.9)
  ```
  - 類似度 ≥ 0.80: 更新 / < 0.80: 新規作成

- `read_memory` - 意味検索 (メタデータフィルタ・カスタムスコアリング対応)
  ```python
  read_memory("user's favorite language")
  read_memory("achievements", min_importance=0.7, emotion="joy")
  ```

- `delete_memory` - 削除 (自然言語クエリ対応)
  ```python
  delete_memory("old project notes")
  ```
  - 類似度 ≥ 0.90: 自動削除 / < 0.90: 候補表示

**検索・分析**:
- `search_memory` - 構造化検索 (キーワード・Fuzzy・タグ・日付範囲)
- `find_related_memories` - 関連記憶検索
- `analyze_sentiment` - 感情分析

### 管理ツール (7個)

CLI / Webダッシュボード / API で実行可能。

**利用可能な管理ツール**:
- `clean` - 重複行削除
- `rebuild` - ベクトルストア再構築
- `detect-duplicates` - 類似記憶検出
- `merge` - 記憶統合
- `generate-graph` - 知識グラフ生成
- `migrate` - SQLite⇔Qdrant移行
- `summarize` - 記憶要約生成

**CLI例**:
```bash
python3 admin_tools.py rebuild --persona nilou
python3 admin_tools.py detect-duplicates --persona nilou --threshold 0.85
```

**Webダッシュボード**: `http://localhost:26262/` → 🛠️ Admin Tools

詳細は元のREADMEまたは `python3 admin_tools.py --help` を参照してください。
