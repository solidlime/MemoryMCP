# Memory MCP Server

Model Context Protocol (MCP) に準拠した永続メモリサーバー。RAG (Retrieval-Augmented Generation)・意味検索・感情分析を組み合わせて、Personaごとの記憶を柔らかく管理します。

## 主な特徴
- 永続メモリ: SQLite + Qdrantでセッションを横断した記憶を保持
- Personaサポート: `X-Persona` ヘッダーで人格ごとに独立したデータ空間
- RAG検索とリランキング: HuggingFace埋め込み + CrossEncoderで高精度検索
- **完全コンテキスト保存** (Phase 25.5 Extended): 12カラムで記憶の完全な状況保存
  - 重要度スコア (`importance`)、感情 (`emotion`)
  - 身体/精神状態 (`physical_state`, `mental_state`)
  - 環境 (`environment`)、関係性 (`relationship_status`)
  - 行動タグ (`action_tag`) - 料理中、コーディング中、キス中など
- **高度な検索機能** (Phase 26/26.3):
  - メタデータフィルタリング: 重要度・感情・行動タグ・環境・状態でフィルタ
  - カスタムスコアリング: 重要度・新しさの重みを調整
  - Fuzzy Matching: 曖昧検索（"joy" → "joyful"もヒット）
- タグとコンテキスト: 感情・体調・環境・関係性を含めた多面的な記録
- 自動整理: アイドル時の重複検知・知識グラフ生成・感情推定
- ダッシュボード: Web UIで統計・日次推移・知識グラフを可視化
- **Phase 25: Qdrant専用化**: 高速ベクトル検索とスケーラビリティ（FAISS廃止）
- **最適化済みDocker**: 2.65GB（CPU版PyTorch、Multi-stage build）
- **クリーンアーキテクチャ**: Phase 1リファクタリング完了（2454行→231行、-90.6%）

## アーキテクチャ

### モジュール構成（Phase 1リファクタリング完了）

**memory_mcp.py** (231行) - メインエントリポイント
```
memory_mcp.py           # MCP サーバー初期化とオーケストレーション
├── core/               # コアロジック
│   ├── config.py      # 設定管理（環境変数 + config.json）
│   ├── database.py    # SQLite CRUD操作
│   ├── vector.py      # Qdrant ベクトルストア管理
│   ├── rag.py         # RAG検索とリランキング
│   ├── sentiment.py   # 感情分析
│   ├── persona.py     # Personaコンテキスト管理
│   └── analysis.py    # 重複検知・知識グラフ生成
├── tools/              # MCPツール定義
│   └── memory_tools.py # 全MCPツール（create/read/update/delete/search etc.）
├── resources.py        # MCPリソース登録（Persona情報提供）
└── dashboard.py        # Web UIダッシュボード
```

**設計原則**:
- 単一責任の原則: 各モジュールが1つの明確な責務を持つ
- 依存性の分離: コア機能はMCPから独立（再利用可能）
- テスタビリティ: モジュール単位でのテストが容易
- 保守性: 機能追加時の影響範囲を最小化

## 技術スタック
- Python 3.12 / FastAPI (FastMCP) / Uvicorn
- LangChain + Qdrant / sentence-transformers / HuggingFace Transformers
- SQLite (Personaごとに分離) / PyVis / NetworkX

## クイックスタート

### ローカル環境
```bash
git clone <repository-url>
cd memory-mcp
python -m venv venv-rag
source venv-rag/bin/activate  # Windowsは venv-rag\Scripts\activate
pip install -r requirements.txt
python memory_mcp.py
```
`http://127.0.0.1:8000` が開き、`/mcp` がMCPエンドポイントです。

### Docker Compose
```bash
docker compose up -d
# ログ
docker compose logs -f memory-mcp
# 停止
docker compose down
```
デフォルトマウント:
- `./data` → `/data` (memory/, logs/, cache/ を含む全データ)
- `./config.json` → `/config/config.json`

デフォルトポート: `26262` (開発環境と競合しないため)

アクセス: `http://localhost:26262`

### 公開イメージ (例)
```bash
docker run -d --name memory-mcp -p 26262:26262 \
  -v $(pwd)/data:/data \
  -v $(pwd)/config.json:/config/config.json:ro \
  -e MEMORY_MCP_SERVER_PORT=26262 \
  ghcr.io/solidlime/memory-mcp:latest
```

## MCPクライアント設定例 (VS Code)

**開発環境（ローカル起動）**:
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

**本番環境（Docker起動）**:
```json
{
  "mcp": {
    "servers": {
      "memory-mcp": {
        "type": "streamable-http",
        "url": "http://127.0.0.1:26262/mcp",
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
3. **config.json（最優先）** ← これが最終的な設定値になります

つまり、**config.jsonがあれば環境変数より優先**されます。

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

### ネスト記法

ネストされた設定（`vector_rebuild.*` や `auto_cleanup.*` など）は、環境変数でアンダースコアを使って表現します：

```bash
# vector_rebuild.mode を設定
export MEMORY_MCP_VECTOR_REBUILD_MODE=manual

# auto_cleanup.enabled を設定
export MEMORY_MCP_AUTO_CLEANUP_ENABLED=false
```

### 設定例

#### パターン1: 環境変数のみ（config.jsonなし）
```bash
export MEMORY_MCP_DATA_DIR=/data
export MEMORY_MCP_EMBEDDINGS_MODEL=intfloat/multilingual-e5-base
export MEMORY_MCP_EMBEDDINGS_DEVICE=cuda
export MEMORY_MCP_VECTOR_REBUILD_MODE=auto
```

#### パターン2: config.jsonのみ
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

## MCPリソースとツール

### LLM用ツール（9個）
会話型AIが直接使用するツールです。`/mcp`エンドポイント経由でアクセスできます。

**リソース**:
- `memory://info` - メモリ統計情報
- `memory://metrics` - 詳細メトリクス
- `memory://stats` - 統計データ
- `memory://cleanup` - 自動整理レポート

**セッション管理**:
- `get_session_context` - **応答前の総合コンテキスト取得**
  - ペルソナ状態（ユーザー情報、感情、関係性、環境など）
  - 最終会話からの経過時間（自動更新）
  - 記憶統計（件数、最近の記憶、重要度/感情/タグ分布）
  - 💡 **推奨**: 毎応答時に呼ぶことでセッション間の記憶同期を行う

**CRUD操作**:
- `create_memory` - 新しい記憶を作成
  - 12カラム完全対応: content, tags, importance, emotion, physical_state, mental_state, environment, relationship_status, action_tag
  - 例: `create_memory(content="...", importance=0.9, emotion="joy", action_tag="coding")`
- `read_memory` - 記憶を読み取り（全12フィールド表示）
- `update_memory` - 記憶を更新（既存フィールド保持）
- `delete_memory` - 記憶を削除

**検索・分析**:
- `search_memory` - キーワード検索（完全一致・Fuzzy matching・タグフィルタ・日付範囲対応）
- `search_memory_rag` - 意味検索（RAG）
  - メタデータフィルタリング（7パラメータ）
    - `min_importance`: 重要度フィルタ（0.0-1.0）
    - `emotion`, `action_tag`, `environment`: テキストフィルタ
    - `physical_state`, `mental_state`, `relationship_status`: 状態フィルタ
  - カスタムスコアリング（2パラメータ）
    - `importance_weight`: 重要度の重み（0.0-1.0）
    - `recency_weight`: 新しさの重み（0.0-1.0）
  - Fuzzy Matching
    - テキストフィルタが部分一致（大文字小文字無視）
    - 例: `emotion="joy"` → "joy", "joyful", "overjoyed" 全部ヒット
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

`http://localhost:8000/`（開発）または`http://localhost:26262/`（Docker）にアクセスし、🛠️ Admin Toolsカードから実行できます。

- 🧹 Clean Memory - 重複行削除
- 🔄 Rebuild Vector Store - ベクトルストア再構築
- 🔀 Migrate Backend - SQLite⇔Qdrant移行
- 🔍 Detect Duplicates - 類似記憶検出
- 🔗 Merge Memories - 複数記憶の統合
- 🕸️ Generate Graph - ナレッジグラフ生成

#### 3. API呼び出し

```bash
# 例: ナレッジグラフ生成
curl -X POST http://localhost:8000/api/admin/generate-graph \
  -H "Content-Type: application/json" \
  -H "X-Persona: nilou" \
  -d '{"persona":"nilou","format":"html","min_count":2}'

# 例: 重複検出
curl -X POST http://localhost:8000/api/admin/detect-duplicates \
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
- 感情分析 (Phase 19): テキストから joy/sadness/neutral を推定
- 知識グラフ生成 (Phase 20): `[[リンク]]` を可視化するHTMLを生成
- アイドル時自動整理 (Phase 21): 重複検知レポートを `cleanup_suggestions.json` に保存

## 開発メモ
- Python 3.12 以上で動作確認
- Dockerイメージは config.json を同梱しないため、必要に応じてバインドマウントまたは環境変数で上書き
- VS Code Tasks からの起動スクリプト例は `.vscode/tasks.json` を参照
- 詳しいDocker運用やTipsは [DOCKER.md](DOCKER.md) へ
- Qdrant必須化により、開発環境でも `start_local_qdrant.sh` などでQdrantを起動してください

**移行結果の例**:
```
✅ Migrated 84 memories from SQLite to Qdrant (persona: nilou)
Collection: memory_nilou
Qdrant URL: http://nas:6333
```

### ステップ4: 本番環境での動作確認
```bash
# Dockerで本番起動
docker run -d --name memory-mcp \
  -p 26262:26262 \
  -v $(pwd)/data:/data \
  -v $(pwd)/config.json:/config/config.json:ro \
  ghcr.io/solidlime/memory-mcp:latest

# ヘルスチェック
curl http://localhost:26262/health
```

### ステップ5: 開発環境ではconfig.dev.jsonを使用
```bash
# ローカル開発
python memory_mcp.py --config config.dev.json

# または環境変数で指定
MEMORY_MCP_CONFIG_PATH=config.dev.json python memory_mcp.py
```

### 注意事項
- ⚠️ `migrate_sqlite_to_qdrant_tool`は**上書き（upsert）**します
- ⚠️ 本番Qdrantへの移行後も、SQLiteファイルは削除されません（ロールバック可能）
- 💡 逆方向移行も可能: `migrate_qdrant_to_sqlite_tool()`

## Phase 24: ペルソナ別動的Qdrant書き込み実装（2025-11-01）

### 問題の発見
Qdrantバックエンド実装後、以下の問題が発覚：
- **症状**: X-Personaヘッダーで`nilou`を指定しても、全記憶が`memory_default`コレクションに書き込まれる
- **原因**: `add_memory_to_vector_store()`関数がサーバー起動時に初期化されたグローバル`vector_store`（defaultペルソナ固定）を使用していた
- **影響**: ペルソナ別の独立した記憶管理が機能しない重大なバグ

### アーキテクチャの誤解
当初、サーバー起動時にペルソナを指定して固定的に動作させる想定だったが、実際のアーキテクチャは：
- **サーバー起動**: defaultペルソナで最小限の初期化のみ
- **リクエスト時**: X-Personaヘッダーに基づいて動的にペルソナを切り替える
- **ベクトルストア**: リクエストごとにペルソナ別の接続を動的に生成する必要がある

### 実装した解決策
**vector_utils.py** の`add_memory_to_vector_store()`関数を修正（Lines 428-451）：

```python
# 修正前: グローバルvector_storeを固定使用
vector_store.add_documents([doc], ids=[key])
## Docker Image最適化の詳細

### 最適化結果
| 項目 | 最適化前 | 最適化後 | 削減率 |
|------|----------|----------|--------|
| イメージサイズ | 8.28GB | 2.65GB | **68.0%削減** |
| PyTorch | CUDA版 6.6GB | CPU版 184MB | 97.2%削減 |

### 実施した最適化
1. **PyTorchをCPU版に切り替え**
   - `--index-url https://download.pytorch.org/whl/cpu`を使用
   - CUDA依存パッケージ（nvidia/4.3GB、triton/593MB）を完全除外

2. **Multi-stage buildの導入**
   - Build stage: build-essentialを含む（依存パッケージのビルド用）
   - Runtime stage: curlのみ（ヘルスチェック用）
   - 最終イメージから336MBのbuild-essentialを除外

3. **.dockerignoreの最適化**
   - venv-rag/, data/, .git/, memory/, output/ などを除外
   - ビルドコンテキストの転送量削減

### ベンチマーク（参考）
- **ビルド時間**: 約5分（最適化前: 約15分）
- **デプロイ時間**: 約2分（最適化前: 約8分）
- **起動時間**: 約15秒（変化なし）

詳細は [DOCKER.md](DOCKER.md) を参照してください。

---

## Phase 25: Qdrant専用化とlist_memory廃止

### 変更内容
1. **list_memory廃止 → get_memory_stats新設**: トークンオーバーフロー回避のため、統計サマリーのみ返却
2. **FAISS完全削除**: Qdrant専用実装に統一、コード複雑度低減
3. **動的アダプターパターン**: リクエストごとにペルソナ別Qdrantアダプター生成（Phase 24実装継続）

### 影響
- ⚠️ **Breaking Change**: `list_memory`は使用不可（代わりに`get_memory_stats` + `search_memory_rag`を使用）
- ⚠️ **Breaking Change**: FAISS非対応（Qdrantが必須）
- ✅ **スケーラビリティ向上**: 大量記憶でも安定動作
- ✅ **コード削減**: 172行削除、保守性向上

詳細は [activeContext.md](.vscode/memory-bank/activeContext.md) と [progress.md](.vscode/memory-bank/progress.md) を参照してください。

---

心地よい記憶管理を楽しんでね。必要があればいつでも `memory://info` に声をかけて状態を確認してみて。
