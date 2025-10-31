# System Patterns: Memory MCP# System Patterns: Memory MCP



## アーキテクチャ概要## アーキテクチャ概要



### 全体構造### 全体構造

``````

┌─────────────────────────────────────┐┌─────────────────────────────┐

│    MCP Server (FastMCP)             ││      MCP Server (FastMCP)    │

│    Streamable HTTP (port 8000)      │├─────────────────────────────┤

├─────────────────────────────────────┤│   Memory Tools (8 tools)     │

│    Memory Tools (12 tools)          ││ - list_memory               │

│  - create_memory                    ││ - create_memory             │

│  - read_memory                      ││ - update_memory             │

│  - update_memory                    ││ - read_memory               │

│  - delete_memory                    ││ - delete_memory             │

│  - list_memory                      ││ - search_memory             │

│  - search_memory                    ││ - search_memory_rag         │

│  - search_memory_rag                ││ - clean_memory              │

│  - search_memory_by_date            │├─────────────────────────────┤

│  - search_memory_by_tags            ││   RAG Layer (LangChain)      │
```markdown
# System Patterns: Memory MCP

## アーキテクチャ概要

### 全体構造

```
┌───────────────────────────────┐
│        MCP Server (FastMCP)   │
│  - Streamable HTTP (port 8000)│
├───────────────────────────────┤
│         Memory Tools          │
│  - create/read/update/delete  │
│  - list/search/search_rag     │
│  - clean                      │
│  - time/context tools         │
├───────────────────────────────┤
│           Persona             │
│  - X-Persona header           │
│  - Persona-scoped paths       │
├───────────────────────────────┤
│             RAG               │
│  - Embeddings (ruri-v3-30m)   │
│  - Vector Store (FAISS)       │
│  - Reranker (CrossEncoder)    │
├───────────────────────────────┤
│             Data              │
│  - SQLite (per persona)       │
│  - Persona Context (JSON)     │
│  - JSONL Operations Log       │
└───────────────────────────────┘
```

## 主要コンポーネント

### 1. MCP Server (FastMCP)
- 役割: MCPプロトコルの実装とクライアントとの通信
- トランスポート: streamable-http（ポート8000）
- エンドポイント: ツール群 + リソース（`memory://info`, `memory://metrics`）

### 2. Persona Layer
- 依存関数: `fastmcp.server.dependencies.get_http_request()`
- ヘッダー: `X-Persona`（デフォルト: `default`）
- データ分離: `memory/{persona}/...`

### 3. RAG Layer
- Embeddings: HuggingFace (`cl-nagoya/ruri-v3-30m`)
- Vector Store: FAISS（保存: `vector_store/`）
- Reranker: sentence-transformers CrossEncoder（`hotchpotch/japanese-reranker-xsmall-v2`）

### 4. Data Layer
- SQLite: `memory/{persona}/memory.sqlite`（`memories`, `operations`）
- Persona Context: `memory/{persona}/persona_context.json`
- JSONL Logging: `memory_operations.log`

## 設計パターン

### Command Pattern
- 各ツールを独立したコマンドとして実装（動的登録）

### Repository Pattern
- DBアクセス/ベクトル操作をユーティリティに集約（`db_utils.py`, `vector_utils.py`）

### Observer Pattern（Logging）
- すべての操作をJSONLに記録（before/after, 成否, メタデータ）

### Strategy Pattern（Search）
- 構造化検索（キーワード/ファジー/タグ/日付）とRAG検索をユースケースで使い分け

### Singleton-like（RAG）
- `embeddings`/`vector_store`/`reranker` をプロセス内で共有
- 書き込み時はDirtyフラグ→アイドル時にバックグラウンド再構築

## データフロー

### メモリ作成
1. `create_memory(content, ...)`
2. SQLiteへ保存（tags/メタ含む）
3. Dirtyフラグをセット（ベクトル再構築はアイドル時）
4. JSONLに操作を記録

### RAG検索
1. 類似候補: FAISSで `top_k*3`
2. 再ランク: CrossEncoderでスコアリング
3. 上位 `top_k` を返却（DBから時刻メタ取得）

### 更新/削除
- SQLite保存（created_at保持）/削除 → Dirtyフラグ → アイドル時にFAISS再構築

## 監視と可視化（Metrics）
- `memory://info`: エントリ数、総文字数、ベクトル数、DBパス、Persona、再構築設定
- `memory://metrics`: モデル名/ロード有無、ベクトル数、Dirty状態、最終書き込み/再構築時刻、再構築モード

## パフォーマンス最適化
- Embeddings/Rerankerを単一ロード
- ベクトルストアのアイドル時再構築（設定: `config.json.vector_rebuild`）
- reranking対象を `top_k*3` に制限

## セキュリティ/分離
- Persona単位で完全分離（DB/ベクトル/コンテキスト）
- 危険なpickleロードはローカル信頼環境でのみ

``` 