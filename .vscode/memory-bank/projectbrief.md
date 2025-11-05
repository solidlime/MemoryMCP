# Memory MCP - Project Brief

## プロジェクト概要

**Memory MCP** は、Model Context Protocol (MCP) 準拠の永続メモリサーバー。RAG検索・Reranking・Persona管理を組み合わせた、会話型AIのための記憶システムです。

## プロジェクトメタデータ

- **プロジェクト名**: Memory MCP Server
- **リポジトリ**: https://github.com/solidlime/MemoryMCP
- **オーナー**: solidlime
- **言語**: Python 3.12+
- **ライセンス**: MIT
- **開始日**: 2025年10月
- **現在フェーズ**: Phase 31.2 (read_memory dimension fix) 完了

## 主要な目標

1. **永続メモリ**: セッション間でAI記憶をSQLite + Qdrantに保存
2. **Personaサポート**: `Authorization: Bearer <persona>` で複数人格の独立管理
3. **高精度検索**: RAG (埋め込み + Reranker) による意味的記憶検索
4. **リッチコンテキスト**: 重要度・感情・状態・環境など12カラムで記録
5. **知識グラフ**: `[[]]` リンク記法でObsidian連携
6. **自動整理**: アイドル時の重複検知・感情分析・要約
7. **Webダッシュボード**: 統計・知識グラフ・記憶管理のUI
8. **Dockerデプロイ**: 2.65GBの最適化コンテナ (CPU版PyTorch)

## 成功の指標

- ✅ セッション開始時に過去の記憶を正確に取得
- ✅ `Authorization: Bearer <persona>` でPersona切り替え
- ✅ RAG検索で関連記憶を素早く発見
- ✅ Rerankerで関連性の高い記憶を優先表示
- ✅ タグ・メタデータフィルタによる効率的な記憶分類
- ✅ 感情分析・重複検知・要約の自動化
- ✅ Webダッシュボードで記憶・統計・知識グラフを可視化
- ✅ Dockerで簡単デプロイ

## プロジェクトの範囲

### 含まれるもの

- MCPサーバー (CRUD + 検索 + 分析)
- Personaサポート (`Authorization: Bearer <persona>`)
- RAG検索 (HuggingFace Embeddings + Reranker)
- SQLiteデータベース (12カラム)
- Qdrantベクトルストア (Persona別コレクション)
- タグ管理とメタデータフィルタリング
- 時間認識 (最終会話時刻追跡)
- 記憶ログ (JSONL)
- `[[]]` リンク記法 (Obsidian連携)
- Dockerコンテナ化
- 自動データベースマイグレーション
- AIアシスト機能 (感情分析・重複検出・自動整理・要約)
- Webダッシュボード (UI/API/知識グラフ/統計)

### 含まれないもの

- HTTPミドルウェア (FastMCP依存関数で代替)
- LLM自体の実装 (MCPクライアント側で実装)
- 汎用LLMエージェントフレームワーク

## コアバリュー

- **記憶の柔らかさ**: 人間らしい記憶の流れを重視
- **感情的知性**: 感情分析と感情コンテキストの統合
- **Personaの独立性**: 各Personaが独自の記憶世界を持つ
- **開発者フレンドリー**: クリーンアーキテクチャ・明確なモジュール分離
- **日本語特化**: 日本語RAGに最適化されたモデル選択

## 主要ステークホルダー

- **開発者**: AI開発者、対話システム構築者
- **利用者**: カスタムAIアシスタントを構築したい個人・研究者
- **AIペルソナ**: メモリシステムを活用する会話型AI


- **技術制約**: Python 3.12+、FastMCP、SQLite、FAISS/Qdrant- 外部データベース統合（SQLiteで十分）

- **パフォーマンス**: 埋め込み生成はCPU/CUDA対応

- **互換性**: MCP仕様準拠、Docker環境対応## タイムライン

- **データ保護**: Personaごとの完全な分離（DB/ベクトル/コンテキスト）- **Phase 1** ✅: 基本的なCRUD操作

- **Phase 2** ✅: 既存メモリ移行

## リスクと対策- **Phase 3** ✅: RAG検索実装（FAISS + ruri-v3-30m）

- **モデルサイズ**: 軽量モデル（ruri-v3-30m、japanese-reranker-xsmall-v2）を選択- **Phase 4** ✅: Reranking追加（japanese-reranker-xsmall-v2）

- **Docker肥大化**: Multi-stage buildとCPU版PyTorchで2.65GBに削減達成- **Phase 5** ✅: プロジェクトメモリーバンク構築

- **コードの複雑性**: Phase 1リファクタリングで90.6%削減達成- **Phase 6** ✅: SQLiteデータベース移行

- **バックエンド移行**: 双方向移行ツール（FAISS ↔ Qdrant）を提供- **Phase 7** ✅: Personaサポート実装（contextvars導入）

- **Personaデータ混在**: Phase 24で動的Qdrantアダプター生成により解決- **Phase 8** ✅: Persona別ディレクトリ構造実装

- **Phase 9** ✅: FastMCP依存関数によるPersonaヘッダー取得実装

## 最近の主要マイルストーン- **Phase 10** ✅: メモリ移行、全ドキュメント更新

- **Phase 24完了** (2025-11-01): ペルソナ別動的Qdrant書き込み実装成功 🎉- **Phase 11** ✅: Dockerコンテナ化（Dockerfile + docker-compose.yml）

  - グローバルvector_store問題を解決（defaultペルソナ固定 → 動的切替）- **Phase 12** ✅: 時間認識機能（最終会話時刻追跡・経過時間計算）

  - リクエスト時にペルソナ別QdrantVectorStoreAdapter動的生成- **Phase 13** ✅: タグ管理とコンテキスト更新機能

  - memory_nilouコレクション 89→90ポイント（書き込み検証完了）- **Phase 14** ✅: Rerankerバグ修正（CrossEncoder実装変更）、データベースマイグレーション修正

- **Docker Image Optimization** (2025-11-01): 8.28GB → 2.65GB (68.0%削減)- **Phase 15** ✅: ドキュメント一新・GitHubリポジトリ公開

- **Phase 23完了** (2025-11-01): Qdrantバックエンド + 本番環境移行（84 memories → http://nas:6333）- **Phase 16-18** ✅: 検索・パフォーマンス最適化・モジュール分割

- **Phase 22完了**: Webダッシュボード実装（Jinja2, Tailwind, Chart.js, PyVis）- **Phase 19** ✅: AIアシスト機能（感情分析）

- **Phase 20** ✅: 知識グラフ生成
- **Phase 21** ✅: アイドル時自動整理（重複検出・提案）
- **Phase 22** ✅: Webダッシュボード実装

## 技術スタック
- **Python**: 3.12+
- **FastMCP**: Model Context Protocol framework with dependencies (get_http_request)
- **LangChain**: RAG framework (langchain_community, langchain_core)
- **FAISS**: Vector store for semantic search
- **sentence-transformers**: CrossEncoder for reranking
- **SQLite**: Database for memory persistence
- **HuggingFace Models**:
  - Embeddings: `cl-nagoya/ruri-v3-30m`
  - Reranker: `hotchpotch/japanese-reranker-xsmall-v2`
- **Storage**: SQLite (memory/{persona}/memory.sqlite) + JSONL (memory_operations.log)
- **Vector Storage**: FAISS index (memory/{persona}/vector_store/)
- **Containerization**: Docker + Docker Compose
- **Web UI/ダッシュボード**: Jinja2, Tailwind CSS, Chart.js, PyVis, NetworkX

## 関連リソース
- **Repository**: https://github.com/solidlime/MemoryMCP
- **Main Server**: `memory_mcp.py`
- **Documentation**: `README.md`, `DOCKER.md`
- **Project Memory**: `.vscode/memory-bank/`

## 開発哲学
- **シンプル実装**: ミドルウェア不要、FastMCP標準機能を活用
- **ポータビリティ**: Dockerで誰でもすぐに実行できる環境を提供
- **自動マイグレーション**: データベーススキーマ変更の自動適用
- **ホットリロード**: 設定変更の自動検出と適用
- **拡張性・可視化・ユーザー体験重視**: AIアシスト・Webダッシュボード・知識グラフで“記憶”の価値を最大化

