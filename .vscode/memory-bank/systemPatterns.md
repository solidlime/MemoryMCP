# System Patterns - アーキテクチャと設計パターン

## アーキテクチャ概要

### モジュール構成

```
memory-mcp/
├── memory_mcp.py              # MCPサーバー初期化
├── tools_memory.py            # MCPツール/リソース登録
├── core/                       # コアロジック (MCP非依存)
│   ├── memory_db.py           # SQLite CRUD
│   ├── persona_context.py     # Personaコンテキスト管理
│   ├── time_utils.py          # タイムゾーン・時刻処理
│   └── forgetting.py          # 忘却曲線
├── src/                        # アプリケーションコード
│   ├── admin_tools.py         # 管理者CLI
│   ├── dashboard.py           # Webダッシュボード
│   └── utils/                 # ユーティリティ
│       ├── config_utils.py    # 設定管理
│       ├── db_utils.py        # DB操作ヘルパー
│       ├── persona_utils.py   # ペルソナ管理
│       ├── vector_utils.py    # ベクトル操作
│       └── analysis_utils.py  # 分析機能
├── scripts/                    # 開発/運用スクリプト
├── tools/                      # MCPツール定義
│   ├── crud_tools.py          # Create/Read/Update/Delete
│   ├── search_tools.py        # 検索 (RAG・タグ・日付)
│   ├── context_tools.py       # Personaコンテキスト
│   ├── analysis_tools.py      # 感情分析・関連記憶検索
│   └── knowledge_graph_tools.py # 知識グラフ生成
├── lib/backends/              # バックエンド実装
│   └── qdrant_backend.py      # Qdrantアダプター
├── templates/                  # ダッシュボードUI
├── data/                       # ランタイムデータ (gitignore)
│   ├── config.json            # 設定ファイル
│   ├── memory/{persona}/      # Persona別ストレージ
│   ├── logs/                  # ログ
│   └── cache/                 # モデルキャッシュ
└── requirements.txt           # Python依存関係
```

## 設計パターン

### 1. Clean Architecture
- `core/`: MCP非依存の純粋ビジネスロジック
- `tools/`: MCPツールとしてコアロジックをラップ
- `memory_mcp.py`: オーケストレーション層

**メリット**: テスト容易・他プロトコル移植可能・保守性向上

### 2. Strategy Pattern
**Qdrantバックエンド**:
```python
def get_vector_store(persona: str):
    backend = config["storage_backend"]
    if backend == "qdrant":
        return create_qdrant_adapter(persona)  # 動的生成
```

### 3. Context Pattern
**Personaコンテキスト管理**:
```python
current_persona: ContextVar[str] = ContextVar("current_persona", default="default")

def get_current_persona() -> str:
    return current_persona.get()

def set_current_persona(persona: str):
    current_persona.set(persona)
```

### 4. Repository Pattern
**データアクセス抽象化**:
```python
# core/memory_db.py
def load_memory_from_db() -> Dict[str, Any]
def save_memory_to_db(key, content, tags, timestamp)
def delete_memory_from_db(key: str) -> bool
```

### 5. Adapter Pattern
**QdrantVectorStoreAdapter**:
```python
class QdrantVectorStoreAdapter:
    def __init__(self, client, collection, embeddings, dim):
        self.client = client
        self.collection = collection  # memory_{persona}
        self.embeddings = embeddings
        self.dim = dim
    
    def add_documents(self, texts, metadatas): ...
    def similarity_search_with_score(self, query, k): ...
```

リクエスト時に動的生成、Persona別コレクションに書き込み。

## データフロー

### 記憶作成フロー
```
MCPクライアント (Authorization: Bearer nilou)
  ↓ create_memory
tools/crud_tools.py
  ↓ set_current_persona(nilou)
core/memory_db.py
  ↓ SQLite保存 (nilou/memory.sqlite)
vector_utils.py
  ↓ 動的QdrantAdapter生成 (persona=nilou)
  ↓ 埋め込み生成
Qdrant保存 (collection=memory_nilou)
```

### RAG検索フロー
```
MCPクライアント (Authorization: Bearer nilou)
  ↓ read_memory
tools/crud_tools.py
  ↓ set_current_persona(nilou)
vector_utils.py
  ↓ 動的QdrantAdapter取得 (memory_nilou)
  ↓ 埋め込み生成
  ↓ ベクトル検索 (top_k * 3)
  ↓ Reranker (CrossEncoder)
上位top_k返却
```

## コンフィグレーション

### 優先順位
1. デフォルト値 (コード内)
2. 環境変数 (`MEMORY_MCP_*`)
3. **config.json (最優先)**

例外: `server_host`, `server_port` は環境変数が最優先 (Docker対応)

### 設定ファイル構造
```json
{
  "embeddings_model": "cl-nagoya/ruri-v3-30m",
  "embeddings_device": "cpu",
  "reranker_model": "hotchpotch/japanese-reranker-xsmall-v2",
  "server_port": 26262,
  "storage_backend": "qdrant",
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

## パフォーマンス戦略

1. **埋め込みキャッシュ**: HuggingFaceモデル `data/cache/` にキャッシュ
2. **クエリキャッシュ**: `db_utils.py` のLRUキャッシュ
3. **非同期処理**: FastAPI/FastMCPの非同期機能活用
4. **リランキング**: 初期検索 `top_k * 3`、CrossEncoderで再スコア、上位 `top_k` 返却
5. **動的アダプター**: Qdrantアダプターはリクエスト時のみ生成

## セキュリティパターン

### Persona分離
- **データベース**: `memory/{persona}/memory.sqlite` (Persona別)
- **ベクトルストア**: `memory_{persona}` (Qdrantコレクション)
- **コンテキスト**: Persona間でデータ混在なし
- **動的切替**: `Authorization: Bearer <persona>` で完全分離

### ファイルパス検証
```python
def get_persona_dir(persona: str) -> Path:
    safe_persona = persona.replace("/", "_").replace("\\", "_")
    return MEMORY_ROOT / safe_persona
```

## エラーハンドリング

### 階層的エラー処理
1. **コア層**: 例外発生 (ValueError, FileNotFoundError等)
2. **ツール層**: 例外キャッチ、ユーザーフレンドリーメッセージ変換
3. **MCP層**: HTTPステータス・JSONエラーレスポンス

### ログ戦略
- `memory_operations.log`: 全操作記録 (JSONL)
- レベル: INFO (正常)、WARNING (注意)、ERROR (エラー)

## 拡張性

### バックエンド追加
新しいバックエンドは `lib/backends/` に追加、共通インターフェース実装:
```python
class VectorBackend(ABC):
    @abstractmethod
    def add_documents(self, texts: list, metadatas: list): pass
    
    @abstractmethod
    def similarity_search_with_score(self, query: str, k: int) -> list: pass
```

```python
# vector_utils.py
def get_vector_store(persona: str):
    backend = config["storage_backend"]
    if backend == "qdrant":
        return create_qdrant_adapter(persona)  # 動的生成
    else:
        return FAISSBackend(persona)
```

**サポートバックエンド**:
- **FAISS**: ローカル、高速、シンプル
- **Qdrant**: スケーラブル、クラウド対応、フィルタリング強力

**Phase 24での改善**:
- グローバルvector_storeの問題を解決
- リクエスト時にペルソナ別QdrantVectorStoreAdapter動的生成
- Personaごとのコレクション（memory_default, memory_nilou等）に正確に書き込み

### 3. Context Pattern
**Personaコンテキスト管理**
```python
# persona_utils.py
current_persona: ContextVar[str] = ContextVar("current_persona", default="default")

def get_current_persona() -> str:
    return current_persona.get()

def set_current_persona(persona: str):
    current_persona.set(persona)
```

**X-Personaヘッダー**でリクエストごとにPersona切り替え（完全動的）

### 4. Repository Pattern
**データアクセス抽象化**
```python
# core/memory_db.py
def load_memory_from_db() -> Dict[str, Any]
def save_memory_to_db(key: str, content: str, tags: list, timestamp: str)
def delete_memory_from_db(key: str) -> bool
```

SQLite操作を抽象化し、将来的な他のDB移行を容易にする。

### 5. Adapter Pattern (Phase 24)
**QdrantVectorStoreAdapter**
```python
# lib/backends/qdrant_backend.py
class QdrantVectorStoreAdapter:
    def __init__(self, client, collection, embeddings, dim):
        self.client = client
        self.collection = collection  # persona別（memory_nilou等）
        self.embeddings = embeddings
        self.dim = dim
    
    def add_documents(self, texts, metadatas):
        # Personaに対応したコレクションへ書き込み
        ...
    
    def similarity_search_with_score(self, query, k):
        # Personaに対応したコレクションから検索
        ...
```

**動的生成**:
- `storage_backend == "qdrant"` の場合、リクエスト時に動的生成
- `get_current_persona()` でペルソナ取得
- ペルソナ別コレクション名（`memory_{persona}`）に書き込み

### 6. Observer Pattern (実装済み)
**イベント駆動アーキテクチャ**
- 記憶作成イベント → 感情分析トリガー（optional）
- 記憶更新イベント → Dirtyフラグセット → ベクトル再構築
- アイドル検出 → 自動整理タスク（重複検出・提案）

## データフロー

### 記憶作成フロー（Phase 24対応）
```mermaid
graph TD
    A[MCPクライアント X-Persona: nilou] -->|create_memory| B[tools/crud_tools.py]
    B --> C[set_current_persona nilou]
    C --> D[core/memory_db.py]
    D --> E[SQLite保存 nilou/memory.sqlite]
    B --> F[vector_utils.py]
    F --> G{storage_backend?}
    G -->|qdrant| H[動的QdrantAdapter生成 persona=nilou]
    H --> I[埋め込み生成]
    I --> J[Qdrant保存 collection=memory_nilou]
    G -->|faiss| K[FAISSインデックス nilou/vector_store/]
    B --> L[persona_context.py]
    L --> M[コンテキスト更新 nilou/persona_context.json]
```

### RAG検索フロー
```mermaid
graph LR
    A[MCPクライアント X-Persona: nilou] -->|search_memory_rag| B[tools/search_tools.py]
    B --> C[set_current_persona nilou]
    C --> D[vector_utils.py]
    D --> E{storage_backend?}
    E -->|qdrant| F[動的QdrantAdapter取得 memory_nilou]
    E -->|faiss| G[FAISSインデックス取得 nilou/vector_store/]
    F --> H[埋め込み生成]
    G --> H
    H --> I[ベクトル検索 top_k*3]
    I --> J[Reranker CrossEncoder]
    J --> K[上位top_k返却]
```

## コンフィグレーション

### 優先順位
1. デフォルト値（コード内）
2. 環境変数（`MEMORY_MCP_*`）
3. **config.json（最優先）**

例外: `server_host`, `server_port` は環境変数が最優先（Docker対応）

### 設定ファイル構造
```json
{
  "embeddings_model": "cl-nagoya/ruri-v3-30m",
  "embeddings_device": "cpu",
  "reranker_model": "hotchpotch/japanese-reranker-xsmall-v2",
  "reranker_top_n": 10,
  "server_host": "0.0.0.0",
  "server_port": 26262,
  "timezone": "Asia/Tokyo",
  "storage_backend": "qdrant",
  "qdrant_url": "http://nas:6333",
  "qdrant_api_key": null,
  "qdrant_collection_prefix": "memory_",
  "vector_rebuild": {
    "mode": "idle",
    "idle_seconds": 30,
    "min_interval": 120
  },
  "auto_cleanup": {
    "enabled": true,
    "idle_minutes": 30,
    "duplicate_threshold": 0.9
  }
}
```

### 開発/本番環境分離
- `config.dev.json`: 開発環境（FAISS、localhost:6333）
- `config.json`: 本番環境（Qdrant、nas:6333）

## パフォーマンス戦略

### 1. 埋め込みキャッシュ
- HuggingFaceモデルキャッシュ: `data/cache/`
- 初回起動後はローカルから読み込み

### 2. クエリキャッシュ
- `db_utils.py`: LRUキャッシュで頻繁なクエリを高速化

### 3. 非同期処理
- FastAPI/FastMCPの非同期機能を活用
- ベクトル再構築はバックグラウンドスレッド

### 4. リランキング戦略
- 初期検索: `top_k * 3` 件取得
- CrossEncoderで再スコアリング
- 上位 `top_k` 件を返却

### 5. 動的アダプター生成（Phase 24）
- Qdrantアダプターはリクエスト時のみ生成
- メモリ効率とPersona分離を両立

## セキュリティパターン

### Persona分離（Phase 24強化）
- **データベース**: Personaごとに完全に独立したSQLiteファイル（`memory/{persona}/memory.sqlite`）
- **ベクトルストア**: 
  - FAISS: Personaごとに独立したディレクトリ（`memory/{persona}/vector_store/`）
  - Qdrant: Personaごとに独立したコレクション（`memory_{persona}`）
- **コンテキスト**: Persona間でデータ混在なし
- **動的切替**: リクエストごとにX-Personaヘッダーで完全分離

### ファイルパス検証
```python
# persona_utils.py
def get_persona_dir(persona: str) -> Path:
    # パストラバーサル対策
    safe_persona = persona.replace("/", "_").replace("\\", "_")
    return MEMORY_ROOT / safe_persona
```

## エラーハンドリング

### 階層的エラー処理
1. **コア層**: 例外を発生させる（ValueError, FileNotFoundError等）
2. **ツール層**: 例外をキャッチし、ユーザーフレンドリーなメッセージに変換
3. **MCP層**: HTTPステータスコードとJSONエラーレスポンス

### ログ戦略
- `memory_operations.log`: 全操作をタイムスタンプ付きで記録（JSONL形式）
- エラーレベル: INFO（正常）、WARNING（注意）、ERROR（エラー）

## 拡張性

### プラグインアーキテクチャ（Phase 3予定）
```python
# plugins/
# ├── emotion_plugin.py
# ├── translation_plugin.py
# └── custom_search_plugin.py
```

各プラグインは標準インターフェースを実装し、動的にロード。

### バックエンド追加
新しいバックエンドは `lib/backends/` に追加し、共通インターフェースを実装：
```python
class VectorBackend(ABC):
    @abstractmethod
    def add_documents(self, texts: list, metadatas: list):
        pass
    
    @abstractmethod
    def similarity_search_with_score(self, query: str, k: int) -> list:
        pass
```

## Phase 24の成果
- ✅ グローバルvector_store問題解決（defaultペルソナ固定 → 動的切替）
- ✅ リクエスト時動的QdrantVectorStoreAdapter生成
- ✅ Personaごとのコレクション（memory_default、memory_nilou等）に正確に書き込み
- ✅ 検証完了（memory_nilouコレクション 89→90ポイント）
