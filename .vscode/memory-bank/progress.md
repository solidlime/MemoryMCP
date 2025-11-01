# Progress: Memory MCP

## 最新更新: 2025-11-01

---

## 現在の状態（要約）
- **Phase 23完了**: Qdrantバックエンド実装、本番環境移行完了（84 memories → http://nas:6333）
- **Docker最適化完了**: イメージサイズ 8.28GB → 2.65GB (68.0%削減)
- **本番運用準備完了**: 開発/本番環境分離、VS Code Tasks、最適化済みDockerイメージ
- Phase 22: Webダッシュボード実装完了
- メモリバンク整備・ドキュメント更新完了

---

## 完了フェーズ（新しい順）
- ✅ **Docker Image Optimization** (2025-11-01)
  - PyTorchをCUDA版からCPU版へ切り替え（6.6GB → 184MB）
  - Multi-stage build導入（build-essential除外）
  - 最終イメージ: 8.28GB → 2.65GB (**68.0%削減**)
- ✅ **Phase 23: Qdrant Backend & Production Migration** (2025-10-31 - 2025-11-01)
  - デュアルバックエンド実装（SQLite/FAISS ⇔ Qdrant）
  - 本番Qdrant移行完了（84 memories → http://nas:6333）
  - 開発/本番環境分離（config.dev.json / config.json）
  - VS Code Tasks実装（nohup+pidfile方式）
- ✅ Phase 22.5: Docker環境最適化（config統一、env変数優先度設計、/data単一マウント、cache統一、ポート26262、0.0.0.0バインド、/healthエンドポイント）
- ✅ Phase 22: Webダッシュボード実装（Jinja2, Tailwind, Chart.js, API, Persona切り替え, セキュリティ, テスト, ドキュメント更新）
- ✅ Phase 21: アイドル時自動整理（重複検出・提案・バックグラウンドワーカー）
- ✅ Phase 20: 知識グラフ生成（NetworkX, PyVis, Obsidian連携、インタラクティブHTML）
- ✅ Phase 19: AIアシスト機能（感情分析自動化、transformers pipeline）
- ✅ Phase 18: パフォーマンス最適化（インクリメンタルインデックス、クエリキャッシュ）
- ✅ Phase 17: メモリ管理強化（統計ダッシュボード、関連検索、重複検出、統合）
- ✅ Phase 16: 検索機能強化（ハイブリッド検索、ファジー検索、タグAND/OR検索、ツール統合）
- ✅ Phase 15: ドキュメント一新、GitHubリポジトリ公開、GitHub Actions自動化
- ✅ Phase 14: Rerankerバグ修正（CrossEncoder実装変更）、データベースマイグレーション修正
- ✅ Phase 13: タグ管理とコンテキスト更新機能
- ✅ Phase 12: 時間認識機能（最終会話時刻追跡・経過時間計算）
- ✅ Phase 11: Dockerコンテナ化
- ✅ Phase 10: メモリ移行、全ドキュメント更新
- ✅ Phase 9: FastMCP依存関数によるPersona取得
- ✅ Phase 8: Persona別ディレクトリ構造
- ✅ Phase 7: Personaサポート実装（contextvars導入）
- ✅ Phase 6: SQLiteデータベース移行
- ✅ Phase 5: プロジェクトメモリーバンク構築
- ✅ Phase 4: Reranking追加（japanese-reranker-xsmall-v2）
- ✅ Phase 3: RAG検索実装（FAISS + ruri-v3-30m）
- ✅ Phase 2: 既存メモリ移行
- ✅ Phase 1: 基本的なCRUD操作

---

## 現在の主要機能
- RAG検索（FAISS or Qdrant + cl-nagoya/ruri-v3-30m）
- デュアルベクトルストアバックエンド（SQLite/FAISS or Qdrant、設定で切替可能）
- SQLite⇔Qdrant移行ツール（双方向データ移行サポート）
- Reranking（sentence-transformers CrossEncoder）
- Personaサポート（X-Personaヘッダー、完全分離）
- タグ管理・柔軟な検索
- コンテキスト追跡（感情・状態・環境）
- AIアシスト（感情分析・重複検出・自動整理・要約）
- 知識グラフ生成・可視化
- Webダッシュボード（UI/UX・API・グラフ・統計）
- Dockerサポート（本番運用最適化済み）
- GitHub Actions自動化

---

## 技術スタック
- Python 3.12+
- FastMCP, LangChain, FAISS or Qdrant, sentence-transformers
- SQLite, Docker, Jinja2, Tailwind, Chart.js, PyVis

---

## 最近の更新履歴
- **2025-11-01**: Docker Image Optimization完了（8.28GB → 2.65GB, 68.0%削減、PyTorch CPU版、Multi-stage build）
- **2025-11-01**: Phase 23完了・本番Qdrant移行（84 memories → http://nas:6333）
- **2025-11-01**: 開発環境/本番環境分離（config.dev.json/config.json）
- **2025-11-01**: VS Code Tasks実装（開発サーバー起動/停止/再起動）
- **2025-10-31**: Phase 23完了・Qdrantバックエンド実装（デュアルバックエンド、QdrantVectorStoreAdapter、移行ツール、Docker連携、ドキュメント更新）
- 2025-10-28: Phase 22.5完了・Docker環境最適化（config統一、env優先度設計、/data単一マウント、cache統一、ポート26262、0.0.0.0バインド、/healthエンドポイント）
- 2025-10-28: タグ管理強化・コンテキスト更新
- 2025-10-26: Docker環境構築・基本機能確認
- 2025-10-24: Phase 11 完了・Dockerコンテナ化

---

## Docker Image Optimization 詳細 (2025-11-01)

### 課題
- Dockerイメージサイズが **8.28GB** と巨大
- ビルド時間が長い（17GBのプロジェクトディレクトリをコピー）
- デプロイ効率が悪い

### 原因分析
- PyTorchのCUDA版が不要にインストールされていた（6.6GB）
  - `nvidia/`: 4.3GB
  - `torch/`: 1.7GB
  - `triton/`: 593MB
- プロジェクトディレクトリ内の不要ファイル（venv-rag: 7.4GB、.git: 689MB、data: 818MB）
- build-essential（336MB）が最終イメージに残っていた

### 実施した最適化

#### 1. PyTorchをCPU版に切り替え
```dockerfile
# Dockerfileで明示的にCPU版をインストール
RUN pip install --no-cache-dir \
    torch \
    torchvision \
    torchaudio \
    --index-url https://download.pytorch.org/whl/cpu
```
- **削減量**: 6.4GB（CUDA版 6.6GB → CPU版 184MB）

#### 2. Multi-stage build導入
```dockerfile
# Build stage: build-essentialを含む
FROM python:3.12-slim AS builder
RUN apt-get install build-essential ...

# Runtime stage: 必要なファイルのみコピー
FROM python:3.12-slim
COPY --from=builder /usr/local/lib/python3.12/site-packages ...
```
- **削減量**: 336MB（build-essential除外）

#### 3. .dockerignoreの検証
- 既に適切に設定されていることを確認
- venv-rag/, data/, .git/, memory/, output/ などを除外済み

### 最適化結果

| 項目 | Before | After | 削減量 | 削減率 |
|------|--------|-------|--------|--------|
| **Total Image Size** | 8.28GB | 2.65GB | -5.63GB | **-68.0%** |
| PyTorch | CUDA版 6.6GB | CPU版 184MB | -6.4GB | -97.2% |
| Build tools | 336MB | 0MB | -336MB | -100% |

### 検証結果
- ✅ PyTorch 2.9.0+cpu 正常動作
- ✅ CUDA無効化確認（`torch.cuda.is_available() == False`）
- ✅ 全パッケージ読み込み成功（sentence_transformers, faiss, qdrant_client）
- ✅ ビルド時間短縮
- ✅ デプロイ効率向上

### 変更ファイル
- `Dockerfile`: Multi-stage build、PyTorch CPU版インストール
- `requirements.txt`: PyTorchのコメント化（Dockerfileで管理）

---

## Phase 23 詳細: Qdrant Backend & Production Migration (2025-10-31 - 2025-11-01)
1. **デュアルバックエンドアーキテクチャ**
   - storage_backend設定で `sqlite`/`faiss` または `qdrant` を選択可能
   - config.jsonまたは環境変数（MEMORY_MCP_STORAGE_BACKEND）で切り替え
   - 既存のFAISSバックエンドは完全互換性維持

2. **QdrantVectorStoreAdapter実装**
   - lib/backends/qdrant_backend.py: FAISSインターフェース互換のアダプター
   - add_documents, delete, similarity_search_with_score, index.ntotalメソッド実装
   - Qdrantコレクション命名: `<qdrant_collection_prefix><persona>` (例: memory_default)
   - Payload: key, content, metadata（全検索・フィルタリングに対応）

3. **vector_utilsのバックエンドスイッチ**
   - initialize_rag_sync()でstorage_backendに応じてQdrantまたはFAISSを初期化
   - Qdrant起動時、SQLiteからのブートストラップ機能（コレクション空なら自動インポート）
   - save_vector_store(), rebuild_vector_store()はバックエンド抽象化済み

4. **双方向移行ツール**
   - migrate_sqlite_to_qdrant(): SQLite→Qdrant全件アップサート
   - migrate_qdrant_to_sqlite(): Qdrant→SQLite全件インポート（upsertモード）
   - MCPツールとして公開（migrate_sqlite_to_qdrant_tool, migrate_qdrant_to_sqlite_tool）

5. **Qdrant設定**
   - qdrant_url: Qdrantサーバー接続URL（デフォルト: http://localhost:6333）
   - qdrant_api_key: 認証キー（未設定なら認証なし）
   - qdrant_collection_prefix: コレクション名プレフィックス（デフォルト: memory_）
   - 環境変数: MEMORY_MCP_QDRANT_URL, MEMORY_MCP_QDRANT_API_KEY, MEMORY_MCP_QDRANT_COLLECTION_PREFIX

6. **Docker連携設定**
   - docker-compose.ymlにQdrantサービス追加例をDOCKER.mdに記載
   - Qdrantコンテナ: ポート6333/6334公開、ボリュームマウント
   - memory-mcpコンテナ: depends_on設定でQdrant起動待機

7. **ドキュメント更新**
   - README.md: Qdrant設定の環境変数マッピング、移行ツール説明追加
   - DOCKER.md: Qdrant連携のdocker-compose例、移行手順追加
   - activeContext.md, progress.md: Phase 23完了状況反映

### 修正ファイル
- requirements.txt: qdrant-client追加
- lib/backends/qdrant_backend.py: QdrantVectorStoreAdapter新規作成
- config_utils.py: storage_backend, qdrant_url, qdrant_api_key, qdrant_collection_prefix設定追加
- vector_utils.py: デュアルバックエンドスイッチ、移行ヘルパー実装、find_similar_memories構文エラー修正
- memory_mcp.py: 移行ツール（migrate_sqlite_to_qdrant_tool, migrate_qdrant_to_sqlite_tool）追加
- tools_memory.py: 移行ツールをMCPツールとして登録
- README.md, DOCKER.md: Qdrant設定・移行説明追加
- .vscode/memory-bank/activeContext.md, progress.md: Phase 23完了反映

### 検証結果
- ✅ qdrant-clientインストール成功
- ✅ QdrantVectorStoreAdapterの実装完了
- ✅ Qdrantサーバー起動（port 6333）成功
- ✅ storage_backend=qdrantでサーバー起動（port 8001）成功
- ✅ Qdrant HTTPリクエストログでコレクション作成確認（memory_default）
- ✅ find_similar_memories構文エラー修正
- ✅ 移行ツールMCP登録完了
- ✅ README/DOCKER.mdドキュメント更新完了
- ✅ Git commit & push成功

---

## Phase 22.5 詳細: Docker環境最適化
- 2025-10-23: Phase 10 完了・メモリ移行
- 2025-10-22: Phase 9 完了・FastMCP依存関数実装
- 2025-10-21: Phase 8 完了・Persona別ディレクトリ構造実装
- 2025-10-20: Phase 7 完了・Personaサポート実装
- 2025-10-19: Phase 6 完了・SQLiteデータベース移行
- 2025-10-18: Phase 5 完了・プロジェクトメモリーバンク構築
- 2025-10-17: Phase 4 完了・Reranking追加
- 2025-10-16: Phase 3 完了・RAG検索実装
- 2025-10-15: Phase 2 完了・既存メモリ移行
- 2025-10-14: Phase 1 完了・基本的なCRUD操作

---

## Phase 23 詳細: Docker環境最適化

### 主な改善点
1. **設定管理の統一**
   - config_utils.pyに集約（get_data_dir, get_memory_root, get_logs_dir, get_cache_dir）
   - 環境変数とconfig.jsonの優先度を明確化（defaults < env < config.json）
   - 例外: server_host/server_portは環境変数でconfig.jsonをオーバーライド可能（運用簡略化のため）

2. **環境変数記法の簡略化**
   - 二重アンダースコア（SECTION__KEY）と単一アンダースコア（SECTION_KEY）の両対応
   - vector_rebuild_*, auto_cleanup_*は自動的にネスト処理
   - SERVER_HOST/SERVER_PORTは最上位キーとして直接マッピング

3. **データディレクトリ構造の単純化**
   - MEMORY_MCP_DATA_DIRを親ディレクトリとして指定
   - その下にmemory/, logs/, cache/を自動配置
   - Dockerでは単一マウント（./data:/data）で全データ永続化

4. **キャッシュの統一**
   - 全キャッシュ（HuggingFace, Transformers, Sentence-Transformers, Torch）を/data/cache以下に統一
   - ホストマウントが1つで済む構成

5. **本番ポート設定**
   - 開発環境: 8000 (config.json)
   - 本番環境: 26262 (環境変数MEMORY_MCP_SERVER_PORT)
   - ポート競合を回避

6. **ネットワークバインド最適化**
   - デフォルトを127.0.0.1から0.0.0.0に変更
   - コンテナ外部からのアクセスを許可

7. **ヘルスチェックエンドポイント追加**
   - GET /health → 200 OK
   - Dockerヘルスチェックが正常動作
   - persona、タイムスタンプ情報を返却

### 修正ファイル
- config_utils.py: 設定管理統一、環境変数パーサー改善、server_*/env優先度例外処理
- memory_mcp.py: /healthエンドポイント追加
- Dockerfile: EXPOSE 26262、HEALTHCHECK /health、データディレクトリ作成、キャッシュ環境変数設定
- docker-compose.yml: ポート26262マッピング、環境変数設定、単一マウント./data:/data
- README.md: 環境変数説明更新、優先度ルール明記、ポート設定例追加
- DOCKER.md: ポート26262、環境変数、マウント構成の説明更新

### 検証結果
- ✅ サーバが0.0.0.0:26262でバインド
- ✅ /healthエンドポイントが200 OKを返却
- ✅ Dockerヘルスチェック正常動作
- ✅ 単一データマウントで全データ永続化
- ✅ キャッシュディレクトリ統一
- ✅ ポート競合解消（開発8000、本番26262）

---

## 過去ログ・参考
- [Phase 0: 計画](https://example.com/phase0)
- [Phase 1: 基本機能実装](https://example.com/phase1)
- [Phase 2: nilou-memory.md完全移行](https://example.com/phase2)
- [Phase 3: RAG検索実装](https://example.com/phase3)
- [Phase 4: Reranking追加](https://example.com/phase4)
- [Phase 5: プロジェクトメモリーバンク構築](https://example.com/phase5)
- [Phase 6: SQLiteデータベース移行](https://example.com/phase6)
- [Phase 7: Personaサポート実装](https://example.com/phase7)
- [Phase 8: Persona別ディレクトリ構造実装](https://example.com/phase8)
- [Phase 9: FastMCP依存関数によるPersona取得](https://example.com/phase9)
- [Phase 10: メモリ移行、全ドキュメント更新](https://example.com/phase10)
- [Phase 11: Dockerコンテナ化](https://example.com/phase11)
- [Phase 12: 時間認識機能実装](https://example.com/phase12)
- [Phase 13: タグ管理とコンテキスト更新機能](https://example.com/phase13)
- [Phase 14: Rerankerバグ修正](https://example.com/phase14)
- [Phase 15: ドキュメント一新、GitHubリポジトリ公開](https://example.com/phase15)
- [Phase 16: 検索機能強化](https://example.com/phase16)
- [Phase 17: メモリ整理・管理機能](https://example.com/phase17)
- [Phase 18: パフォーマンス最適化](https://example.com/phase18)
- [Phase 19: AIアシスト機能](https://example.com/phase19)
- [Phase 20: 知識グラフ生成](https://example.com/phase20)
- [Phase 21: アイドル時自動整理](https://example.com/phase21)
- [Phase 22: Webダッシュボード実装](https://example.com/phase22)
