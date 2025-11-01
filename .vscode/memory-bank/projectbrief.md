# Memory MCP - プロジェクト概要

## プロジェクト名
**Memory MCP** - Model Context Protocol Memory Server with Persona Support, RAG & Reranking

## プロジェクトの目的
MCPサーバーを使用した永続化メモリ管理システム。FastMCPの`get_http_request()`依存関数を使用したX-Personaヘッダー対応による複数人格の独立した記憶管理を実装。

## 主要な目標
1. **記憶の永続化**: セッション間でAIの記憶をSQLiteデータベースに保存
2. **Personaサポート**: FastMCP依存関数を使用したX-Personaヘッダーによる複数人格の独立した記憶管理（ミドルウェア不要）
3. **高度な検索**: RAG（Retrieval-Augmented Generation）+ Rerankingによる意味的な記憶検索
4. **知識グラフ**: Obsidianとの統合による記憶の可視化（`[[]]`リンク記法）
5. **タグ管理**: 柔軟なタグ付けとタグ検索機能
6. **コンテキスト追跡**: 感情・状態・環境のリアルタイム管理
7. **AIアシスト**: 感情分析・重複検出・自動整理・要約などのAI機能
8. **Webダッシュボード**: モダンなWeb UIで記憶・統計・知識グラフを可視化、API連携
9. **Dockerデプロイ**: コンテナ化によるポータブルな実行環境

## 成功の指標
- ✅ セッション開始時に過去の記憶を正確に取得できること
- ✅ X-Personaヘッダーによる人格切り替えが機能すること（get_http_request使用）
- ✅ RAG検索で関連する記憶を素早く見つけられること
- ✅ Rerankingでより関連性の高い記憶を優先表示できること
- ✅ タグによる効率的な記憶分類と検索ができること
- ✅ AIアシスト機能で感情・重複・要約などが自動化されていること
- ✅ Webダッシュボードで記憶・統計・知識グラフが直感的に可視化できること
- ✅ Dockerコンテナで簡単にデプロイできること

## プロジェクトの範囲

### 含まれるもの
- MCPサーバーによるメモリ管理（CRUD操作）
- FastMCP依存関数（get_http_request）によるPersonaサポート
- RAG検索（FAISS + HuggingFace Embeddings）
- Reranking（sentence-transformers CrossEncoder）
- SQLiteデータベースストレージ
- タグ管理とタグ検索
- コンテキスト管理（感情・状態・環境）
- 時間認識（最終会話時刻追跡）
- 記憶のログ記録（JSONL形式）
- Obsidian連携用の`[[]]`リンク記法
- Persona別ディレクトリ構造とベクトルストア分離
- Dockerコンテナ化（Dockerfile + docker-compose.yml）
- 自動データベースマイグレーション
- **AIアシスト機能（感情分析・重複検出・自動整理・要約）**
- **Webダッシュボード（UI/UX・API・知識グラフ・統計）**

### 含まれないもの
- HTTPミドルウェア（FastMCP依存関数で代替）
- 外部データベース統合（SQLiteで十分）

## タイムライン
- **Phase 1** ✅: 基本的なCRUD操作
- **Phase 2** ✅: 既存メモリ移行
- **Phase 3** ✅: RAG検索実装（FAISS + ruri-v3-30m）
- **Phase 4** ✅: Reranking追加（japanese-reranker-xsmall-v2）
- **Phase 5** ✅: プロジェクトメモリーバンク構築
- **Phase 6** ✅: SQLiteデータベース移行
- **Phase 7** ✅: Personaサポート実装（contextvars導入）
- **Phase 8** ✅: Persona別ディレクトリ構造実装
- **Phase 9** ✅: FastMCP依存関数によるPersonaヘッダー取得実装
- **Phase 10** ✅: メモリ移行、全ドキュメント更新
- **Phase 11** ✅: Dockerコンテナ化（Dockerfile + docker-compose.yml）
- **Phase 12** ✅: 時間認識機能（最終会話時刻追跡・経過時間計算）
- **Phase 13** ✅: タグ管理とコンテキスト更新機能
- **Phase 14** ✅: Rerankerバグ修正（CrossEncoder実装変更）、データベースマイグレーション修正
- **Phase 15** ✅: ドキュメント一新・GitHubリポジトリ公開
- **Phase 16-18** ✅: 検索・パフォーマンス最適化・モジュール分割
- **Phase 19** ✅: AIアシスト機能（感情分析）
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

