# Memory MCP Server

Model Context Protocol (MCP) に準拠した永続メモリサーバー。RAG (Retrieval-Augmented Generation)・意味検索・感情分析を組み合わせて、Personaごとの記憶を管理します。

## 主な特徴

### コア機能
- **永続メモリ**: SQLite + Qdrantでセッションを横断した記憶を保持
- **Personaサポート**: `X-Persona` ヘッダーでPersonaごとに独立したデータ空間
- **RAG検索とリランキング**: HuggingFace埋め込み + CrossEncoderで高精度検索
- **完全コンテキスト保存**: 12カラムで記憶の完全な状況を記録
  - 重要度スコア (`importance`)、感情 (`emotion`)
  - 身体/精神状態 (`physical_state`, `mental_state`)
  - 環境 (`environment`)、関係性 (`relationship_status`)
  - 行動タグ (`action_tag`) - 料理中、コーディング中など

### 検索機能
- **意味検索 (`read_memory`)**: 自然言語クエリで記憶を検索
  - メタデータフィルタリング: 重要度・感情・行動タグ・環境・状態でフィルタ
  - カスタムスコアリング: 重要度・新しさの重みを調整
  - Fuzzy Matching: 曖昧検索対応
- **構造化検索 (`search_memory`)**: キーワード完全一致・Fuzzy・タグ・日付範囲検索

### 便利機能
- **簡単なAPI**: 
  - `create_memory`: 作成・更新を一本化（自然言語クエリで既存記憶を自動更新）
  - `read_memory`: 意味検索で記憶を読み取り
  - `delete_memory`: 自然言語クエリで削除（安全閾値付き）
- **自動整理**: アイドル時の重複検知・知識グラフ生成・感情推定
- **ダッシュボード**: Web UIで統計・日次推移・知識グラフを可視化

### 技術仕様
- **最適化済みDocker**: 2.65GB（CPU版PyTorch、Multi-stage build）
- **クリーンアーキテクチャ**: モジュール化され保守性が高い設計
- **Python 3.12** / FastAPI (FastMCP) / Uvicorn
- **LangChain + Qdrant** / sentence-transformers / HuggingFace Transformers

## クイックスタート

### Docker Compose
```bash
docker compose up -d
# ログ
docker compose logs -f memory-mcp
# 停止
docker compose down
```
推奨ホストマウント:
- `/data` (memory/, logs/, cache/ を含む全データ)

デフォルトポート: `26262`

アクセス: `http://localhost:26262`

### 公開イメージ
```bash
docker run -d --name memory-mcp -p 26262:26262 \
  -e MEMORY_MCP_SERVER_PORT=26262 \
  ghcr.io/solidlime/memory-mcp:latest
```

## MCPクライアント設定例
**VS Code**:
```json
{
  "mcp": {
    "servers": {
      "memory-mcp": {
        "type": "streamable-http",
        "url": "http://127.0.0.1:8000/mcp",
        "headers": {
          "X-Persona": "default"
        }
      }
    }
  }
}
```

Personaを切り替えたいときは `X-Persona` の値を変更します。

## 設定と環境変数

### 優先順位
設定は以下の順序で読み込まれ、**後から読み込まれたものが優先**されます：

1. デフォルト値（コード内に定義）
2. 環境変数（`MEMORY_MCP_*`）
3. **config.json（最優先）**

注: 運用利便性のため、`server_host` と `server_port` に限っては、環境変数（`MEMORY_MCP_SERVER_HOST` / `MEMORY_MCP_SERVER_PORT`）が最優先で上書きします（Dockerでのポート競合回避のため）。

### 環境変数 ↔ config.json マッピング

| 環境変数 | config.json パス | 型 | デフォルト値 | 説明 |
|---------|-----------------|-----|------------|------|
| `MEMORY_MCP_CONFIG_PATH` | *(特別)* | string | `./data/config.json` | config.jsonファイルのパス（デフォルトはdataディレクトリ内） |
| `MEMORY_MCP_DATA_DIR` | *(特別)* | string | `./` (Docker: `/data`) | データディレクトリ（memory/, logs/, cache/の親） |
| `MEMORY_MCP_LOG_FILE` | *(特別)* | string | `<data_dir>/logs/memory_operations.log` | ログファイルパス |
| `HF_HOME` | *(キャッシュ)* | string | `<data_dir>/cache/huggingface` | HuggingFaceキャッシュ |
| `TRANSFORMERS_CACHE` | *(キャッシュ)* | string | `<data_dir>/cache/transformers` | Transformersキャッシュ |
| `SENTENCE_TRANSFORMERS_HOME` | *(キャッシュ)* | string | `<data_dir>/cache/sentence_transformers` | SentenceTransformersキャッシュ |
| `TORCH_HOME` | *(キャッシュ)* | string | `<data_dir>/cache/torch` | PyTorchキャッシュ |
| `MEMORY_MCP_EMBEDDINGS_MODEL` | `embeddings_model` | string | `cl-nagoya/ruri-v3-30m` | 埋め込みモデル名 |
| `MEMORY_MCP_EMBEDDINGS_DEVICE` | `embeddings_device` | string | `cpu` | 計算デバイス（cpu/cuda） |
| `MEMORY_MCP_RERANKER_MODEL` | `reranker_model` | string | `hotchpotch/japanese-reranker-xsmall-v2` | リランカーモデル |
| `MEMORY_MCP_RERANKER_TOP_N` | `reranker_top_n` | int | `5` | リランク後の返却件数 |
| `MEMORY_MCP_SENTIMENT_MODEL` | `sentiment_model` | string | `cardiffnlp/twitter-xlm-roberta-base-sentiment` | 感情分析モデル |
| `MEMORY_MCP_SERVER_HOST` | `server_host` | string | `0.0.0.0` | サーバーホスト（Dockerは0.0.0.0、開発環境は127.0.0.1を推奨） |
| `MEMORY_MCP_SERVER_PORT` | `server_port` | int | `8000` (Docker: `26262`) | サーバーポート |
| `MEMORY_MCP_TIMEZONE` | `timezone` | string | `Asia/Tokyo` | タイムゾーン |
| `MEMORY_MCP_QDRANT_URL` | `qdrant_url` | string | `http://localhost:6333` | Qdrantサーバー接続URL（Phase 25: 必須） |
| `MEMORY_MCP_QDRANT_API_KEY` | `qdrant_api_key` | string | `null` | Qdrant API Key（未設定なら認証なし） |
| `MEMORY_MCP_QDRANT_COLLECTION_PREFIX` | `qdrant_collection_prefix` | string | `memory_` | Qdrantコレクション名Prefix |
| `MEMORY_MCP_VECTOR_REBUILD_MODE` | `vector_rebuild.mode` | string | `idle` | 再構築モード（idle/manual/auto） |
| `MEMORY_MCP_VECTOR_REBUILD_IDLE_SECONDS` | `vector_rebuild.idle_seconds` | int | `30` | アイドル判定秒数 |
| `MEMORY_MCP_VECTOR_REBUILD_MIN_INTERVAL` | `vector_rebuild.min_interval` | int | `120` | 最小再構築間隔（秒） |
| `MEMORY_MCP_AUTO_CLEANUP_ENABLED` | `auto_cleanup.enabled` | boolean | `true` | 自動整理有効化 |
| `MEMORY_MCP_AUTO_CLEANUP_IDLE_MINUTES` | `auto_cleanup.idle_minutes` | int | `30` | アイドル判定分数 |
| `MEMORY_MCP_AUTO_CLEANUP_CHECK_INTERVAL_SECONDS` | `auto_cleanup.check_interval_seconds` | int | `300` | チェック間隔（秒） |
| `MEMORY_MCP_AUTO_CLEANUP_DUPLICATE_THRESHOLD` | `auto_cleanup.duplicate_threshold` | float | `0.90` | 重複検出閾値 |
| `MEMORY_MCP_AUTO_CLEANUP_MIN_SIMILARITY_TO_REPORT` | `auto_cleanup.min_similarity_to_report` | float | `0.85` | レポート最小類似度 |
| `MEMORY_MCP_AUTO_CLEANUP_MAX_SUGGESTIONS_PER_RUN` | `auto_cleanup.max_suggestions_per_run` | int | `20` | 1回の最大提案数 |

### 設定例

#### パターン1: 環境変数のみ（config.jsonなし）
```bash
export MEMORY_MCP_DATA_DIR=/data
export MEMORY_MCP_EMBEDDINGS_MODEL=intfloat/multilingual-e5-base
export MEMORY_MCP_EMBEDDINGS_DEVICE=cuda
export MEMORY_MCP_VECTOR_REBUILD_MODE=auto
```

#### パターン2: config.jsonのみ
```json
{
  "embeddings_model": "cl-nagoya/ruri-v3-30m",
  "embeddings_device": "cpu",
  "reranker_model": "hotchpotch/japanese-reranker-xsmall-v2",
  "reranker_top_n": 10,
  "server_host": "0.0.0.0",
  "server_port": 8000,
  "timezone": "Asia/Tokyo",
  "vector_rebuild": {
    "mode": "idle",
    "idle_seconds": 30,
    "min_interval": 120
  },
  "auto_cleanup": {
    "enabled": true,
    "idle_minutes": 30,
    "check_interval_seconds": 300,
    "duplicate_threshold": 0.9,
    "min_similarity_to_report": 0.85,
    "max_suggestions_per_run": 20
  }
}
```

#### パターン3: 混在（config.jsonが優先される）
```bash
# 環境変数
export MEMORY_MCP_EMBEDDINGS_DEVICE=cpu

# config.json
{
  "embeddings_device": "cuda"  # ← こっちが優先される！
}

# 結果: embeddings_device="cuda"
```

## データ配置とディレクトリ
アプリコードは `/opt/memory-mcp`、データは `/data` 配下に分離しています。

**Phase 25: Qdrantベクトルストア専用**: SQLiteはPersonaごとに使用し、ベクトルインデックスはQdrantサーバー（別途起動）に保存されます。コレクション名は `<qdrant_collection_prefix><persona>` となります。

```
/opt/memory-mcp
├── memory_mcp.py        # サーバー本体
├── config_utils.py      # 設定ローダー
├── persona_utils.py     # Personaとパス管理
├── vector_utils.py      # Qdrantベクトルストア制御
└── templates/           # ダッシュボードUI

/data
├── memory/              # PersonaごとのSQLite
│   ├── default/
│   │   ├── memory.sqlite
│   │   └── persona_context.json
│   ├── nilou/
│   │   ├── memory.sqlite
│   │   └── persona_context.json
│   └── ...
├── logs/
│   └── memory_operations.log
└── cache/               # HuggingFaceモデルキャッシュ
    ├── huggingface/
    ├── transformers/
    ├── sentence_transformers/
    └── torch/
```

`MEMORY_MCP_DATA_DIR` は `/data` を指し、その中に `memory/`、`logs/`、`cache/` が作成されます。

**Qdrant設定**: `MEMORY_MCP_QDRANT_URL` でQdrantサーバーを指定。Dockerの場合は `docker-compose.yml` にQdrantコンテナを含めることを推奨。

## 記憶構造とその扱い

### SQLiteデータベーススキーマ

各Personaの記憶は **12カラム**の完全なコンテキストで保存されます：

| カラム名 | 型 | デフォルト | 説明 |
|---------|-----|-----------|------|
| `key` | TEXT | (必須) | 一意識別子（`memory_YYYYMMDDHHMMSS`形式） |
| `content` | TEXT | (必須) | 記憶本文（自然言語テキスト） |
| `created_at` | TEXT | (必須) | 作成日時（ISO 8601形式） |
| `updated_at` | TEXT | (必須) | 更新日時（ISO 8601形式） |
| `tags` | TEXT | `[]` | タグのJSON配列（例: `["technical_achievement", "important_event"]`） |
| `importance` | REAL | `0.5` | 重要度スコア（0.0〜1.0、0.7以上が高重要度） |
| `emotion` | TEXT | `"neutral"` | 感情タグ（joy, sadness, love, neutral など） |
| `physical_state` | TEXT | `"normal"` | 身体状態（energetic, tired, normal など） |
| `mental_state` | TEXT | `"calm"` | 精神状態（focused, anxious, calm など） |
| `environment` | TEXT | `"unknown"` | 環境（home, office, outdoors など） |
| `relationship_status` | TEXT | `"normal"` | 関係性（closer, intimate, distant など） |
| `action_tag` | TEXT | `NULL` | 行動タグ（coding, cooking, talking など） |

### Qdrantベクトルストア

**コレクション名**: `<qdrant_collection_prefix><persona>` (例: `memory_nilou`)

各記憶は以下の形式でQdrantに保存：
- **ベクトル**: `embeddings_model`（デフォルト: cl-nagoya/ruri-v3-30m）で生成された埋め込み
- **ペイロード**: SQLiteの全12カラム + メタデータ
- **ID**: SQLiteの `key` と同一

### 記憶の作成・更新・削除

#### 作成（create_memory）
```python
# 新規作成
create_memory("ユーザーは[[Python]]が好き", importance=0.7, emotion="joy")

# 自然言語クエリで自動更新（類似度≥0.80なら更新、<0.80なら新規作成）
create_memory("約束", content="明日10時に変更", importance=0.9)
```

**処理フロー**:
1. クエリで類似記憶を検索（RAG）
2. 類似度≥0.80: 既存記憶を更新（SQLite + Qdrant両方）
3. 類似度<0.80: 新規記憶を作成（SQLite + Qdrant両方）

#### 読み取り（read_memory）
```python
# 自然言語検索
read_memory("ユーザーの好きなプログラミング言語")

# メタデータフィルタ
read_memory("最近の成果", min_importance=0.7, emotion="joy", action_tag="coding")

# カスタムスコアリング
read_memory("重要なプロジェクト", importance_weight=0.3, recency_weight=0.2)
```

**検索プロセス**:
1. Qdrantで意味検索（embeddings類似度）
2. メタデータフィルタ適用（SQL後処理）
3. カスタムスコアリング計算
4. Rerankerで再ランク（hotchpotch/japanese-reranker-xsmall-v2）
5. Top-K結果を返却

#### 削除（delete_memory）
```python
# 自然言語クエリで削除
delete_memory("古いプロジェクトの記憶")
```

**安全機構**:
- 類似度≥0.90: 自動削除（高信頼度）
- 類似度<0.90: 候補リスト表示（ユーザー確認）

### 知識グラフ

記憶本文中の `[[リンク]]` 記法で知識グラフを構築：

```markdown
ユーザーは[[Python]]と[[機械学習]]に興味がある。[[TensorFlow]]と[[PyTorch]]を使っている。
```

→ ノード: Python, 機械学習, TensorFlow, PyTorch  
→ エッジ: 同一記憶内のリンク同士を接続

**可視化**: ダッシュボードまたは `generate-graph` 管理ツールでHTML生成（vis.js使用）

### Personaコンテキスト（persona_context.json）

各Personaの状態を保存：

```json
{
  "user_info": {"name": "らうらう", "nickname": "らうらう"},
  "persona_info": {"name": "ニィロウ", "nickname": "ニィロウ"},
  "current_emotion": "joy",
  "physical_state": "energetic",
  "mental_state": "focused",
  "environment": "home",
  "relationship_status": "closer",
  "last_conversation_time": "2025-11-03T10:28:06.123456+09:00"
}
```

**更新タイミング**: `create_memory`実行時に自動更新

## MCPリソースとツール

### LLM用ツール（5個）
会話型AIが直接使用するツールです。`/mcp`エンドポイント経由でアクセスできます。

**セッション管理**:
- `get_session_context` - **応答前の総合コンテキスト取得**
  - ペルソナ状態（ユーザー情報、感情、関係性、環境など）
  - 最終会話からの経過時間（自動更新）
  - 記憶統計（件数、最近の記憶、重要度/感情/タグ分布）
  - 💡 **推奨**: 毎応答時に呼ぶことでセッション間の記憶同期を行う

**CRUD操作**:
- `create_memory` - **🆕 記憶の作成・更新**
  - 新規作成: `create_memory("ユーザーは [[苺]] が好き")`
  - 更新: `create_memory("約束", content="明日10時に変更")`
  - 類似度 ≥ 0.80: 自動更新
  - 類似度 < 0.80: 新規作成（低信頼度の場合）
  - **見つからなければ自動的に新規作成** ✨
  - 12カラム完全対応: importance, emotion, physical_state, mental_state, environment, relationship_status, action_tag
- `read_memory` - **🆕 意味検索のメインツール**（旧search_memory_ragの機能）
  - 自然言語で検索: `read_memory("ユーザーの好きな食べ物")`
  - メタデータフィルタリング＆カスタムスコアリング対応
  - メタデータフィルタ（7パラメータ）: `min_importance`, `emotion`, `action_tag`, `environment`, `physical_state`, `mental_state`, `relationship_status`
  - カスタムスコアリング（2パラメータ）: `importance_weight`, `recency_weight`
  - Fuzzy Matching: テキストフィルタが部分一致（大文字小文字無視）
- `delete_memory` - **記憶を削除**（Phase 26.6の自然言語クエリ対応）
  - 自然言語で削除: `delete_memory("古いプロジェクトの記憶")`
  - 類似度 ≥ 0.90: 自動削除（安全性のため高閾値）
  - 類似度 < 0.90: 候補リスト表示

**検索・分析**:
- `search_memory` - **構造化検索**（完全一致・Fuzzy matching・タグフィルタ・日付範囲対応）
  - キーワード完全一致、Fuzzy matching対応
  - 使用例: `search_memory("Python", fuzzy_match=True, tags=["technical_achievement"])`
- `find_related_memories` - 関連記憶検索
- `analyze_sentiment` - 感情分析

### 管理者用ツール（7個）
管理者がメンテナンスに使用するツールです。以下3つの方法でアクセスできます：

#### 1. CLI（admin_tools.py）

```bash
# 仮想環境を有効化
source venv-rag/bin/activate

# ヘルプ表示
python3 admin_tools.py --help

# 使用例
python3 admin_tools.py clean --persona nilou --key memory_20251101183052
python3 admin_tools.py rebuild --persona nilou
python3 admin_tools.py migrate --source sqlite --target qdrant --persona nilou
python3 admin_tools.py detect-duplicates --persona nilou --threshold 0.85
python3 admin_tools.py merge --persona nilou --keys memory_001,memory_002
python3 admin_tools.py generate-graph --persona nilou --format html
```

#### 2. Webダッシュボード
`http://localhost:26262/`にアクセスし、🛠️ Admin Toolsカードから実行できます。

- 🧹 Clean Memory - 重複行削除
- 🔄 Rebuild Vector Store - ベクトルストア再構築
- 🔀 Migrate Backend - SQLite⇔Qdrant移行
- 🔍 Detect Duplicates - 類似記憶検出
- 🔗 Merge Memories - 複数記憶の統合
- 🕸️ Generate Graph - ナレッジグラフ生成

#### 3. API呼び出し

```bash
# 例: ナレッジグラフ生成
curl -X POST http://localhost:26262/api/admin/generate-graph \
  -H "Content-Type: application/json" \
  -H "X-Persona: nilou" \
  -d '{"persona":"nilou","format":"html","min_count":2}'

# 例: 重複検出
curl -X POST http://localhost:26262/api/admin/detect-duplicates \
  -H "Content-Type: application/json" \
  -H "X-Persona: nilou" \
  -d '{"persona":"nilou","threshold":0.85,"max_pairs":50}'
```

**管理ツール一覧**:
- `clean` - メモリ内の重複行を削除
- `rebuild` - Qdrantベクトルストアを再構築
- `detect-duplicates` - 類似した記憶を検出
- `merge` - 複数の記憶を1つに統合
- `generate-graph` - 知識グラフHTMLを生成

**LLMツールから除外された理由**:
- 管理ツールはメンテナンス作業用
- LLMの会話中に誤って実行されるリスクを回避
- 人間の判断が必要な操作（削除・統合など）

## 自動処理とバックグラウンド機能
- **感情分析**: テキストから joy/sadness/neutral を推定
- **知識グラフ生成**: `[[リンク]]` を可視化するHTMLを生成
- **アイドル時自動整理**: 重複検知レポートを `cleanup_suggestions.json` に保存

## 開発・運用
- **開発要件**: Python 3.12以上
- **Qdrant必須**: 開発環境でも `start_local_qdrant.sh` などでQdrantを起動してください
- **Docker運用**: 詳しくは [DOCKER.md](DOCKER.md) を参照
- **VS Code Tasks**: `.vscode/tasks.json` に起動スクリプト例あり

---

## アーキテクチャの変遷

### Phase 27: ツール統合・簡素化（2025-11-02 ~ 11-03）
- **7ツール → 5ツール**: create/update統合、search_rag→readリネーム
- **自然言語API**: create_memory/delete_memoryが自然言語クエリ対応
- **本番安定化**: sentencepiece依存問題解決、エラーログ強化

### Phase 25: Qdrant専用化（2025-11-01）
- **FAISS完全削除**: Qdrant専用実装に統一
- **list_memory廃止**: トークンオーバーフロー回避のため統計サマリーに変更

### Phase 24: ペルソナ別動的Qdrant（2025-11-01）
- **動的アダプター**: リクエストごとにペルソナ別Qdrantコレクション生成
- **X-Personaヘッダー対応**: ペルソナ切り替え実装

### Docker最適化（2025-10-30）
- **イメージサイズ削減**: 8.28GB → 2.65GB（68.0%削減）
- **CPU版PyTorch**: CUDA依存除外、Multi-stage build
