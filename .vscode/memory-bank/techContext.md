# Tech Context: Memory MCP

## 技術スタック

### 言語とフレームワーク

- **Python**: 3.12+ (venv-rag environment)
- **FastMCP**: MCPサーバー実装フレームワーク
  - `fastmcp.server.dependencies.get_http_request()`: HTTPリクエスト取得
  - Streamable HTTP transport
- **LangChain**: RAG（Retrieval-Augmented Generation）フレームワーク
  - langchain_core: コアドキュメント構造
  - langchain_community: Vector store & Embeddings

### 主要ライブラリ

**Core:**
- **fastmcp**: MCPサーバーのコア機能（0.9.0+）
- **sqlite3**: SQLiteデータベース操作
- **json**: データのシリアライズ/デシリアライズ
- **datetime**: タイムスタンプ管理
- **zoneinfo**: タイムゾーン管理（Asia/Tokyo）
- **uuid**: 一意の操作ID生成
- **contextvars**: スレッドセーフなPersonaコンテキスト管理（フォールバック用）

**RAG Stack:**
- **FAISS** (faiss-cpu): Facebook AI Similarity Search
- **HuggingFaceEmbeddings**: 埋め込みモデルインターフェース
  - Model: `cl-nagoya/ruri-v3-30m` (日本語最適化)
- **CrossEncoder** (sentence-transformers): Reranking
  - Model: `hotchpotch/japanese-reranker-xsmall-v2`
- **LangChain Document**: ドキュメント構造（page_content + metadata）

**Containerization:**
- **Docker**: コンテナ化
- **Docker Compose**: オーケストレーション

## 技術的制約

### Pythonバージョン

- 使用バージョン: 3.12+
- 最低バージョン: 3.10（型ヒント `str | None`）
- async/await: asyncio必須

### 依存関係

**必須:**
- FastMCP 0.9.0+
- LangChain 1.0+
- FAISS (CPU版)
- sentence-transformers 2.2.0+
- SQLite3（Python標準ライブラリ）

**オプション:**
- Obsidian: `[[]]` リンク記法の可視化

### プラットフォーム

- **OS**: Linux, macOS, Windows (WSL)
- **Docker**: 20.10+ (推奨)
- **ファイルシステム**: UTF-8エンコーディング対応
- **CPU**: FAISS はCPUモード
- **メモリ**: 2GB+推奨（モデルキャッシュ含む）

## データ形式

### SQLite Database

\`\`\`sql
-- memories table
CREATE TABLE memories (
    key TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    tags TEXT  -- JSON array
);

-- operations table
CREATE TABLE operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    key TEXT,
    before TEXT,
    after TEXT,
    success INTEGER NOT NULL,
    error TEXT,
    metadata TEXT
);
\`\`\`

### Persona Context (JSON)

\`\`\`json
{
  "user_info": {
    "name": "User",
    "nickname": "User",
    "preferred_address": "User"
  },
  "persona_info": {
    "name": "Assistant",
    "nickname": "AI",
    "preferred_address": "Assistant"
  },
  "current_emotion": "neutral",
  "physical_state": "normal",
  "mental_state": "calm",
  "environment": "unknown",
  "relationship_status": "normal",
  "last_conversation_time": "2025-10-30T12:00:00+09:00"
}
\`\`\`

### Operations Log (JSONL)

\`\`\`json
{"timestamp": "2025-10-30T12:00:00", "operation": "create", "key": "memory_20251030120000", "success": true}
\`\`\`

## 実装詳細

### Personaヘッダー取得（FastMCP依存関数）

\`\`\`python
from fastmcp.server.dependencies import get_http_request

def get_current_persona() -> str:
    """Get current persona from HTTP request header or context variable"""
    try:
        # FastMCP依存関数で現在のHTTPリクエストを取得
        request = get_http_request()
        if request:
            # X-Personaヘッダーを取得（ヘッダー名は小文字）
            persona = request.headers.get('x-persona', 'default')
            return persona
    except Exception:
        # フォールバック: リクエスト取得失敗時はcontextvarsを使用
        pass
    
    # ContextVarの値を返す
    return current_persona.get()
\`\`\`

### ツール内でのPersona使用

\`\`\`python
@mcp.tool()
async def create_memory(content: str) -> str:
    try:
        # ツール実行時にPersonaを取得
        persona = get_current_persona()
        
        # Persona別のパスを使用
        db_path = get_db_path(persona)
        vector_store_path = get_vector_store_path(persona)
        
        # メモリを保存...
\`\`\`

### パス解決関数

\`\`\`python
def get_persona_dir(persona: str = None) -> str:
    """Get persona-specific directory"""
    if persona is None:
        persona = get_current_persona()
    return os.path.join(SCRIPT_DIR, "memory", persona)

def get_db_path(persona: str = None) -> str:
    """Get persona-specific database path"""
    persona_dir = get_persona_dir(persona)
    os.makedirs(persona_dir, exist_ok=True)
    return os.path.join(persona_dir, "memory.sqlite")

def get_vector_store_path(persona: str = None) -> str:
    """Get persona-specific vector store path"""
    persona_dir = get_persona_dir(persona)
    return os.path.join(persona_dir, "vector_store")
\`\`\`

### RAG検索実装

\`\`\`python
def search_memory_rag(query: str, top_k: int = 5):
    persona = get_current_persona()
    
    # 1. 初期候補取得（多め）
    initial_k = top_k * 3 if reranker else top_k
    docs = vector_store.similarity_search(query, k=initial_k)
    
    # 2. Reranking
    if reranker and docs:
        pairs = [[query, doc.page_content] for doc in docs]
        scores = reranker.predict(pairs)
        ranked_docs = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        docs = [doc for doc, score in ranked_docs[:top_k]]
    
    return docs
\`\`\`

### データベースマイグレーション

\`\`\`python
def load_memory_from_db():
    """Load memory from SQLite with auto-migration"""
    db_path = get_db_path()
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # スキーママイグレーション
        cursor.execute("PRAGMA table_info(memories)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'tags' not in columns:
            cursor.execute('ALTER TABLE memories ADD COLUMN tags TEXT')
            conn.commit()
\`\`\`

## 設定管理

### config.json

\`\`\`json
{
  "embeddings_model": "cl-nagoya/ruri-v3-30m",
  "embeddings_device": "cpu",
  "reranker_model": "hotchpotch/japanese-reranker-xsmall-v2",
  "reranker_top_n": 5,
  "server_host": "127.0.0.1",
  "server_port": 8000,
  "vector_rebuild": {
    "mode": "idle",
    "idle_seconds": 30,
    "min_interval": 120
  }
}
\`\`\`

### ホットリロード

\`\`\`python
_config_mtime = 0

def load_config():
    global _config, _config_mtime
    current_mtime = os.path.getmtime(CONFIG_FILE)
    
    if current_mtime != _config_mtime:
        with open(CONFIG_FILE) as f:
            _config = json.load(f)
        _config_mtime = current_mtime
\`\`\`

## モデル情報

### Embeddings Model

- **名前**: cl-nagoya/ruri-v3-30m
- **パラメータ数**: 30M
- **サイズ**: ~120MB
- **言語**: 日本語最適化（多言語対応）
- **次元数**: 768

### Reranker Model

- **名前**: hotchpotch/japanese-reranker-xsmall-v2
- **タイプ**: CrossEncoder
- **サイズ**: ~50MB
- **言語**: 日本語専用

## ディレクトリ構造

\`\`\`
memory-mcp/
├── memory_mcp.py              # メインサーバー
├── db_utils.py                # DB操作ヘルパー
├── persona_utils.py           # Persona管理
├── vector_utils.py            # RAG/ベクトル管理
├── tools_memory.py            # MCP動的登録
├── config.json                # 設定ファイル
├── requirements.txt           # 依存関係
├── Dockerfile                 # Dockerイメージ定義
├── docker-compose.yml         # Docker Compose設定
├── test_tools.py              # テストスクリプト
├── memory/                    # Persona別データ
│   ├── default/
│   │   ├── memory.sqlite
│   │   ├── persona_context.json
│   │   └── vector_store/
│   └── {persona}/
│       ├── memory.sqlite
│       ├── persona_context.json
│       └── vector_store/
├── .cache/                    # モデルキャッシュ
│   ├── huggingface/
│   ├── transformers/
│   ├── sentence_transformers/
│   └── torch/
├── .vscode/                   # プロジェクトメモリバンク
│   └── memory-bank/
│       ├── projectbrief.md
│       ├── productContext.md
│       ├── activeContext.md
│       ├── systemPatterns.md
│       ├── techContext.md
│       └── progress.md
└── memory_operations.log      # 操作ログ（全Persona共通）
\`\`\`

## アーキテクチャパターン

### Personaスコープ管理（FastMCP依存関数ベース）

- **get_http_request()**: FastMCP標準の依存関数でHTTPリクエストを取得
- **ヘッダー取得**: request.headers.get('x-persona', 'default')
- **ツール内実行**: 各ツール関数内でget_current_persona()を呼び出し
- **フォールバック**: リクエスト取得失敗時はContextVarを使用
- **Path Resolution**: Personaに基づく動的ファイルパス解決

### RAGアーキテクチャ

- **初期化**: 起動時にモデルとベクトルストアを同期的にロード
- **更新**: CRUD操作時にベクトルストアを自動更新
- **検索**: 意味検索 + リランキングによる高精度検索
- **フォールバック**: RAG未準備時のキーワード検索自動切り替え
- **アイドル再構築**: Dirtyフラグ + バックグラウンドワーカーで非同期再構築

### データ永続化

- **SQLite**: 構造化データストレージ
- **JSONL**: 操作ログ（監査とデバッグ用）
- **FAISS**: ベクトルインデックス（検索性能用）

## RAG実装詳細

### Embeddings

- **Model**: \`cl-nagoya/ruri-v3-30m\`
- **Type**: Multilingual E5-based model (Japanese優先)
- **Dimension**: 768
- **Device**: CPU
- **Normalization**: True (cosine similarity最適化)

### Vector Store (FAISS)

- **Index Type**: Flat L2 (exact search, no quantization)
- **Similarity**: Cosine similarity (normalized embeddings)
- **Storage**: Disk persistence (\`vector_store/\`)
- **Operations**:
  - \`add_documents()\`: 新規ドキュメント追加
  - \`similarity_search(query, k)\`: Top-k類似検索
  - \`save_local()\`: Disk保存
  - \`load_local()\`: Disk読み込み
- **Rebuild Strategy**: Update/Delete時は全再構築（FAISS limitation）

### Reranker

- **Model**: \`hotchpotch/japanese-reranker-xsmall-v2\`
- **Type**: Cross-encoder (bi-encoder embeddingsより精度高い)
- **Input**: Query + Document pairs
- **Output**: Relevance scores (0-1)
- **Strategy**: 
  1. FAISS で top_k*3 候補取得（高速）
  2. Cross-encoder で再スコアリング（高精度）
  3. 上位 top_k を返す

### 検索フロー

\`\`\`
User Query
    ↓
[Embeddings] → Query Vector (768-dim)
    ↓
[FAISS Similarity Search] → Top 15 candidates (if top_k=5)
    ↓
[CrossEncoderReranker] → Rescoring with query-document pairs
    ↓
[Top-k Selection] → Top 5 most relevant memories
    ↓
[Format & Return] → Results with metadata
\`\`\`

## パフォーマンス特性

### メモリ使用量

- **FAISS Index**: ~10MB (40 vectors × 768 dim × 4 bytes)
- **Embeddings Model**: ~120MB (loaded once)
- **Reranker Model**: ~50MB (loaded once)
- **Total**: ~180MB (startup時)

### 検索速度

- **Keyword Search**: ~1ms (Python string search)
- **FAISS Search**: ~5-10ms (top_k=5, 40 docs)
- **Reranking**: ~50-100ms (top_k*3=15 pairs)
- **Total RAG Search**: ~60-110ms

### スケーラビリティ

- **Current**: 40+ memories
- **Target**: 1000+ memories (FAISS は100万+ docs対応可能)
- **Bottleneck**: Reranking (O(k) pairs) - top_k調整で制御

## 複数人格実装

### アーキテクチャ

- **Context Variables**: \`contextvars\` を使用したリクエストスコープのpersona管理
- **Persona Directory Structure**: 各personaごとに独立したディレクトリ (\`memory/{persona}/\`)
- **Database Isolation**: 各personaごとに独立したSQLite DB (\`memory/{persona}/memory.sqlite\`)
- **Vector Store Isolation**: 各personaごとに独立したベクトルストア (\`memory/{persona}/vector_store/\`)
- **Header-based Selection**: HTTPリクエストの \`X-Persona\` ヘッダーでpersona指定
- **Default Fallback**: ヘッダーなし時は \`default\` personaを使用

### ディレクトリ構造

\`\`\`
memory/
├── default/
│   ├── memory.sqlite
│   ├── persona_context.json
│   └── vector_store/
│       ├── index.faiss
│       └── index.pkl
├── nilou/
│   ├── memory.sqlite
│   ├── persona_context.json
│   └── vector_store/
│       ├── index.faiss
│       └── index.pkl
└── {persona_name}/
    ├── memory.sqlite
    ├── persona_context.json
    └── vector_store/
        ├── index.faiss
        └── index.pkl
\`\`\`

### レガシーデータ移行

- **自動移行**: 起動時に旧形式（\`memory/{persona}.sqlite\`, \`vector_store/\`）を検出して新形式に移行
- **移行ログ**: 移行実行時にコンソールに出力
- **移行方法**: \`os.replace()\` または \`shutil.copy2()\` でファイル/ディレクトリをコピー

### セキュリティ考慮

- **Isolation**: 各personaのデータ（DB + Vector Store）は完全に分離
- **Validation**: persona名はファイルシステムセーフな文字列のみ許可（パス区切り文字を \`_\` に置換）
- **Logging**: すべての操作にpersona情報を含む

## 開発環境

### IDE

- **VS Code** with extensions:
  - Pylance (型チェック)
  - Python (デバッグ)
  - GitHub Copilot (コーディング支援✨)

### Virtual Environment

\`\`\`bash
venv-rag/
├── bin/
│   ├── python (3.12+)
│   ├── activate
│   └── pip
└── lib/python3.12/site-packages/
    ├── langchain/
    ├── faiss/
    ├── fastmcp/
    └── ...
\`\`\`

### インストール

\`\`\`bash
# FastMCP
pip install mcp

# LangChain
pip install langchain langchain-community langchain-core

# FAISS
pip install faiss-cpu

# HuggingFace
pip install sentence-transformers
\`\`\`

## セキュリティ考慮事項

### データ保護

- **ローカルストレージ**: 全データは \`memory/\` ディレクトリに保存
- **アクセス制御**: ファイルシステムの権限に依存
- **暗号化**: なし（個人用途、ローカル環境）

### FAISS警告

- \`allow_dangerous_deserialization=True\`: pickle deserializationのリスク承知で使用
- **理由**: 信頼できる環境（ローカル開発）でのみ使用

## トラブルシューティング

### よくある問題

**Rerankerエラー**:

\`\`\`python
# 'NoneType' object is not callable
# → sentence-transformersのインストール確認
pip install --upgrade sentence-transformers
\`\`\`

**データベースマイグレーションエラー**:

\`\`\`bash
# table memories has no column named tags
# → サーバー再起動でマイグレーション実行
python memory_mcp.py
\`\`\`

**モデルダウンロードエラー**:

\`\`\`bash
# ネットワークエラー時
# → 手動ダウンロード
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('cl-nagoya/ruri-v3-30m')"
\`\`\`
