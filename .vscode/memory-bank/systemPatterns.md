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
│  - clean/time/context tools   │
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

---

## 主要コンポーネント

1. **MCP Server (FastMCP)**
   - MCPプロトコルの実装とクライアント通信
   - streamable-http（ポート8000）
   - ツール群 + リソース（memory://info, memory://metrics, ...）
2. **Persona Layer**
   - X-Personaヘッダーで分離、memory/{persona}/...
3. **RAG Layer**
   - Embeddings: cl-nagoya/ruri-v3-30m
   - Vector Store: FAISS
   - Reranker: hotchpotch/japanese-reranker-xsmall-v2
4. **Data Layer**
   - SQLite: memory/{persona}/memory.sqlite
   - Persona Context: memory/{persona}/persona_context.json
   - JSONL Logging: memory_operations.log

---

## 設計パターン
- Command Pattern: 各ツールを独立したコマンドとして実装（動的登録）
- Repository Pattern: DB/ベクトル操作をユーティリティに集約
- Observer Pattern: すべての操作をJSONLに記録
- Strategy Pattern: 構造化検索とRAG検索を使い分け
- Singleton-like: embeddings/vector_store/rerankerをプロセス内で共有

---

## データフロー
- **メモリ作成**: create_memory → SQLite保存 → Dirtyフラグ → JSONL記録
- **RAG検索**: FAISSで候補取得 → CrossEncoderで再ランク → 上位を返却
- **更新/削除**: SQLite保存/削除 → Dirtyフラグ → アイドル時にFAISS再構築

---

## 監視と可視化（Metrics）
- memory://info: エントリ数、総文字数、ベクトル数、DBパス、Persona、再構築設定
- memory://metrics: モデル名/ロード有無、ベクトル数、Dirty状態、最終書き込み/再構築時刻、再構築モード

---

## パフォーマンス最適化
- Embeddings/Rerankerを単一ロード
- ベクトルストアのアイドル時再構築（config.json.vector_rebuild）
- reranking対象をtop_k*3に制限

---

## セキュリティ/分離
- Persona単位で完全分離（DB/ベクトル/コンテキスト）
- 危険なpickleロードはローカル信頼環境でのみ