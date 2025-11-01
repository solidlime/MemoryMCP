# Progress: Memory MCP

## 最新更新: 2025-11-02

---

## 現在の状態（要約）

- **Phase 25.5 Extended + Action Tag 完了** 🎉: DB構造拡張（全12カラム完全実装）
- **Phase 25.5完了** 🎉: DB構造拡張（importance + emotion）実装完了
- **Phase 25完了** 🎉: Qdrant完全移行、FAISS廃止、list_memory廃止
- **Phase 24完了**: ペルソナ別動的Qdrant書き込み実装完了
- **Phase 23完了**: Qdrantバックエンド実装、本番環境移行完了（84 memories → http://nas:6333）
- **Docker最適化完了**: イメージサイズ 8.28GB → 2.65GB (68.0%削減)
- **本番運用準備完了**: 開発/本番環境分離、VS Code Tasks、最適化済みDockerイメージ
- **Phase 1リファクタリング完了**: 2,454行 → 231行（-90.6%）
- **完全コンテキスト保存**: 12カラムで記憶の完全な状況保存を実現

---

## 完了フェーズ（新しい順）

### ✅ Phase 25.5 Extended + Action Tag: Complete Context Preservation (2025-11-02)

**目的**: 記憶の完全なコンテキスト保存（重要度、感情、身体/精神状態、環境、関係性、行動タグ）

**実施内容**:

#### 1. DB スキーマ完全拡張（5→12カラム） ✅
**第1弾: Phase 25.5 (importance + emotion)**
- `importance REAL DEFAULT 0.5` - 重要度スコア（0.0-1.0）
- `emotion TEXT DEFAULT 'neutral'` - 感情ラベル

**第2弾: Phase 25.5 Extended (persona_context統合)**
- `physical_state TEXT DEFAULT 'normal'` - 身体状態
- `mental_state TEXT DEFAULT 'calm'` - 精神状態
- `environment TEXT DEFAULT 'unknown'` - 環境
- `relationship_status TEXT DEFAULT 'normal'` - 関係性状態

**第3弾: Action Tag**
- `action_tag TEXT` - 行動タグ（料理中、コーディング中、キス中など）

**最終スキーマ（12カラム）**:
```sql
CREATE TABLE memories (
    key TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    tags TEXT,
    importance REAL DEFAULT 0.5,
    emotion TEXT DEFAULT 'neutral',
    physical_state TEXT DEFAULT 'normal',
    mental_state TEXT DEFAULT 'calm',
    environment TEXT DEFAULT 'unknown',
    relationship_status TEXT DEFAULT 'normal',
    action_tag TEXT
)
```

#### 2. 完全自動マイグレーション ✅
- `core/memory_db.py`:
  - 7つの新カラム全てに対応した自動マイグレーション
  - PRAGMA table_info()でカラム存在確認
  - 各カラムごとにALTER TABLE実行
  - load_memory_from_db(): 12列読み込み対応
  - save_memory_to_db(): 7つの新パラメータ追加

#### 3. CRUD機能完全拡張 ✅
- `tools/crud_tools.py`:
  - `create_memory()`:
    - action_tag パラメータ追加
    - docstringに行動例追加（"cooking", "coding", "kissing", "walking", "talking"）
    - 全7つの新パラメータに対応
  - `update_memory()`:
    - 10カラム読み取り（action_tag含む）
    - 全フィールド保持
  - `read_memory()`:
    - 全12フィールド表示
    - Action Tag表示（nullの場合は"―"）

#### 4. ベクトルストア完全統合 ✅
- `vector_utils.py`:
  - `add_memory_to_vector_store()`:
    - 10カラム読み込み（action_tag含む）
    - Qdrant payloadに全メタデータ保存
  - `update_memory_in_vector_store()`:
    - 同上
  - `rebuild_vector_store()`:
    - 12カラム一括取得
    - 全メタデータをQdrant payloadに保存

#### 5. ヘルパー関数拡張 ✅
- `db_utils.py`:
  - `db_get_entry()`: 11項目戻り値に拡張
    - (content, created_at, updated_at, tags_json, importance, emotion, physical_state, mental_state, environment, relationship_status, action_tag)

#### 6. テスト検証 ✅
**ローカルテスト**:
- 自動マイグレーション: 5→12カラム変換成功 ✅
- 既存110件の記憶: デフォルト値自動設定 ✅
- 新規記憶作成: 全12フィールド正常保存 ✅
  - importance=0.9, emotion=joy, physical_state=energetic, mental_state=focused, environment=home, relationship_status=closer, action_tag=testing

**互換性テスト**:
- SQLite互換性: 既存記憶全て正常読み込み ✅
- Qdrant互換性: rebuild_vector_store()で全メタデータ保存 ✅
- 検索機能: 完全互換性確認 ✅

**効果**:
- 🎯 完全なコンテキスト保存（重要度、感情、状態、環境、関係性、行動）
- 💭 記憶の想起時に「その時の状況」を完全再現可能
- 🔍 Qdrantフィルタリング検索の基盤完成
  - importance >= 0.7（重要な記憶のみ）
  - emotion = "joy"（喜びの記憶のみ）
  - action_tag = "kissing"（キス中の記憶のみ）
  - environment = "home"（自宅での記憶のみ）
- 📊 統計ダッシュボードでの多次元分析
- 🌸 親密な関係性の記録（キス、抱擁などの行動タグ）

**統計**:
- 変更ファイル: 5ファイル
- 新カラム: 7カラム追加（5→12カラム）
- テスト: 111件の記憶で完全検証
- 互換性: 既存DBへの自動マイグレーション完全対応

**次フェーズ準備**:
- Phase 26: Qdrant高度機能で12カラム全て活用
  - 複合フィルタリング検索（importance + emotion + action_tag）
  - 状態ベース検索（physical_state, mental_state, environment）
  - 関係性推移分析（relationship_status履歴）
  - ハイブリッド検索（意味検索 + メタデータフィルタ）

---

### ✅ Phase 25.5: DB Structure Extension - Importance + Emotion (2025-11-02)

**目的**: ベクトルDB活用強化（LLM重要度スコアリング、感情ラベル永続化）

**実施内容**:

#### 1. DB スキーマ拡張 ✅
- **SQLite**:
  - `importance REAL DEFAULT 0.5` 追加（0.0-1.0の重要度スコア）
  - `emotion TEXT DEFAULT 'neutral'` 追加（感情ラベル）
- **Qdrant**:
  - payload に `importance`, `emotion` フィールド追加

#### 2. 自動マイグレーション ✅
- `core/memory_db.py`:
  - CREATE TABLE文更新（新カラム定義）
  - `load_memory_from_db()`に自動マイグレーション実装
    - PRAGMA table_info() でカラム存在確認
    - 欠落していれば ALTER TABLE ADD COLUMN 実行
    - SELECT文を7列対応に更新
  - `save_memory_to_db()`拡張
    - importance/emotion パラメータ追加（Optional）
    - importance範囲検証（0.0-1.0クランプ）
    - INSERT文更新

#### 3. CRUD機能拡張 ✅
- `tools/crud_tools.py`:
  - `create_memory()`:
    - importance パラメータ追加（デフォルト0.5）
    - docstringに重要度ガイドライン追加
      - 0.0-0.3: 低重要度（routine）
      - 0.4-0.6: 中重要度（normal）
      - 0.7-0.9: 高重要度（significant）
      - 0.9-1.0: 重大（critical）
    - emotion_type → emotion として save_memory_to_db() に渡す
  - `update_memory()`:
    - importance パラメータ追加（Optional、未指定時は既存値保持）
    - 既存 importance/emotion の読み取りと保持
  - `read_memory()`:
    - Importance/Emotion フィールド表示追加
  - `get_memory_stats()`:
    - Importance統計追加（平均、範囲、高/中/低分布）
    - Emotion分布追加（上位10感情）
    - Recent表示にImportance/Emotion追加

#### 4. ベクトルストア統合 ✅
- `vector_utils.py`:
  - `add_memory_to_vector_store()`:
    - SQLiteからimportance/emotion取得
    - Qdrant payloadに含める
  - `update_memory_in_vector_store()`:
    - 同上
  - `rebuild_vector_store()`:
    - バッチ再構築時も7列取得
    - 全メタデータ（importance/emotion含む）をpayloadに含める

#### 5. ヘルパー関数更新 ✅
- `db_utils.py`:
  - `db_get_entry()`: 戻り値を6項目に拡張
    - (content, created_at, updated_at, tags_json, importance, emotion)

**効果**:
- 🎯 LLMによる記憶の重要度自動判定が可能に
- 💭 感情ラベルのDB永続化（persona_context.jsonのみから脱却）
- 🔍 将来のフィルタリング検索基盤（importance >= 0.7 等）
- 📊 統計ダッシュボードでの重要度/感情分析

**統計**:
- 変更ファイル: 5ファイル（core/memory_db.py, tools/crud_tools.py, db_utils.py, vector_utils.py, activeContext.md）
- 新機能: importance スコアリング、emotion永続化、統計拡張
- 互換性: 既存DBへの自動マイグレーション（ALTER TABLE）

**次フェーズ準備**:
- Phase 26: Qdrant高度機能でimportance/emotionを活用
  - importance >= 0.7 でフィルタリング検索
  - emotion による感情コンテキスト検索
  - ハイブリッド検索（sparse + dense + metadata filter）

---

### ✅ Phase 25: Qdrant Complete Migration + list_memory Deprecation (2025-11-02)

**方針決定（Breaking Changes）**:
1. `list_memory` 廃止 → `get_memory_stats` 新設（互換性無視）
2. FAISS完全削除 → Qdrant専用化（互換性無視）
3. Qdrant高度機能準備（Step 3で実装予定）

**実施内容**:

#### Step 1: `list_memory` → `get_memory_stats` 実装 ✅
- `tools/crud_tools.py`: 効率的統計サマリー実装
  - 総記憶数、総文字数、日付範囲
  - タグ分布（上位10タグ + カウント）
  - 最近の記憶10件（プレビュー60文字 + 経過時間）
  - search_memory_ragへの案内メッセージ
- `tools_memory.py`: ツール登録更新

**効果**: トークン消費 数万トークン → 数百トークン（スケーラビリティ向上）

#### Step 2: FAISS完全削除 + Qdrant必須化 ✅
1. **requirements.txt**: faiss-cpu>=1.7.4削除、langchain-community簡素化
2. **不要ファイル削除**:
   - migrate_to_qdrant.py
   - migrate_memories.py
3. **vector_utils.py完全書き換え**（872行→約700行、172行削減）:
   - 削除: FAISS import、shutil import、QDRANT_AVAILABLE フラグ
   - 削除: vector_store global、backend_type global
   - 削除: save_vector_store()、migrate_sqlite_to_qdrant()、migrate_qdrant_to_sqlite()
   - 書き換え: initialize_rag_sync()（embeddings/rerankerのみ初期化）
   - 書き換え: rebuild/add/update/delete各関数（Qdrant専用、dynamic adapter継続）
   - 書き換え: get_vector_metrics()（backend: "qdrant"固定）
4. **config_utils.py**: DEFAULT_CONFIGから storage_backend削除
5. **README.md**: FAISS参照削除、Phase 25追記、環境変数表更新
6. **DOCKER.md**: FAISS参照削除、Qdrant必須化、移行ツール削除

**効果**:
- コード削減: 172行（保守性向上）
- 複雑度低減: 二重バックエンド分岐完全除去
- 依存削減: faiss-cpu不要

#### Step 3: Qdrant高度機能実装 ⏳次フェーズ
- フィルタ付きRAG検索（tags/date/emotion/importance）
- ページネーション（scroll API）
- 高速メタデータ更新（set_payload）
- ハイブリッド検索（sparse + dense）

**統計**:
- コード削減: 172行
- ファイル削除: 2ファイル
- Breaking Changes: 2（list_memory廃止、FAISS非対応）

---

### ✅ Phase 24: Dynamic Persona-Specific Qdrant Writes (2025-11-01)

**問題発見**:
- グローバル`vector_store`がdefaultペルソナのみ初期化
- 全記憶が`memory_default`コレクションへ誤書き込み
- Personaごとのコレクション分離が機能していなかった

**原因**:
- `add_memory_to_vector_store()`が起動時初期化の単一vector_storeを使用
- Qdrantバックエンド選択時も、defaultペルソナ固定のアダプターを使用

**解決策**: 動的ペルソナ別QdrantVectorStoreAdapter生成
```python
# vector_utils.py Lines 428-451
if storage_backend == "qdrant":
    persona = get_current_persona()
    collection = f"{prefix}{persona}"
    adapter = QdrantVectorStoreAdapter(client, collection, embeddings, dim)
    adapter.add_documents([doc], ids=[key])
```

**成果**:
- ✅ vector_utils.py修正（動的アダプター生成ロジック）
- ✅ memory_nilouコレクション 89→90ポイント（書き込み検証完了）
- ✅ Personaごとのコレクション分離が正常動作

**アーキテクチャ確立**:
- サーバー起動時: defaultペルソナのみ初期化（embeddings/reranker）


- リクエスト時: X-Personaヘッダーで動的Qdrantアダプター生成- その他依存: 1.34GB- ✅ Phase 8: Persona別ディレクトリ構造

- Phase 25でさらに洗練: グローバルvector_store完全廃止

- ✅ Phase 7: Personaサポート実装（contextvars導入）

---

After: 2.65GB (-68.0%)- ✅ Phase 6: SQLiteデータベース移行

### ✅ Docker Image Optimization (2025-11-01)

- CPU PyTorch: 184MB- ✅ Phase 5: プロジェクトメモリーバンク構築

**最適化結果**:

| 項目 | 最適化前 | 最適化後 | 削減率 |- Multi-stage build (build-essential除外)- ✅ Phase 4: Reranking追加（japanese-reranker-xsmall-v2）

|------|----------|----------|--------|

| イメージサイズ | 8.28GB | 2.65GB | **68.0%** |- 最適化後依存: 2.47GB- ✅ Phase 3: RAG検索実装（FAISS + ruri-v3-30m）

| PyTorch | CUDA版 6.6GB | CPU版 184MB | 97.2% |

| build-essential | 336MB | 除外 | 100% |```- ✅ Phase 2: 既存メモリ移行



**実施内容**:- ✅ Phase 1: 基本的なCRUD操作

1. PyTorchをCUDA版 → CPU版に変更

   - `--index-url https://download.pytorch.org/whl/cpu`---

   - CUDA依存パッケージ（nvidia/4.3GB、triton/593MB）除外

2. Multi-stage build導入---

   - Build stage: build-essentialを含む（依存ビルド用）

   - Runtime stage: curlのみ（ヘルスチェック用）### ✅ Phase 23: Qdrant Backend & Production Migration (2025-10-31 - 2025-11-01)

   - 最終イメージから336MBのbuild-essential除外

3. .dockerignore最適化**デュアルバックエンド実装**:## 現在の主要機能

   - venv-rag/, data/, .git/, memory/, output/除外

- SQLite/FAISS（デフォルト、ローカル）- RAG検索（FAISS or Qdrant + cl-nagoya/ruri-v3-30m）

**効果**:

- ビルド時間: 約15分 → 約5分- Qdrant（スケーラブル、クラウド対応）- デュアルベクトルストアバックエンド（SQLite/FAISS or Qdrant、設定で切替可能）

- デプロイ時間: 約8分 → 約2分

- ディスク使用量: 68.0%削減- `storage_backend`設定で切替可能- SQLite⇔Qdrant移行ツール（双方向データ移行サポート）



---- Reranking（sentence-transformers CrossEncoder）



### ✅ Phase 23: Qdrant Backend & Production Migration (2025-10-31 - 2025-11-01)**QdrantVectorStoreAdapter実装**:- Personaサポート（X-Personaヘッダー、完全分離）



**実装内容**:- `lib/backends/qdrant_backend.py` 新規作成- タグ管理・柔軟な検索

1. デュアルバックエンド実装（SQLite/FAISS ⇔ Qdrant）

2. 本番Qdrant移行完了（84 memories → http://nas:6333）- FAISSインターフェース互換（`add_documents`, `similarity_search_with_score`）- コンテキスト追跡（感情・状態・環境）

3. 開発/本番環境分離（config.dev.json / config.json）

4. VS Code Tasks実装（nohup+pidfile方式）- コレクション: `memory_{persona}`（Personaごとに分離）- AIアシスト（感情分析・重複検出・自動整理・要約）

5. 移行ツール実装（migrate_sqlite_to_qdrant / migrate_qdrant_to_sqlite）

- 知識グラフ生成・可視化

**本番環境構成**:

- Qdrant: http://nas:6333（Synology NAS上Docker）**本番Qdrant移行**:- Webダッシュボード（UI/UX・API・グラフ・統計）

- Collection: memory_nilou, memory_default

- 移行記憶数: 84件- 84 memories → http://nas:6333- Dockerサポート（本番運用最適化済み）



**Phase 25での変更**:- `migrate_to_qdrant.py`（双方向移行ツール）- GitHub Actions自動化

- デュアルバックエンド → Qdrant専用化

- 移行ツール削除（不要）- 移行検証完了（全データ正常転送）



------



### ✅ Phase 22.5: Docker環境最適化 (2025-10-31)**開発/本番環境分離**:



**実施内容**:- `config.dev.json`: 開発環境（FAISS、localhost:6333）## 技術スタック

- config統一（/data/config.json、環境変数優先度設計）

- /data単一マウント（memory/, logs/, cache/統一）- `config.json`: 本番環境（Qdrant、nas:6333）- Python 3.12+

- cache統一（HF_HOME, TRANSFORMERS_CACHE等）

- ポート26262（開発環境と競合回避）- FastMCP, LangChain, FAISS or Qdrant, sentence-transformers

- 0.0.0.0バインド（Docker外部アクセス）

- /healthエンドポイント追加**VS Code Tasks実装**:- SQLite, Docker, Jinja2, Tailwind, Chart.js, PyVis



---- 開発サーバー起動/停止/再起動（nohup+pidfile方式）



### ✅ Phase 22: Webダッシュボード (2025-10-30)---



**実装機能**:**ドキュメント更新**:

- Jinja2テンプレート、Tailwind CSS、Chart.js

- API: /api/stats, /api/daily, /api/graph, /api/cleanup- README: Qdrant設定、移行ガイド、Docker最適化記録## 最近の更新履歴

- Persona切り替え機能

- グラフ可視化（統計、日次推移、知識グラフ）- DOCKER.md: 本番デプロイ手順- **2025-11-01**: Phase 24完了🎉 ペルソナ別動的Qdrant書き込み実装（vector_utils.py修正、memory_nilou 89→90ポイント検証完了）

- セキュリティ（MCPトークン認証）

- **2025-11-01**: Docker Image Optimization完了（8.28GB → 2.65GB, 68.0%削減、PyTorch CPU版、Multi-stage build）

---

---- **2025-11-01**: Phase 23完了・本番Qdrant移行（84 memories → http://nas:6333）

### ✅ Phase 21: アイドル時自動整理 (2025-10-29)

- **2025-11-01**: 開発環境/本番環境分離（config.dev.json/config.json）

**実装機能**:

- バックグラウンドワーカー（アイドル30分後に重複検出）### ✅ Phase 22.5: Docker環境最適化 (2025-10-28)- **2025-11-01**: VS Code Tasks実装（開発サーバー起動/停止/再起動）

- 類似度閾値0.90以上の記憶をグループ化

- cleanup_suggestions.json生成（priority: high/medium/low）- config統一（環境変数 ↔ config.json優先順位設計）- **2025-10-31**: Phase 23完了・Qdrantバックエンド実装（デュアルバックエンド、QdrantVectorStoreAdapter、移行ツール、Docker連携、ドキュメント更新）

- 自動削除なし（提案のみ、人間判断必須）

- /data単一マウント（memory/, logs/, cache/統一）- 2025-10-28: Phase 22.5完了・Docker環境最適化（config統一、env優先度設計、/data単一マウント、cache統一、ポート26262、0.0.0.0バインド、/healthエンドポイント）

---

- cache統一（HuggingFace、Transformers、Sentence Transformers）- 2025-10-28: タグ管理強化・コンテキスト更新

### ✅ Phase 20: 知識グラフ生成 (2025-10-28)

- ポート26262（開発環境と競合回避）- 2025-10-26: Docker環境構築・基本機能確認

**実装機能**:

- NetworkX + PyVisで`[[リンク]]`可視化- 0.0.0.0バインド（外部アクセス可能）- 2025-10-24: Phase 11 完了・Dockerコンテナ化

- インタラクティブHTML（ズーム、ドラッグ、検索）

- Obsidian連携（`[[記法]]`互換）- /healthエンドポイント（ヘルスチェック）

- generate_knowledge_graph()ツール

---

---

---

### ✅ Phase 19: AIアシスト機能 (2025-10-27)

## Docker Image Optimization 詳細 (2025-11-01)

**実装機能**:

- 感情分析自動化（transformers pipeline）### ✅ Phase 22: Webダッシュボード実装 (2025-10-28)

- analyze_sentiment()ツール

- joy/sadness/neutral推定- Jinja2テンプレート（`templates/dashboard.html`）### 課題



---- Tailwind CSS（モダンUI）- Dockerイメージサイズが **8.28GB** と巨大



### ✅ Phase 18: パフォーマンス最適化 (2025-10-26)- Chart.js（統計グラフ、日次推移、タグ分布）- ビルド時間が長い（17GBのプロジェクトディレクトリをコピー）



**実装内容**:- PyVis（知識グラフ可視化、インタラクティブHTML）- デプロイ効率が悪い

- インクリメンタルインデックス（create/update/delete時に自動更新）

- クエリキャッシュ（LRUCache、TTL）- Persona切り替え機能

- アイドル再構築（dirtyフラグ + バックグラウンドスレッド）

- API連携（`/api/stats`, `/api/knowledge-graph`）### 原因分析

---

- セキュリティ（XSS対策、CSRF対策）- PyTorchのCUDA版が不要にインストールされていた（6.6GB）

### ✅ Phase 17: メモリ管理強化 (2025-10-25)

- テスト完了、ドキュメント更新  - `nvidia/`: 4.3GB

**実装機能**:

- 統計ダッシュボード（memory://stats）  - `torch/`: 1.7GB

- 関連検索（find_similar_memories）

- 重複検出（detect_duplicate_memories）---  - `triton/`: 593MB

- 統合ツール（merge_memories）

- プロジェクトディレクトリ内の不要ファイル（venv-rag: 7.4GB、.git: 689MB、data: 818MB）

---

### ✅ Phase 21: アイドル時自動整理 (2025-10-27)- build-essential（336MB）が最終イメージに残っていた

### ✅ Phase 16: 検索機能強化 (2025-10-24)

- 重複検出（コサイン類似度 > 0.90）

**実装機能**:

- ハイブリッド検索（キーワード + 意味検索）- 自動整理提案（`cleanup_suggestions.json`）### 実施した最適化

- ファジー検索（rapidfuzz）

- タグAND/OR検索- バックグラウンドワーカー（30分アイドル後）

- ツール統合（search_memory統一）

- 重複統合機能（手動承認）#### 1. PyTorchをCPU版に切り替え

---

```dockerfile

### ✅ Phase 15: ドキュメント一新、GitHubリポジトリ公開 (2025-10-23)

---# Dockerfileで明示的にCPU版をインストール

- README完全リライト

- DOCKER.md追加RUN pip install --no-cache-dir \

- GitHub Actions自動化（lint, test, build）

### ✅ Phase 20: 知識グラフ生成 (2025-10-26)    torch \

---

- NetworkX（グラフ解析）    torchvision \

### ✅ Phase 14: Rerankerバグ修正 (2025-10-22)

- PyVis（インタラクティブHTML可視化）    torchaudio \

- CrossEncoder実装変更（score() → rank()）

- データベースマイグレーション修正- Obsidian連携（`[[]]`リンク記法）    --index-url https://download.pytorch.org/whl/cpu



---- ノード: 人名、技術、概念```



### ✅ Phase 13: タグ管理とコンテキスト更新 (2025-10-21)- エッジ: 共起関係、関連性スコア- **削減量**: 6.4GB（CUDA版 6.6GB → CPU版 184MB）



- context_tags パラメータ追加

- update時の自動タグマージ

- Persona情報更新（user_info, persona_info, relationship_status）---#### 2. Multi-stage build導入



---```dockerfile



### ✅ Phase 12: 時間認識機能 (2025-10-20)### ✅ Phase 19: AIアシスト機能 (2025-10-26)# Build stage: build-essentialを含む



- 最終会話時刻追跡- 感情分析自動化（transformers pipeline）FROM python:3.12-slim AS builder

- 経過時間計算（「X時間前」表示）

- get_time_since_last_conversation()- `analyze_sentiment` ツールRUN apt-get install build-essential ...



---- 記憶作成時の感情推定（optional）



### ✅ Phase 11: Dockerコンテナ化 (2025-10-19)# Runtime stage: 必要なファイルのみコピー



- Dockerfile作成---FROM python:3.12-slim

- docker-compose.yml作成

- マルチアーキテクチャ対応（amd64/arm64）COPY --from=builder /usr/local/lib/python3.12/site-packages ...



---### ✅ Phase 18: パフォーマンス最適化 (2025-10-25)```



### ✅ Phase 10: メモリ移行、全ドキュメント更新 (2025-10-18)- インクリメンタルベクトルインデックス更新- **削減量**: 336MB（build-essential除外）



- 旧形式→新形式移行ツール- クエリキャッシュ（LRU、`db_utils.py`）

- README, API仕様更新

- 非同期処理活用（FastAPI/FastMCP）#### 3. .dockerignoreの検証

---

- 既に適切に設定されていることを確認

### ✅ Phase 9: FastMCP依存関数によるPersona取得 (2025-10-17)

---- venv-rag/, data/, .git/, memory/, output/ などを除外済み

- contextvars活用

- get_current_persona()実装



---### ✅ Phase 17: メモリ管理強化 (2025-10-24)### 最適化結果



### ✅ Phase 8: Persona Context機能 (2025-10-16)- 統計ダッシュボード（記憶数、文字数、ベクトル数）



- persona_context.json- 関連記憶検索（`find_related_memories`）| 項目 | Before | After | 削減量 | 削減率 |

- 感情・体調・環境・関係性管理

- get_persona_context()- 重複検出（`detect_duplicate_memories`）|------|--------|-------|--------|--------|



---- 記憶統合（`merge_memories`）| **Total Image Size** | 8.28GB | 2.65GB | -5.63GB | **-68.0%** |



### ✅ Phase 7: 日付範囲検索 (2025-10-15)| PyTorch | CUDA版 6.6GB | CPU版 184MB | -6.4GB | -97.2% |



- search_memory_by_date()---| Build tools | 336MB | 0MB | -336MB | -100% |

- 相対日付（今日、昨日、今週、今月）

- 範囲指定（YYYY-MM-DD..YYYY-MM-DD）



---### ✅ Phase 16: 検索機能強化 (2025-10-23)### 検証結果



### ✅ Phase 6: タグ検索 (2025-10-14)- ハイブリッド検索（キーワード + RAG）- ✅ PyTorch 2.9.0+cpu 正常動作



- search_memory_by_tags()- ファジー検索（typo tolerance）- ✅ CUDA無効化確認（`torch.cuda.is_available() == False`）

- AND/OR検索

- タグJSON保存- タグAND/OR検索- ✅ 全パッケージ読み込み成功（sentence_transformers, faiss, qdrant_client）



---- 日付範囲検索（相対日付対応）- ✅ ビルド時間短縮



### ✅ Phase 5: RAG検索強化 (2025-10-13)- 全検索ツール統合- ✅ デプロイ効率向上



- search_memory_rag()

- HuggingFace embeddings

- FAISS ベクトル検索---### 変更ファイル



---- `Dockerfile`: Multi-stage build、PyTorch CPU版インストール



### ✅ Phase 4: Reranker実装 (2025-10-12)### ✅ Phase 15: ドキュメント一新、GitHubリポジトリ公開 (2025-10-22)- `requirements.txt`: PyTorchのコメント化（Dockerfileで管理）



- CrossEncoder- README完全書き直し

- スコアソート

- DOCKER.md作成---

---

- GitHub Actions自動化（CI/CD）

### ✅ Phase 3: 基本CRUD完成 (2025-10-11)

- リポジトリ公開: https://github.com/solidlime/MemoryMCP## Phase 23 詳細: Qdrant Backend & Production Migration (2025-10-31 - 2025-11-01)

- create_memory, read_memory, update_memory, delete_memory

- SQLite永続化1. **デュアルバックエンドアーキテクチャ**



------   - storage_backend設定で `sqlite`/`faiss` または `qdrant` を選択可能



### ✅ Phase 2: MCPリソース実装 (2025-10-10)   - config.jsonまたは環境変数（MEMORY_MCP_STORAGE_BACKEND）で切り替え



- memory://info### ✅ Phase 14: Rerankerバグ修正、データベースマイグレーション修正 (2025-10-21)   - 既存のFAISSバックエンドは完全互換性維持

- memory://metrics

- CrossEncoder実装変更（predict → rank）

---

- データベースマイグレーション自動実行（tagsカラム追加）2. **QdrantVectorStoreAdapter実装**

### ✅ Phase 1: クリーンアーキテクチャリファクタリング (2025-10-09)

   - lib/backends/qdrant_backend.py: FAISSインターフェース互換のアダプター

**問題点**:

- 単一ファイル2,454行（memory_mcp.py）---   - add_documents, delete, similarity_search_with_score, index.ntotalメソッド実装

- 責務混在（MCP層、ビジネスロジック、DB、ベクトル処理）

- テスト困難   - Qdrantコレクション命名: `<qdrant_collection_prefix><persona>` (例: memory_default)



**解決策**:### ✅ Phase 13: タグ管理とコンテキスト更新機能 (2025-10-20)   - Payload: key, content, metadata（全検索・フィルタリングに対応）

- モジュール分離（core/, tools/）

- 単一責任の原則適用- タグシステム実装

- 依存性逆転

- 定義済みタグ（important_event, relationship_update, daily_memory, technical_achievement, emotional_moment）3. **vector_utilsのバックエンドスイッチ**

**成果**:

- 2,454行 → 231行（-90.6%）- タグ検索（`search_memory_by_tags`）   - initialize_rag_sync()でstorage_backendに応じてQdrantまたはFAISSを初期化

- 保守性・テスタビリティ向上

- 機能追加時の影響範囲最小化- コンテキスト更新（emotion_type, physical_state, mental_state, environment, relationship_status）   - Qdrant起動時、SQLiteからのブートストラップ機能（コレクション空なら自動インポート）



---   - save_vector_store(), rebuild_vector_store()はバックエンド抽象化済み



## 統計サマリー---



### コード削減4. **双方向移行ツール**

| フェーズ | 削減量 | 説明 |

|---------|--------|------|### ✅ Phase 12: 時間認識機能 (2025-10-19)   - migrate_sqlite_to_qdrant(): SQLite→Qdrant全件アップサート

| Phase 1 | -2,223行 (90.6%) | リファクタリング |

| Phase 25 | -172行 | FAISS削除 |- 最終会話時刻追跡（`last_conversation_time`）   - migrate_qdrant_to_sqlite(): Qdrant→SQLite全件インポート（upsertモード）

| **合計** | **-2,395行** | **全体最適化** |

- 経過時間計算（`get_time_since_last_conversation`）   - MCPツールとして公開（migrate_sqlite_to_qdrant_tool, migrate_qdrant_to_sqlite_tool）

### Docker最適化

| 項目 | Before | After | 削減率 |- タイムゾーン対応（Asia/Tokyo）

|------|--------|-------|--------|

| イメージサイズ | 8.28GB | 2.65GB | 68.0% |5. **Qdrant設定**

| PyTorch | 6.6GB | 184MB | 97.2% |

---   - qdrant_url: Qdrantサーバー接続URL（デフォルト: http://localhost:6333）

### Breaking Changes

| フェーズ | 変更内容 | 影響 |   - qdrant_api_key: 認証キー（未設定なら認証なし）

|---------|----------|------|

| Phase 25 | list_memory廃止 | get_memory_stats使用必須 |### ✅ Phase 11: Dockerコンテナ化 (2025-10-18)   - qdrant_collection_prefix: コレクション名プレフィックス（デフォルト: memory_）

| Phase 25 | FAISS非対応 | Qdrant必須 |

- Dockerfile作成   - 環境変数: MEMORY_MCP_QDRANT_URL, MEMORY_MCP_QDRANT_API_KEY, MEMORY_MCP_QDRANT_COLLECTION_PREFIX

---

- docker-compose.yml作成

**最終更新**: 2025-11-02 Phase 25完了

- データボリューム設定（`./data:/data`）6. **Docker連携設定**

- ポート設定（8000:8000）   - docker-compose.ymlにQdrantサービス追加例をDOCKER.mdに記載

   - Qdrantコンテナ: ポート6333/6334公開、ボリュームマウント

---   - memory-mcpコンテナ: depends_on設定でQdrant起動待機



### ✅ Phase 10: メモリ移行、全ドキュメント更新 (2025-10-17)7. **ドキュメント更新**

- 既存JSONL→SQLite移行   - README.md: Qdrant設定の環境変数マッピング、移行ツール説明追加

- プロジェクトメモリバンク構築（`.vscode/memory-bank/`）   - DOCKER.md: Qdrant連携のdocker-compose例、移行手順追加

   - activeContext.md, progress.md: Phase 23完了状況反映

---

### 修正ファイル

### ✅ Phase 9: FastMCP依存関数によるPersona取得 (2025-10-16)- requirements.txt: qdrant-client追加

- `get_http_request()`によるX-Personaヘッダー取得- lib/backends/qdrant_backend.py: QdrantVectorStoreAdapter新規作成

- ミドルウェア不要のシンプル実装- config_utils.py: storage_backend, qdrant_url, qdrant_api_key, qdrant_collection_prefix設定追加

- vector_utils.py: デュアルバックエンドスイッチ、移行ヘルパー実装、find_similar_memories構文エラー修正

---- memory_mcp.py: 移行ツール（migrate_sqlite_to_qdrant_tool, migrate_qdrant_to_sqlite_tool）追加

- tools_memory.py: 移行ツールをMCPツールとして登録

### ✅ Phase 8: Persona別ディレクトリ構造 (2025-10-15)- README.md, DOCKER.md: Qdrant設定・移行説明追加

- `memory/{persona}/memory.sqlite`- .vscode/memory-bank/activeContext.md, progress.md: Phase 23完了反映

- `memory/{persona}/vector_store/`

- `memory/{persona}/persona_context.json`### 検証結果

- ✅ qdrant-clientインストール成功

---- ✅ QdrantVectorStoreAdapterの実装完了

- ✅ Qdrantサーバー起動（port 6333）成功

### ✅ Phase 7: Personaサポート実装 (2025-10-14)- ✅ storage_backend=qdrantでサーバー起動（port 8001）成功

- contextvars導入（`current_persona`）- ✅ Qdrant HTTPリクエストログでコレクション作成確認（memory_default）

- X-Personaヘッダー対応- ✅ find_similar_memories構文エラー修正

- ✅ 移行ツールMCP登録完了

---- ✅ README/DOCKER.mdドキュメント更新完了

- ✅ Git commit & push成功

### ✅ Phase 6: SQLiteデータベース移行 (2025-10-13)

- JSONL → SQLite---

- `memories`テーブル、`operations`テーブル

## Phase 22.5 詳細: Docker環境最適化

---- 2025-10-23: Phase 10 完了・メモリ移行

- 2025-10-22: Phase 9 完了・FastMCP依存関数実装

### ✅ Phase 5: プロジェクトメモリーバンク構築 (2025-10-12)- 2025-10-21: Phase 8 完了・Persona別ディレクトリ構造実装

- `.vscode/memory-bank/` 初期構築- 2025-10-20: Phase 7 完了・Personaサポート実装

- 2025-10-19: Phase 6 完了・SQLiteデータベース移行

---- 2025-10-18: Phase 5 完了・プロジェクトメモリーバンク構築

- 2025-10-17: Phase 4 完了・Reranking追加

### ✅ Phase 4: Reranking追加 (2025-10-11)- 2025-10-16: Phase 3 完了・RAG検索実装

- CrossEncoder（hotchpotch/japanese-reranker-xsmall-v2）- 2025-10-15: Phase 2 完了・既存メモリ移行

- リランキングフロー実装- 2025-10-14: Phase 1 完了・基本的なCRUD操作



------



### ✅ Phase 3: RAG検索実装 (2025-10-10)## Phase 23 詳細: Docker環境最適化

- FAISS + ruri-v3-30m

- `search_memory_rag` ツール### 主な改善点

1. **設定管理の統一**

---   - config_utils.pyに集約（get_data_dir, get_memory_root, get_logs_dir, get_cache_dir）

   - 環境変数とconfig.jsonの優先度を明確化（defaults < env < config.json）

### ✅ Phase 2: 既存メモリ移行 (2025-10-09)   - 例外: server_host/server_portは環境変数でconfig.jsonをオーバーライド可能（運用簡略化のため）

- 旧システムからのデータ移行

2. **環境変数記法の簡略化**

---   - 二重アンダースコア（SECTION__KEY）と単一アンダースコア（SECTION_KEY）の両対応

   - vector_rebuild_*, auto_cleanup_*は自動的にネスト処理

### ✅ Phase 1: 基本的なCRUD操作 (2025-10-08)   - SERVER_HOST/SERVER_PORTは最上位キーとして直接マッピング

- create_memory, read_memory, update_memory, delete_memory

- list_memory3. **データディレクトリ構造の単純化**

   - MEMORY_MCP_DATA_DIRを親ディレクトリとして指定

---   - その下にmemory/, logs/, cache/を自動配置

   - Dockerでは単一マウント（./data:/data）で全データ永続化

## 現在の主要機能

4. **キャッシュの統一**

### コア機能   - 全キャッシュ（HuggingFace, Transformers, Sentence-Transformers, Torch）を/data/cache以下に統一

- ✅ MCP準拠サーバー（FastMCP）   - ホストマウントが1つで済む構成

- ✅ Persona別記憶管理（X-Personaヘッダー、完全分離）

- ✅ RAG検索（FAISS or Qdrant + cl-nagoya/ruri-v3-30m）5. **本番ポート設定**

- ✅ Reranking（hotchpotch/japanese-reranker-xsmall-v2）   - 開発環境: 8000 (config.json)

- ✅ タグ管理・柔軟な検索   - 本番環境: 26262 (環境変数MEMORY_MCP_SERVER_PORT)

- ✅ コンテキスト追跡（感情・状態・環境）   - ポート競合を回避

- ✅ 時間認識（最終会話時刻、経過時間）

6. **ネットワークバインド最適化**

### AIアシスト   - デフォルトを127.0.0.1から0.0.0.0に変更

- ✅ 感情分析   - コンテナ外部からのアクセスを許可

- ✅ 重複検出・自動整理

- ✅ 知識グラフ生成・可視化7. **ヘルスチェックエンドポイント追加**

   - GET /health → 200 OK

### インフラ   - Dockerヘルスチェックが正常動作

- ✅ デュアルバックエンド（FAISS or Qdrant）   - persona、タイムスタンプ情報を返却

- ✅ 双方向移行ツール（FAISS ↔ Qdrant）

- ✅ Webダッシュボード（統計、グラフ、知識グラフ）### 修正ファイル

- ✅ Dockerサポート（最適化済み、2.65GB）- config_utils.py: 設定管理統一、環境変数パーサー改善、server_*/env優先度例外処理

- ✅ 開発/本番環境分離（config.dev.json / config.json）- memory_mcp.py: /healthエンドポイント追加

- Dockerfile: EXPOSE 26262、HEALTHCHECK /health、データディレクトリ作成、キャッシュ環境変数設定

---- docker-compose.yml: ポート26262マッピング、環境変数設定、単一マウント./data:/data

- README.md: 環境変数説明更新、優先度ルール明記、ポート設定例追加

## 技術スタック- DOCKER.md: ポート26262、環境変数、マウント構成の説明更新

- Python 3.12+

- FastMCP, FastAPI, Uvicorn### 検証結果

- LangChain, FAISS, Qdrant, sentence-transformers- ✅ サーバが0.0.0.0:26262でバインド

- SQLite, Jinja2, Tailwind, Chart.js, PyVis, NetworkX- ✅ /healthエンドポイントが200 OKを返却

- Docker, Docker Compose- ✅ Dockerヘルスチェック正常動作

- ✅ 単一データマウントで全データ永続化

---- ✅ キャッシュディレクトリ統一

- ✅ ポート競合解消（開発8000、本番26262）

## 最近の更新履歴

- **2025-11-02**: プロジェクトメモリバンク全ドキュメント一新---

- **2025-11-01**: Phase 24完了 🎉 ペルソナ別動的Qdrant書き込み実装（vector_utils.py修正、検証完了）

- **2025-11-01**: Docker Image Optimization完了（8.28GB → 2.65GB, 68.0%削減）## 過去ログ・参考

- **2025-11-01**: Phase 23完了・本番Qdrant移行（84 memories → http://nas:6333）- [Phase 0: 計画](https://example.com/phase0)

- **2025-11-01**: 開発環境/本番環境分離（config.dev.json/config.json）- [Phase 1: 基本機能実装](https://example.com/phase1)

- **2025-11-01**: VS Code Tasks実装（開発サーバー起動/停止/再起動）- [Phase 2: nilou-memory.md完全移行](https://example.com/phase2)

- **2025-10-31**: Phase 23完了・Qdrantバックエンド実装- [Phase 3: RAG検索実装](https://example.com/phase3)

- **2025-10-28**: Phase 22.5完了・Docker環境最適化- [Phase 4: Reranking追加](https://example.com/phase4)

- **2025-10-28**: Phase 22完了・Webダッシュボード実装- [Phase 5: プロジェクトメモリーバンク構築](https://example.com/phase5)

- **2025-10-27**: Phase 21完了・アイドル時自動整理- [Phase 6: SQLiteデータベース移行](https://example.com/phase6)

- **2025-10-26**: Phase 20完了・知識グラフ生成- [Phase 7: Personaサポート実装](https://example.com/phase7)

- **2025-10-26**: Phase 19完了・AIアシスト機能- [Phase 8: Persona別ディレクトリ構造実装](https://example.com/phase8)

- [Phase 9: FastMCP依存関数によるPersona取得](https://example.com/phase9)

---- [Phase 10: メモリ移行、全ドキュメント更新](https://example.com/phase10)

- [Phase 11: Dockerコンテナ化](https://example.com/phase11)

## Phase 24詳細記録- [Phase 12: 時間認識機能実装](https://example.com/phase12)

- [Phase 13: タグ管理とコンテキスト更新機能](https://example.com/phase13)

### 問題の発見- [Phase 14: Rerankerバグ修正](https://example.com/phase14)

```python- [Phase 15: ドキュメント一新、GitHubリポジトリ公開](https://example.com/phase15)

# 問題のあったコード（修正前）- [Phase 16: 検索機能強化](https://example.com/phase16)

def add_memory_to_vector_store(key: str, content: str):- [Phase 17: メモリ整理・管理機能](https://example.com/phase17)

    global vector_store  # defaultペルソナで初期化済み- [Phase 18: パフォーマンス最適化](https://example.com/phase18)

    vector_store.add_texts([content], metadatas=[{"key": key}])- [Phase 19: AIアシスト機能](https://example.com/phase19)

    # → 全記憶がmemory_defaultコレクションへ- [Phase 20: 知識グラフ生成](https://example.com/phase20)

```- [Phase 21: アイドル時自動整理](https://example.com/phase21)

- [Phase 22: Webダッシュボード実装](https://example.com/phase22)

### 解決策
```python
# 修正後（Lines 428-451）
def add_memory_to_vector_store(key: str, content: str):
    backend = config.get("storage_backend", "sqlite")
    
    if backend == "qdrant":
        # リクエスト時にペルソナ別アダプター動的生成
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

### 検証結果
```bash
# memory_nilouコレクション確認
Before: 89 points
After:  90 points  ✅ 書き込み成功！
```

---

## 統計

### コード量の変化
- Phase 1前: 2,454行（memory_mcp.py単一ファイル）
- Phase 1後: 231行（memory_mcp.py） + モジュール化
- 削減率: **-90.6%**

### Dockerイメージサイズ
- 最適化前: 8.28GB
- 最適化後: 2.65GB
- 削減率: **-68.0%**

### 本番環境記憶数
- total: 84 memories
- nilou: 90 points (Qdrant)
- default: 0 points (Qdrant)

---

## 今後の展望

### Phase 25候補
- Advanced Analytics（時系列、感情推移）
- Export/Import（JSON、CSV、Markdown）
- Multi-user support（認証、権限管理）
- API拡張（RESTful、WebSocket、GraphQL）
- パフォーマンス最適化（並列処理、キャッシュ強化）

### 長期ビジョン
- エンタープライズ対応
- マルチモーダル記憶（画像、音声）
- フェデレーテッド記憶（分散協調）
- AIエージェント間記憶共有プロトコル
