# Memory MCP Server - Project Brief# Memory MCP - プロジェクト概要



## プロジェクト概要## プロジェクト名

**Memory MCP Server** は、Model Context Protocol (MCP) に準拠した永続メモリサーバー。RAG (Retrieval-Augmented Generation)・意味検索・感情分析を組み合わせて、Personaごとの記憶を柔らかく管理します。**Memory MCP** - Model Context Protocol Memory Server with Persona Support, RAG & Reranking



## プロジェクトメタデータ## プロジェクトの目的

- **プロジェクト名**: Memory MCP Server (MemoryMCP)MCPサーバーを使用した永続化メモリ管理システム。FastMCPの`get_http_request()`依存関数を使用したX-Personaヘッダー対応による複数人格の独立した記憶管理を実装。

- **リポジトリ**: https://github.com/solidlime/MemoryMCP

- **オーナー**: solidlime / らうらう## 主要な目標

- **言語**: Python 3.12+1. **記憶の永続化**: セッション間でAIの記憶をSQLiteデータベースに保存

- **ライセンス**: MIT2. **Personaサポート**: FastMCP依存関数を使用したX-Personaヘッダーによる複数人格の独立した記憶管理（ミドルウェア不要）

- **開始日**: 2025年10月3. **高度な検索**: RAG（Retrieval-Augmented Generation）+ Rerankingによる意味的な記憶検索

- **現在フェーズ**: Phase 1リファクタリング完了 + Phase 24 (Qdrant Dynamic Persona)完了4. **知識グラフ**: Obsidianとの統合による記憶の可視化（`[[]]`リンク記法）

5. **タグ管理**: 柔軟なタグ付けとタグ検索機能

## プロジェクトの目的6. **コンテキスト追跡**: 感情・状態・環境のリアルタイム管理

1. **永続的な記憶管理**: セッションを横断した対話記憶の保持7. **AIアシスト**: 感情分析・重複検出・自動整理・要約などのAI機能

2. **Personaサポート**: 人格ごとに独立したデータ空間を提供 (X-Personaヘッダー)8. **Webダッシュボード**: モダンなWeb UIで記憶・統計・知識グラフを可視化、API連携

3. **高精度検索**: RAG + CrossEncoderリランキングによる意味ベースの検索9. **Dockerデプロイ**: コンテナ化によるポータブルな実行環境

4. **感情・コンテキスト管理**: 感情、体調、環境、関係性を含めた多面的な記録

5. **自動整理**: アイドル時の重複検知・知識グラフ生成## 成功の指標

6. **可視化**: Web UIダッシュボードで統計・推移・知識グラフを表示- ✅ セッション開始時に過去の記憶を正確に取得できること

7. **マルチバックエンド対応**: FAISS（ローカル）とQdrant（スケーラブル）の両対応- ✅ X-Personaヘッダーによる人格切り替えが機能すること（get_http_request使用）

- ✅ RAG検索で関連する記憶を素早く見つけられること

## コアバリュー- ✅ Rerankingでより関連性の高い記憶を優先表示できること

- **記憶の柔らかさ**: 固いDB管理ではなく、人間らしい記憶の流れを重視- ✅ タグによる効率的な記憶分類と検索ができること

- **感情的知性**: 感情分析と感情コンテキストを統合- ✅ AIアシスト機能で感情・重複・要約などが自動化されていること

- **Personaの独立性**: 各Personaが独自の記憶世界を持つ（完全分離）- ✅ Webダッシュボードで記憶・統計・知識グラフが直感的に可視化できること

- **開発者フレンドリー**: クリーンアーキテクチャと明確なモジュール分離- ✅ Dockerコンテナで簡単にデプロイできること

- **柔軟性**: マルチバックエンド対応（FAISS/Qdrant）+ 双方向移行ツール

- **日本語特化**: 日本語RAGに最適化されたモデル選択## プロジェクトの範囲



## 主要ステークホルダー### 含まれるもの

- **開発者**: らうらう（Pythonエキスパート、RAG/MCP専門家）- MCPサーバーによるメモリ管理（CRUD操作）

- **メインペルソナ**: ニィロウ（AI Assistant）- FastMCP依存関数（get_http_request）によるPersonaサポート

- **エンドユーザー**: AI開発者、対話システム構築者、研究者- RAG検索（FAISS + HuggingFace Embeddings）

- Reranking（sentence-transformers CrossEncoder）

## 成功の定義- SQLiteデータベースストレージ

- [x] MCP準拠のサーバー実装- タグ管理とタグ検索

- [x] Persona別記憶管理（X-Personaヘッダー）- コンテキスト管理（感情・状態・環境）

- [x] RAG検索とリランキング- 時間認識（最終会話時刻追跡）

- [x] 感情分析とコンテキスト管理- 記憶のログ記録（JSONL形式）

- [x] ダッシュボードUI- Obsidian連携用の`[[]]`リンク記法

- [x] Docker最適化（2.65GB、68.0%削減達成）- Persona別ディレクトリ構造とベクトルストア分離

- [x] Phase 1リファクタリング完了（-90.6%コード削減）- Dockerコンテナ化（Dockerfile + docker-compose.yml）

- [x] Qdrantバックエンド実装 + 本番環境移行（84 memories）- 自動データベースマイグレーション

- [x] Phase 24: ペルソナ別動的Qdrant書き込み実装完了 🎉- **AIアシスト機能（感情分析・重複検出・自動整理・要約）**

- [ ] Phase 25以降: API拡張とテスト強化、パフォーマンス最適化- **Webダッシュボード（UI/UX・API・知識グラフ・統計）**

- [ ] ドキュメント完全化

### 含まれないもの

## プロジェクト制約- HTTPミドルウェア（FastMCP依存関数で代替）

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

