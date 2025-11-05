# Tech Context - 技術要素と実装詳細

## 技術スタック

### コア技術
- **Python 3.12+**: 最新型ヒント、asyncio、contextvars
- **FastMCP 0.9.0+**: Model Context Protocol framework
- **FastAPI**: Web UI・MCPエンドポイント
- **Uvicorn**: ASGIサーバー

### RAG・検索エンジン
- **LangChain**: RAGフレームワーク
- **Qdrant**: スケーラブルベクトルDB
  - QdrantClient (REST API)
  - コレクション: `memory_{persona}`
- **sentence-transformers 2.2.0+**: CrossEncoderリランカー

### モデル
**Embeddings**:
- モデル: `cl-nagoya/ruri-v3-30m`
- 次元数: 256
- 言語: 日本語特化
- サイズ: ~30MB

**Reranker**:
- モデル: `hotchpotch/japanese-reranker-xsmall-v2`
- アーキテクチャ: CrossEncoder
- 言語: 日本語特化
- サイズ: ~120MB

### データストレージ
- **SQLite3**: メモリデータベース (12カラム)
  - テーブル: `memories`
  - Persona別: `memory/{persona}/memory.sqlite`
- **Qdrant**: ベクトルインデックス (`memory_{persona}` collection)
- **JSON**: Personaコンテキスト (`memory/{persona}/persona_context.json`)
- **JSONL**: 操作ログ (`logs/memory_operations.log`)

### Web UI・可視化
- **Jinja2**: テンプレートエンジン
- **Tailwind CSS**: CSSフレームワーク
- **Chart.js**: 統計グラフ
- **vis.js**: 知識グラフ可視化
- **NetworkX**: グラフ解析

### コンテナ化
- **Docker**: 2.65GB (CPU版PyTorch)
- **Docker Compose**: 開発環境オーケストレーション

## 依存関係

### requirements.txt (主要)
```
fastmcp>=0.9.0
langchain>=1.0
langchain-community>=1.0
sentence-transformers>=2.2.0
qdrant-client
transformers
torch  # CPU版
networkx
jinja2
```

## データ形式

### SQLite Schema (12カラム)
```sql
CREATE TABLE memories (
    key TEXT PRIMARY KEY,           -- memory_YYYYMMDDHHMMSS
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,       -- ISO 8601
    updated_at TEXT NOT NULL,
    tags TEXT,                      -- JSON配列
    importance REAL DEFAULT 0.5,    -- 0.0-1.0
    emotion TEXT DEFAULT 'neutral',
    physical_state TEXT DEFAULT 'normal',
    mental_state TEXT DEFAULT 'calm',
    environment TEXT DEFAULT 'unknown',
    relationship_status TEXT DEFAULT 'normal',
    action_tag TEXT
)
```

### Persona Context (persona_context.json)
```json
{
  "user_info": {"name": "User", "nickname": "User"},
  "persona_info": {"name": "Assistant", "nickname": "Assistant"},
  "current_emotion": "joy",
  "physical_state": "energetic",
  "mental_state": "focused",
  "environment": "home",
  "relationship_status": "closer",
  "last_conversation_time": "2025-11-04T10:00:00+09:00"
}
```

## API エンドポイント

### MCP エンドポイント
- `POST /mcp`: MCP protocol messages
- ヘッダー: `Authorization: Bearer <persona>` でPersona指定

### ダッシュボード
- `GET /`: Webダッシュボード
- `GET /api/stats`: 統計データ (JSON)
- `POST /api/admin/*`: 管理ツール

## パフォーマンス最適化

### 埋め込みキャッシュ
- HuggingFaceモデル: `data/cache/huggingface/`
- sentence-transformers: `data/cache/sentence_transformers/`
- transformers: `data/cache/transformers/`

### クエリキャッシュ
- `db_utils.py`: LRUキャッシュで頻繁なクエリを高速化
- `clear_query_cache()` で手動クリア可能

### 非同期処理
- FastAPI/Uvicornの非同期機能活用
- ベクトル再構築はバックグラウンドタスク

### リランキング戦略
1. 初期検索: `top_k * 3` 件取得
2. CrossEncoderで再スコアリング
3. 上位 `top_k` 件返却

## セキュリティ

### Persona分離
- SQLite: `memory/{persona}/memory.sqlite`
- Qdrant: `memory_{persona}` collection
- コンテキスト: `memory/{persona}/persona_context.json`

### ファイルパス検証
```python
safe_persona = persona.replace("/", "_").replace("\\", "_")
persona_dir = MEMORY_ROOT / safe_persona
```

## Docker最適化

### イメージサイズ削減
- **Before**: 8.28GB
- **After**: 2.65GB (68.0%削減)

### Multi-stage Build
```dockerfile
FROM python:3.12-slim as builder
# 依存関係インストール

FROM python:3.12-slim
# 最小限のランタイム環境
```

### CPU版PyTorch
- GPU不要な環境向けに最適化
- `torch` (CPU版) でサイズ削減

## 開発環境

### VS Code Tasks
- `.vscode/tasks.json`: ビルド・実行タスク定義
- `Cmd+Shift+B` でDocker起動

### テスト
- `scripts/test_mcp_http.py`: MCP HTTPエンドポイントテスト
- `scripts/test_search_accuracy.py`: 検索精度診断

### デバッグ
- FastAPI自動リロード (`--reload`)
- ログ: `data/logs/memory_operations.log`

  "user_info": {
    "name": "らうらう",
    "nickname": "らうらう",
    "preferred_address": "らうらう"
  },
  "persona_info": {
    "name": "ニィロウ",
    "nickname": "ニィロウ",
    "preferred_address": "ニィロウ"
  },
  "current_emotion": "joy",
  "physical_state": "energetic",
  "mental_state": "focused",
  "environment": "home",
  "relationship_status": "closer",
  "last_conversation_time": "2025-11-02T00:42:48+09:00"
}
```

### Operations Log（memory_operations.log）
JSONL形式:
```jsonl
{"timestamp": "2025-11-01T...", "operation": "create", "key": "memory_...", "success": true}
{"timestamp": "2025-11-01T...", "operation": "update", "key": "memory_...", "success": true}
```

## ディレクトリ構造

```
memory-mcp/
├── memory_mcp.py              # メインサーバー
├── config_utils.py            # 設定ローダー
├── persona_utils.py           # Personaとパス管理
├── vector_utils.py            # ベクトルストア制御（FAISS/Qdrant）
├── db_utils.py                # SQLiteユーティリティ
├── analysis_utils.py          # 分析ユーティリティ
├── admin_tools.py             # 管理ツール
├── dashboard.py               # Webダッシュボード
├── resources.py               # MCPリソース
├── tools_memory.py            # MCPツール（旧、Phase 1前）
├── core/                      # コアロジック
│   ├── memory_db.py           # SQLite CRUD
│   ├── persona_context.py     # Personaコンテキスト
│   └── time_utils.py          # 時刻処理
├── tools/                     # MCPツール（Phase 1後）
│   ├── crud_tools.py
│   ├── search_tools.py
│   ├── context_tools.py
│   ├── analysis_tools.py
│   ├── vector_tools.py
│   └── knowledge_graph_tools.py
├── lib/                       # ライブラリ
│   ├── backends/
│   │   └── qdrant_backend.py  # Qdrantアダプター
│   └── bindings/
│       └── utils.js
├── templates/
│   └── dashboard.html
├── data/                      # データディレクトリ
│   ├── memory/
│   │   ├── default/
│   │   │   ├── memory.sqlite
│   │   │   ├── persona_context.json
│   │   │   └── vector_store/  # FAISS mode
│   │   └── nilou/
│   ├── logs/
│   │   └── memory_operations.log
│   └── cache/
│       ├── huggingface/
│       ├── sentence_transformers/
│       └── transformers/
├── config.json                # 本番設定
├── config.dev.json            # 開発設定
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .vscode/
    └── memory-bank/           # プロジェクトメモリバンク
```

## 実装詳細

### Personaサポート（Phase 24対応）
**X-Personaヘッダー**でリクエストごとにPersona切り替え:
```python
# persona_utils.py
current_persona: ContextVar[str] = ContextVar("current_persona", default="default")

def get_current_persona() -> str:
    return current_persona.get()

def set_current_persona(persona: str):
    current_persona.set(persona)
```

**動的パス解決**:
```python
def get_db_path() -> Path:
    persona = get_current_persona()
    return MEMORY_ROOT / persona / "memory.sqlite"

def get_vector_store_path() -> Path:
    persona = get_current_persona()
    return MEMORY_ROOT / persona / "vector_store"
```

**Qdrant動的アダプター生成**（Phase 24）:
```python
# vector_utils.py (Lines 428-451)
def add_memory_to_vector_store(key: str, content: str):
    backend = config.get("storage_backend", "sqlite")
    
    if backend == "qdrant":
        # リクエスト時にペルソナ別Qdrantアダプター動的生成
        persona = get_current_persona()
        qdrant_client = get_qdrant_client()
        collection = f"{config['qdrant_collection_prefix']}{persona}"
        adapter = QdrantVectorStoreAdapter(
            client=qdrant_client,
            collection=collection,
            embeddings=embeddings,
            dim=384
        )
        adapter.add_documents([content], [{"key": key}])
    else:
        # FAISS: グローバルvector_store使用
        global vector_store
        vector_store.add_texts([content], metadatas=[{"key": key}])
```

### RAG検索フロー
1. クエリ埋め込み生成（cl-nagoya/ruri-v3-30m）
2. FAISS/Qdrantで類似検索（`top_k * 3` 件取得）
3. CrossEncoderで再ランキング（hotchpotch/japanese-reranker-xsmall-v2）
4. 上位 `top_k` 件を返却

### ベクトル再構築
- **モード**: `idle`（デフォルト）、`manual`、`auto`
- **アイドル判定**: 最終書き込みから30秒経過
- **最小間隔**: 120秒
- **Dirtyフラグ**: CRUD操作時にセット、再構築でクリア

### 自動整理（アイドル時）
- **アイドル判定**: 30分間操作なし
- **チェック間隔**: 5分ごと
- **重複検出閾値**: 0.90（コサイン類似度）
- **提案保存**: `memory/{persona}/cleanup_suggestions.json`

## パフォーマンス・スケーラビリティ

### メモリ使用量
- Embeddings モデル: ~50MB
- Reranker モデル: ~120MB
- FAISSインデックス: ~数MB（数千件）
- 合計: ~200MB（モデルロード後）

### 検索速度
- RAG検索: 60-110ms（40件時、リランキング含む）
- キーワード検索: <10ms
- タグ検索: <5ms

### スケーラビリティ
- **FAISS**: 数万件まで高速（ローカル）
- **Qdrant**: 数百万件対応（クラウド）
- **Reranking**: `top_k * 3` のみ処理（効率化）

## セキュリティ

### Persona分離
- SQLite: `memory/{persona}/memory.sqlite`
- FAISS: `memory/{persona}/vector_store/`
- Qdrant: `collection: memory_{persona}`
- Context: `memory/{persona}/persona_context.json`

### ファイルシステム保護
```python
def get_persona_dir(persona: str) -> Path:
    safe_persona = persona.replace("/", "_").replace("\\", "_")
    return MEMORY_ROOT / safe_persona
```

### データ暗号化
- 現状: なし（ローカル/個人用途）
- 将来: AES暗号化オプション（Phase 3）

## 開発環境

### ローカル開発
- VS Code（推奨拡張: Python、Pylance、Copilot）
- `venv-rag` 仮想環境
- `config.dev.json`（FAISS、localhost:6333）

### 本番環境
- Docker Compose
- `config.json`（Qdrant、nas:6333）
- ポート: 26262

### VS Code Tasks
```json
{
  "tasks": [
    {
      "label": "Start MCP Server (Dev)",
      "type": "shell",
      "command": "nohup ./start_server.sh > server.log 2>&1 & echo $! > server.pid"
    },
    {
      "label": "Stop MCP Server (Dev)",
      "type": "shell",
      "command": "kill $(cat server.pid) && rm server.pid"
    }
  ]
}
```

## トラブルシューティング

### よくある問題

**1. Rerankerエラー**
```
ModuleNotFoundError: No module named 'sentence_transformers'
```
→ `pip install sentence-transformers`

**2. DBマイグレーションエラー**
```
sqlite3.OperationalError: no such column: tags
```
→ サーバー再起動で自動マイグレーション実行

**3. モデルダウンロードエラー**
```
HTTPError: 403 Forbidden
```
→ 手動ダウンロード: `huggingface-cli download cl-nagoya/ruri-v3-30m`

**4. Qdrant接続エラー**
```
QdrantException: Connection refused
```
→ Qdrantサーバー起動確認: `docker compose up -d qdrant`

**5. Personaデータ混在（Phase 24で解決）**
```
全記憶がmemory_defaultコレクションに保存される
```
→ Phase 24で動的QdrantAdapter生成により解決済み

## 参考: 主要コード例

### Persona取得
```python
persona = get_current_persona()  # contextvars経由
```

### DB操作
```python
from core.memory_db import load_memory_from_db, save_memory_to_db

memory_store = load_memory_from_db()  # Persona-scoped
save_memory_to_db(key, content, tags, timestamp)
```

### RAG検索
```python
from tools.search_tools import search_memory_rag

results = search_memory_rag(query="Pythonに関する記憶", top_k=5)
```

### ベクトル追加（Phase 24対応）
```python
from vector_utils import add_memory_to_vector_store

add_memory_to_vector_store(key, content)  # 動的Persona切替対応
```

---

## 🛠️ Debug Commands Cheat Sheet

### Quick Testing

#### Full Environment Test
```bash
# Start Qdrant + MCP Server + Health check + MCP initialize
./test_local_environment.sh
```

#### HTTP Endpoint Test
```bash
# Test all MCP tools (server must be running)
source venv-rag/bin/activate
python test_mcp_http.py
```

### Environment Management

#### Start Qdrant (Docker)
```bash
docker-compose up -d qdrant

# Verify
curl http://localhost:6333/health
```

#### Start MCP Server

**Foreground** (see logs directly):
```bash
source venv-rag/bin/activate
python memory_mcp.py
```

**Background** (for testing):
```bash
source venv-rag/bin/activate
python memory_mcp.py > /tmp/mcp_server.log 2>&1 &
echo $! > /tmp/mcp_server.pid

# View logs
tail -f /tmp/mcp_server.log

# Stop
kill $(cat /tmp/mcp_server.pid)
```

### Health Checks

```bash
# MCP Server health
curl http://localhost:26262/health | jq .

# Qdrant health
curl http://localhost:6333/health

# List Qdrant collections
curl http://localhost:6333/collections | jq '.result.collections'

# Collection details
curl http://localhost:6333/collections/memory_default | jq .
```

### MCP Protocol Testing

#### Initialize
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
      "clientInfo": {"name": "test", "version": "1.0"}
    }
  }'
```

#### List Tools
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

#### Call Tool
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
        "content_or_query": "Debug test memory",
        "importance": 0.7
      }
    }
  }'
```

### Database Inspection

```bash
# SQLite
sqlite3 memory/default/memories.db

# Useful queries
SELECT COUNT(*) FROM memories;
SELECT key, content, created_at FROM memories ORDER BY created_at DESC LIMIT 10;
SELECT key, content, importance FROM memories WHERE importance >= 0.7;

# Persona context
cat memory/default/persona_context.json | jq .
```

### Log Analysis

```bash
# Operation logs (real-time)
tail -f data/logs/memory_operations.log

# Search errors
grep -i error data/logs/memory_operations.log

# Server logs (if background)
tail -f /tmp/mcp_server.log
```

### Process Management

```bash
# Find MCP process
ps aux | grep memory_mcp.py | grep -v grep

# Find process on port
lsof -i :26262

# Kill server
kill $(lsof -t -i:26262)
# or
kill -9 $(lsof -t -i:26262)
```

### Docker Management

```bash
# View containers
docker ps

# Qdrant logs
docker-compose logs -f qdrant

# Restart Qdrant
docker-compose restart qdrant

# Stop all
docker-compose down
```

### Troubleshooting

#### Reset Qdrant Collection
```bash
curl -X DELETE http://localhost:6333/collections/memory_default
```

#### Rebuild Vector Store
```bash
python -c "from vector_utils import rebuild_vector_store; rebuild_vector_store()"
```

#### Kill All Related Processes
```bash
# Stop MCP server
pkill -f memory_mcp.py

# Stop Qdrant
docker-compose down
```

### Configuration

```bash
# View current config
python -c "from config_utils import load_config; import json; print(json.dumps(load_config(), indent=2))"

# Set env vars (temporary)
export MEMORY_MCP_EMBEDDINGS_DEVICE=cpu
export MEMORY_MCP_SERVER_PORT=26262
```

---

## 📚 See Also

- [TESTING.md](../../TESTING.md) - Comprehensive testing guide with detailed examples
- [README.md](../../README.md) - Project overview and setup instructions
- [DOCKER.md](../../DOCKER.md) - Docker deployment and optimization guide
