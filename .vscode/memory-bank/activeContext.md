# Active Context: Memory MCP

## 現在の状態

- **現在フェーズ**: Phase 27（ツール統合・簡素化）完了 🎉
- **次フェーズ**: Phase 28検討中
- **本番環境**: Qdrant (http://nas:6333) 運用中、sentencepiece依存解決済み
- **開発環境**: Qdrant専用（Phase 25でFAISS廃止完了）
- **最新DB構造**: 12カラム（完全コンテキスト保存）
- **最新ツール構成**: 5ツール（create_memory, read_memory, search_memory, delete_memory, helpers）

---

## 今日の作業（2025-11-03）

### Phase 27フォローアップ: 本番環境バグ修正 & 改善 ✨

#### sentencepiece依存問題解決 ✅
**問題**: NAS本番環境でRAG初期化失敗
- エラー: "Cannot instantiate this tokenizer from a slow version. If it's based on sentencepiece, make sure you have sentencepiece installed."
- 原因: ローカル環境では偶然インストール済みだったが、Dockerには含まれていなかった

**解決**:
- [x] requirements.txt に `sentencepiece>=0.1.99` 追加
- [x] vector_utils.py にエラーログ追加（デバッグ用）
- [x] NASでDockerイメージ再ビルド成功
- [x] RAG検索動作確認（create_memory成功）

#### Admin Tools更新 ✅
- [x] **dashboard.py**: "Rebuild Vector Store" → "Rebuild Qdrant Collection"
- [x] **templates/dashboard.html**: UI表示更新（FAISS→Qdrant）
- [x] メッセージ更新: "Successfully rebuilt Qdrant collection for {persona}"

#### コードリファクタリング調査 ✅
**発見した改善点**:
1. ✅ **重複インポート削除**: tools/crud_tools.py L625 の `from config_utils import load_config`
2. 📝 **将来の改善候補**（Phase 28以降）:
   - 共通SQLクエリ関数の集約（db_utils.py）
   - 定数の一元管理（SQLスキーマ）
   - 未使用コードの整理

---

## 最近の主要変更（Phase 27）

### Phase 27: ツール統合・簡素化（2025-11-02完了）

#### 実装目的
- 完全一致フィルタだと使いづらい問題を解消
- 例: `emotion="joy"` で "joyful", "overjoyed" もヒットさせたい
- 例: `action_tag="cook"` で "cooking", "cooked" もヒットさせたい

#### 実装内容
- [x] **Fuzzy Matchingアルゴリズム**
  - 完全一致 (`==`) → 部分一致 (`in`) に変更
  - 大文字小文字を無視（`.lower()`）
  - 6つのテキストフィルタ全てに適用:
    - emotion
    - action_tag
    - environment
    - physical_state
    - mental_state
    - relationship_status

#### 更新されたファイル
- [x] **tools/search_tools.py**
  - `search_memory_rag()`: 6つのテキストフィルタをFuzzy Matching化
  ```python
  # Before (完全一致)
  if emotion and meta.get("emotion") != emotion:
      continue
  
  # After (部分一致 + 大文字小文字無視)
  if emotion and emotion.lower() not in str(meta.get("emotion", "")).lower():
      continue
  ```

#### テスト準備
- [x] 本番環境に3つのテスト記憶作成:
  1. emotion="joyful" (fuzzy test: "joy")
  2. action_tag="cooking" (fuzzy test: "cook")
  3. environment="outdoors" (fuzzy test: "out")

#### Git管理
- [x] Git commit & push完了
  - コミット: "Phase 26.3: Fuzzy matching for text filters (emotion, action_tag, etc.)"
  - SHA: 09c4f24
  - プッシュ: 成功（18 objects, 177.38 KiB）

#### ドキュメント更新
- [x] `.github/copilot-instructions.md`
  - search_memory_rag例にFuzzy matching追加
  - search_memory例にfuzzy_match, fuzzy_threshold追加
  - Fuzzy matchingの特徴を説明セクション追加

---

### Phase 26: Advanced Qdrant Features（メタデータフィルタリング + カスタムスコアリング）完了 ✅

#### 実装内容
- [x] **メタデータフィルタリング（7パラメータ）**
  - `min_importance`: 重要度フィルタ（0.0-1.0）
  - `emotion`: 感情フィルタ
  - `action_tag`: 行動タグフィルタ
  - `environment`: 環境フィルタ
  - `physical_state`: 身体状態フィルタ
  - `mental_state`: 精神状態フィルタ
  - `relationship_status`: 関係性フィルタ

- [x] **カスタムスコアリング（2パラメータ）**
  - `importance_weight`: 重要度スコアの重み（0.0-1.0、デフォルト: 0.0）
  - `recency_weight`: 新しさの重み（0.0-1.0、デフォルト: 0.0）

#### 更新されたファイル
- [x] **tools/search_tools.py**
  - `search_memory_rag()`: 9パラメータ追加（7フィルタ + 2スコア）
  - フィルタリングロジック実装
  - カスタムスコアリング実装

#### テスト結果（完全成功）
- ✅ Test 1: 重要度フィルタ (`min_importance=0.7`) → 3 hits
- ✅ Test 2: 感情フィルタ (`emotion="joy"`) → 3 hits
- ✅ Test 3: 行動タグフィルタ (`action_tag="coding"`) → 2 hits
- ✅ Test 4: 複合フィルタ (`emotion="love"` AND `action_tag="kissing"`) → 1 hit (perfect match)
- ✅ Test 5: カスタムスコアリング → スコア表示正常

#### Git管理
- [x] Git commit & push完了
  - コミット: "Phase 26: Advanced Qdrant features (metadata filtering + custom scoring)"
  - SHA: 328ce62
  - プッシュ: 成功（18 objects, 177.38 KiB）

---

### Phase 25.5 Extended + Action Tag: 完全コンテキスト保存（全12カラム実装完了）✨

#### 実装内容
- [x] **Action Tag追加（第3弾）**
  - `action_tag TEXT` - 行動タグ（料理中、コーディング中、キス中など）
  - CREATE TABLE文に追加
  - 自動マイグレーション実装
  - create_memory()にaction_tagパラメータ追加
  - 全ベクトルストア関数でaction_tagをQdrant payloadに追加

- [x] **Phase 25.5 Extended: persona_context統合（第2弾）**
- [x] **Phase 25.5 Extended: persona_context統合（第2弾）**
  - `physical_state TEXT DEFAULT 'normal'`
  - `mental_state TEXT DEFAULT 'calm'`
  - `environment TEXT DEFAULT 'unknown'`
  - `relationship_status TEXT DEFAULT 'normal'`

- [x] **Phase 25.5: importance + emotion（第1弾）**
  - `importance REAL DEFAULT 0.5`
  - `emotion TEXT DEFAULT 'neutral'`

#### 更新されたファイル
- [x] **core/memory_db.py**
  - CREATE TABLE: 12カラム完全実装
  - 自動マイグレーション: 7つの新カラム全て対応
  - load_memory_from_db(): 12列読み込み
  - save_memory_to_db(): 7つの新パラメータ追加

- [x] **tools/crud_tools.py**
  - create_memory(): action_tag含む全7パラメータ追加
  - update_memory(): 全フィールド保持
  - read_memory(): 全12フィールド表示

- [x] **db_utils.py**
  - db_get_entry(): 11項目戻り値（action_tag含む）

- [x] **vector_utils.py**
  - add_memory_to_vector_store(): 10カラム読み込み、全メタデータQdrant保存
  - update_memory_in_vector_store(): 同上
  - rebuild_vector_store(): 12カラム一括再構築

#### テスト結果
- ✅ ローカルテスト完全成功
  - 自動マイグレーション: 5→12カラム変換成功
  - 新規記憶作成: 全12フィールド正常保存
  - 既存110件: デフォルト値自動設定
  - 新規1件: importance=0.9, emotion=joy, action_tag=testing
- ✅ 互換性テスト完全成功
  - SQLite: 既存記憶全て正常読み込み
  - Qdrant: rebuild_vector_store()で全メタデータ保存
  - 検索機能: 完全互換性確認

---

### Phase 25.5 Extended: 完全コンテキスト保存（persona_context統合）（旧記録）
  - `physical_state TEXT DEFAULT 'normal'`
  - `mental_state TEXT DEFAULT 'calm'`
  - `environment TEXT DEFAULT 'unknown'`
  - `relationship_status TEXT DEFAULT 'normal'`
- [x] core/memory_db.py更新
  - [x] CREATE TABLE文に4カラム追加
  - [x] 自動マイグレーション（4カラムのALTER TABLE）実装
  - [x] load_memory_from_db()を11列対応に更新
  - [x] save_memory_to_db()に4パラメータ追加
- [x] tools/crud_tools.py更新
  - [x] create_memory()で4状態をDBに保存
  - [x] update_memory()で4状態を保持
  - [x] read_memory()で4状態を表示
- [x] db_utils.py更新
  - [x] db_get_entry()を10項目戻り値に拡張
- [x] vector_utils.py更新
  - [x] add_memory_to_vector_store()でQdrant payloadに4状態追加
  - [x] update_memory_in_vector_store()同上
  - [x] rebuild_vector_store()で11列取得、全メタデータ保存

### Phase 25.5: DB構造拡張（importance + emotion）
- [x] DB スキーマ設計
  - SQLite: `importance REAL DEFAULT 0.5`, `emotion TEXT DEFAULT 'neutral'`
  - Qdrant: payloadにimportance/emotionを追加
- [x] core/memory_db.py更新
  - [x] CREATE TABLE文にimportance/emotion追加
  - [x] 自動マイグレーション（ALTER TABLE）実装
  - [x] load_memory_from_db()更新（7列対応）
  - [x] save_memory_to_db()拡張（importance範囲検証）
- [x] tools/crud_tools.py更新
  - [x] create_memory()にimportanceパラメータ追加
  - [x] update_memory()にimportanceパラメータ追加
  - [x] read_memory()でimportance/emotion表示
  - [x] get_memory_stats()でimportance/emotion統計表示
- [x] db_utils.py更新
  - [x] db_get_entry()の戻り値拡張（6項目対応）
- [x] vector_utils.py更新
  - [x] add_memory_to_vector_store()でimportance/emotionをpayloadに追加
  - [x] update_memory_in_vector_store()でimportance/emotionをpayloadに追加
  - [x] rebuild_vector_store()でimportance/emotionを含むバッチ再構築
- [ ] 動作確認とテスト（次）

### Phase 25: FAISS完全削除 + list_memory廃止
- [x] Phase 25 Step 1: `list_memory` → `get_memory_stats` 実装完了
- [x] Phase 25 Step 2: FAISS完全削除 + Qdrant必須化完了
  - [x] requirements.txt更新（faiss-cpu削除）
  - [x] 不要ファイル削除（migrate_to_qdrant.py, migrate_memories.py）
  - [x] vector_utils.py完全書き換え（872行→700行、Qdrant専用化）
  - [x] config_utils.py更新（storage_backend削除）
  - [x] README.md更新（FAISS参照削除、Phase 25追記）
  - [x] DOCKER.md更新（FAISS参照削除、Qdrant必須化）
- [ ] Phase 25 Step 3: Qdrant高度機能実装（Phase 26へ）





---- [x] Phase 25の計画策定



## Phase 25: Qdrant完全移行 + 意味検索強化 🎉- [x] Phase 25実装開始: `list_memory` → `get_memory_stats` 書き換え---



### 方針決定（2025-11-02）- [ ] Phase 25実装: FAISS完全削除 + Qdrant必須化



1. ✅ **`list_memory` 廃止** → `get_memory_stats` のみ（互換性無視）- [ ] Phase 25実装: Qdrant機能フル活用---

2. ✅ **FAISS廃止** → Qdrant完全移行（互換性無視）

3. ⏳ **Qdrantの強力な機能をフル活用**（Step 3で実装予定）



**背景**:---## 今日のTODO（2025-11-01）

- `list_memory`は記憶が増えるとトークン消費が爆発的に増加（数百〜数千記憶で破綻）

- FAISSはローカル用途のみ、Qdrantのスケーラビリティを活かせていない

- Qdrantの強力な機能（フィルタリング、スクロール、ペイロード更新、ハイブリッド検索）が未使用

## Phase 25: Qdrant完全移行 + 意味検索強化 🚀## 今日の作業（2025-11-02）- ✅ Qdrantバックエンド実装完了

---



## Phase 25 実装ステップ

### 方針決定（2025-11-02）- [ ] プロジェクトメモリバンク全ドキュメント一新- ✅ 本番Qdrant (http://nas:6333) への全記憶移行完了（84件）

### ステップ1: `list_memory` 廃止 + `get_memory_stats` 実装 ✅完了

1. ✅ **`list_memory` 廃止** → `get_memory_stats` のみ（互換性無視）

**実施内容**:

- `tools/crud_tools.py`: `list_memory` → `get_memory_stats` 書き換え2. ✅ **FAISS廃止** → Qdrant完全移行（互換性無視）- [ ] MCPメモリサーバー（パーソナルメモリ）への記録- ✅ config.json/config.dev.json分離（本番/開発環境の安全な分離）

- `tools_memory.py`: ツール登録更新（`list_memory`削除、`get_memory_stats`追加）

3. ✅ **Qdrantの強力な機能をフル活用**

**新しい`get_memory_stats`の機能**:

```python- [ ] Phase 25の計画策定- ✅ VS Code Tasks実装（nohup+pidfile方式）

# 効率的な統計サマリー

- 総記憶数、総文字数**背景**:

- 日付範囲（最古〜最新）

- タグ分布（上位10タグ + カウント）- `list_memory`は記憶が増えるとトークン消費が爆発的に増加- ✅ Dockerイメージ最適化完了（8.28GB → 2.65GB, 68.0%削減）

- 最近の記憶10件（プレビュー60文字 + 経過時間）

- search_memory_ragへの案内メッセージ- FAISSはローカル用途のみ、Qdrantのスケーラビリティを活かせていない

```

- Qdrantの強力な機能（フィルタリング、スクロール、ペイロード更新）が未使用---- ✅ PyTorchをCPU版に切り替え（CUDA依存6.6GB削除）

**効果**:

- トークン消費: 数万トークン（全記憶リスト） → 数百トークン（統計のみ）

- スケーラビリティ: 記憶数に依存せず一定のレスポンスサイズ

### Phase 25 実装ステップ- ✅ Multi-stage build導入（build-essential除外）

---



### ステップ2: FAISS完全削除 + Qdrant必須化 ✅完了

#### ステップ1: `list_memory` 廃止 + `get_memory_stats` 実装 ✅進行中## 最近の完了事項- ✅ プロジェクトメモリバンク更新

**実施内容**:

- [x] `tools/crud_tools.py`: `list_memory` → `get_memory_stats` 書き換え

1. ✅ **requirements.txt更新**

   - `faiss-cpu>=1.7.4` 削除- [x] `tools_memory.py`: ツール登録更新（`list_memory`削除、`get_memory_stats`追加）- ✅ README更新（本番移行ガイド、Docker最適化記録）

   - Phase 25コメント追加

- [ ] テスト実行・動作確認

2. ✅ **不要ファイル削除**

   - `migrate_to_qdrant.py` 削除（移行スクリプト不要）- [ ] ドキュメント更新### ✅ Phase 24: Dynamic Persona-Specific Qdrant Writes (2025-11-01)- ✅ **Phase 24完了**: ペルソナ別動的Qdrant書き込み実装・検証成功🎉

   - `migrate_memories.py` 削除（移行スクリプト不要）



3. ✅ **vector_utils.py完全書き換え**（872行→約700行、172行削減）

   - 削除: `FAISS` import, `shutil` import, `get_vector_store_path()` import**新しい`get_memory_stats`の機能**:**問題発見**:

   - 削除: `QDRANT_AVAILABLE` フラグ、`vector_store` global、`backend_type` global

   - 削除: `save_vector_store()` 関数```python

   - 削除: `migrate_sqlite_to_qdrant()`, `migrate_qdrant_to_sqlite()` 関数

   - 書き換え: `initialize_rag_sync()` - ベクターストア初期化削除（embeddings/rerankerのみ）# 効率的な統計サマリー- グローバル`vector_store`がサーバー起動時にdefaultペルソナのみ初期化---

   - 書き換え: `rebuild_vector_store()` - Qdrant専用実装

   - 書き換え: `add_memory_to_vector_store()` - Qdrant専用（Phase 24 dynamic adapter継続）- 総記憶数、総文字数

   - 書き換え: `update_memory_in_vector_store()` - Qdrant専用

   - 書き換え: `delete_memory_from_vector_store()` - Qdrant専用- 日付範囲（最古〜最新）- 全ての記憶が`memory_default`コレクションへ誤書き込み

   - 書き換え: `get_vector_count()` - Qdrant専用

   - 書き換え: `get_vector_metrics()` - `"backend": "qdrant"` 固定- タグ分布（上位10タグ + カウント）



4. ✅ **config_utils.py更新**- 最近の記憶10件（プレビュー60文字 + 経過時間）- Personaごとのコレクション分離が機能していなかった## 🎯 最近の主要完了事項

   - `DEFAULT_CONFIG` から `"storage_backend": "sqlite"` 削除

   - Qdrant設定のみ残す- search_memory_ragへの案内メッセージ



5. ✅ **README.md更新**```

   - 「マルチバックエンド」 → 「Phase 25: Qdrant専用化」

   - FAISS参照削除（6箇所）

   - `MEMORY_MCP_STORAGE_BACKEND` 環境変数削除

   - Phase 24移行ガイド削除**メリット**:**原因**:### Phase 24: Dynamic Persona-Specific Qdrant Writes ✅ 🎉

   - Phase 25セクション追加

- ✅ トークン消費を大幅削減（数千件でも安全）

6. ✅ **DOCKER.md更新**

   - ディレクトリ構造からFAISS削除- ✅ 必要な情報だけを効率的に表示- `add_memory_to_vector_store()`がグローバルvector_storeを使用- ✅ **問題解決**: グローバルvector_storeによるdefaultペルソナ固定問題を修正

   - `MEMORY_MCP_STORAGE_BACKEND` 環境変数削除

   - docker-compose例からFAISS参照削除- ✅ 詳細検索は`search_memory_rag`で対応

   - 移行ツールセクション削除

- 起動時初期化の単一インスタンスを全リクエストで共有- ✅ **動的アダプター生成**: リクエスト時にペルソナ別QdrantVectorStoreAdapter作成

**効果**:

- コード削減: 172行（保守性向上）#### ステップ2: FAISS完全削除 + Qdrant必須化

- 複雑度低減: 二重バックエンド分岐の完全除去

- 依存削減: faiss-cpu削除、langchain-community簡素化- [ ] `vector_utils.py`: FAISSコード削除、Qdrant専用化- ✅ **vector_utils.py修正**: Lines 428-451（storage_backend判定 → 動的接続生成）



---  - グローバル`vector_store`削除（動的生成のみ）



### ステップ3: Qdrant高度機能実装 ⏳次フェーズ  - `backend_type` 変数削除**解決策**:- ✅ **検証完了**: memory_nilouコレクション 89→90ポイント（書き込み成功✨）



**実装予定**:  - FAISS関連インポート削除



1. **フィルタ付きRAG検索**: `search_memory_rag_filtered()`- [ ] `config_utils.py`: `storage_backend` デフォルトを `"qdrant"` に変更- `storage_backend == "qdrant"`の場合、動的アダプター生成に変更- ✅ **アーキテクチャ確立**: サーバー起動=default初期化、リクエスト=X-Personaヘッダーで動的切替

   ```python

   # Qdrant Filter APIを使用- [ ] `config.json` / `config.dev.json`: qdrant設定のみに簡素化

   from qdrant_client.models import Filter, FieldCondition, MatchValue

   - [ ] 移行ツール削除- リクエスト時に`get_current_persona()`でペルソナ取得

   def search_memory_rag_filtered(

       query: str,  - `migrate_to_qdrant.py` 削除

       tags: list[str] = None,

       date_range: str = None,  - `migrate_from_qdrant.py` 削除（存在すれば）- ペルソナ別`QdrantVectorStoreAdapter`を動的生成### Phase 23: Qdrant Backend & Production Migration ✅

       emotion: str = None,

       top_k: int = 5- [ ] `requirements.txt`: FAISS依存削除

   ):

       """  - `faiss-cpu` 削除- ペルソナ別コレクション（`memory_nilou`等）へ正確に書き込み- ✅ デュアルバックエンドシステム（SQLite/FAISS ⇔ Qdrant）

       タグ・日付・感情でフィルタリングしたRAG検索

       例: search_memory_rag_filtered("Python", tags=["technical_achievement"], date_range="2025-11")  - `langchain-community[faiss]` → `langchain-community` のみ

       """

       filter_conditions = []- [ ] ドキュメント更新- ✅ 本番Qdrant移行: **84 memories** → http://nas:6333

       if tags:

           filter_conditions.append(  - README.md: FAISS関連記述削除、Qdrant必須化記載

               FieldCondition(key="tags", match=MatchValue(any=tags))

           )  - DOCKER.md: 環境変数説明更新**修正箇所**:- ✅ 開発/本番環境完全分離（config.dev.json / config.json）

       # ... date_range, emotion も同様

         - systemPatterns.md: アーキテクチャ図更新

       # Qdrant scroll with filter

       results = client.search(- `vector_utils.py` Lines 428-451- ✅ VS Code Tasks（開発サーバー起動/停止/再起動）

           collection_name=collection,

           query_vector=embedding,**変更内容**:

           query_filter=Filter(must=filter_conditions),

           limit=top_k```python- 動的Qdrantアダプター生成ロジック実装

       )

   ```# Before (マルチバックエンド)



2. **ページネーション対応**: `list_memory_paginated()`storage_backend = config.get("storage_backend", "sqlite")### Docker Image Optimization ✅

   ```python

   # Qdrant scroll() APIでページングif storage_backend == "qdrant":

   def list_memory_paginated(page: int = 1, per_page: int = 20):

       offset = (page - 1) * per_page    # Qdrant処理**検証結果**:- ✅ **イメージサイズ削減**: 8.28GB → 2.65GB (**68.0%削減**)

       results, next_offset = client.scroll(

           collection_name=collection,else:

           limit=per_page,

           offset=offset    # FAISS処理- ✅ memory_nilouコレクション: 89→90ポイント（書き込み成功確認）- ✅ **PyTorch最適化**: CUDA版(6.6GB) → CPU版(184MB)

       )

       return {

           "memories": results,

           "page": page,# After (Qdrant専用)- ✅ Personaごとのコレクション分離が正常動作- ✅ **Multi-stage build**: build-essential除外で336MB削減

           "per_page": per_page,

           "has_next": next_offset is not None# storage_backend設定削除、Qdrant固定

       }

   ```qdrant_client = get_qdrant_client()- ✅ **ビルド時間短縮**: 本番デプロイ効率向上



3. **高速メタデータ更新**: `update_memory_tags_only()`collection = get_persona_collection_name()

   ```python

   # Qdrant set_payload() で埋め込み再計算なしvector_store = create_qdrant_adapter(client, collection)**アーキテクチャ確立**:

   def update_memory_tags_only(key: str, tags: list[str]):

       client.set_payload(```

           collection_name=collection,

           payload={"tags": tags},- サーバー起動時: defaultペルソナのみ初期化（グローバルvector_store）---

           points=[key]

       )#### ステップ3: Qdrant機能フル活用

   ```

**3-1. フィルタ付きRAG検索実装**- リクエスト時: X-Personaヘッダーでペルソナ切替 → 動的アダプター生成

4. **ハイブリッド検索**: `search_memory_hybrid()`

   ```python```python

   # Qdrant 1.7+ sparse + dense ベクトル

   # キーワード検索 + 意味検索の組み合わせasync def search_memory_rag_filtered(## 📋 Next Steps

   from qdrant_client.models import SparseVector

       query: str,

   def search_memory_hybrid(query: str, top_k: int = 5):

       # sparse: キーワードベクトル（TF-IDF等）    tags: Optional[List[str]] = None,---- [ ] 本番環境への修正デプロイ（vector_utils.py変更をDocker/NAS環境へ）

       # dense: 意味ベクトル（embeddings）

       results = client.search(    date_from: Optional[str] = None,

           collection_name=collection,

           query_vector=dense_vector,    date_to: Optional[str] = None,- [ ] 全ペルソナでのマルチペルソナ書き込みテスト（default, nilou, test）

           query_sparse_vector=sparse_vector,

           limit=top_k    emotion: Optional[str] = None,

       )

   ```    top_k: int = 5### ✅ Docker Image Optimization (2025-11-01)- [ ] Phase 25の検討（Advanced Analytics, Export/Import, Multi-user support）



**期待効果**:) -> str:

- フィルタ検索: タグ・日付・感情による高速絞り込み

- ページネーション: 大量記憶の段階的取得（UIフレンドリー）    """- PyTorchをCUDA版(6.6GB) → CPU版(184MB)に変更- [ ] WebダッシュボードのUI/UX微調整・API拡張

- 高速更新: タグ変更時の埋め込み再計算スキップ

- ハイブリッド検索: キーワードと意味の両立（検索精度向上）    Qdrantのフィルタ機能を活用した高度なRAG検索



---    """- Multi-stage build導入（build-essential除外）- [ ] 時系列記憶の高度化（Qdrant payload拡張: timestamp, emotion, importance）



## 最近の完了事項    # Qdrant Filter構築



### ✅ Phase 24: Dynamic Persona-Specific Qdrant Writes (2025-11-01)    filters = []- イメージサイズ: 8.28GB → 2.65GB (**68.0%削減**)



**問題発見**:    if tags:

- グローバル`vector_store`がサーバー起動時にdefaultペルソナのみ初期化

- 全ての記憶が`memory_default`コレクションへ誤書き込み        filters.append(FieldCondition(key="tags", match=MatchAny(any=tags)))- ビルド時間短縮、本番デプロイ効率向上## 記憶構造の設計案

- Personaごとのコレクション分離が機能していなかった

    if date_from:

**解決策**: 動的ペルソナ別アダプター生成

```python        filters.append(FieldCondition(key="created_at", range=Range(gte=date_from)))RAG + Qdrantで**時系列＋感情付き記憶**を実現するための設計案

# リクエストごとにアダプター生成（global vector_store廃止）

persona = get_current_persona()    # ... その他フィルタ

collection = f"{prefix}{persona}"

adapter = QdrantVectorStoreAdapter(client, collection, embeddings, dim)    ---

adapter.add_documents([doc], ids=[key])

```    # フィルタ付き検索



**効果**:    results = client.search(## 🧩 全体構造

- ✅ ペルソナ別コレクション分離正常化

- ✅ SQLiteディレクトリとの一貫性確保        collection_name=collection,

- ✅ contextvars活用でスレッドセーフ

        query_vector=embedding,### ✅ Phase 23: Qdrant Backend & Production Migration (2025-10-31 - 2025-11-01)```

### ✅ Docker最適化（Phase 23）

        query_filter=Filter(must=filters),

| 項目 | 最適化前 | 最適化後 | 削減率 |

|------|----------|----------|--------|        limit=top_k * 3- デュアルバックエンド実装（SQLite/FAISS ⇔ Qdrant）[出来事入力] → [感情推定・埋め込み生成]

| イメージサイズ | 8.28GB | 2.65GB | **68.0%** |

| PyTorch | CUDA版 6.6GB | CPU版 184MB | 97.2% |    )



**実施内容**:    # Reranking + 返却- QdrantVectorStoreAdapterクラス実装              → Qdrant（時系列＋ベクトル保存）

- PyTorchをCPU版に切り替え

- Multi-stage build導入```

- .dockerignore最適化

- 本番Qdrant移行完了（84 memories → http://nas:6333）              → [RAGで再想起・生成時に自己参照]

---

**3-2. ページネーション実装**

## 技術的詳細

```python- 双方向移行ツール（`migrate_to_qdrant.py`）```

### Phase 25アーキテクチャ（Qdrant専用）

async def list_memory_paginated(

```mermaid

graph LR    page: int = 1,- 開発/本番環境完全分離（`config.dev.json` / `config.json`）

    A[MCP Client] -->|HTTP| B[FastMCP Server]

    B --> C[tools_memory.py]    per_page: int = 20,

    C --> D[tools/crud_tools.py]

    C --> E[tools/search_tools.py]    sort_by: str = "created_at",- VS Code Tasks実装（nohup+pidfile方式）### 1️⃣ 出来事入力層

    D --> F[vector_utils.py]

    E --> F    order: str = "desc"

    F -->|Per-request| G[QdrantVectorStoreAdapter]

    G -->|HTTP| H[Qdrant Server]) -> str:- ドキュメント更新（README、DOCKER.md）* 入力：テキスト or 対話ログ or 状態変数

    D --> I[SQLite]

        """

    style A fill:#e1f5ff

    style B fill:#fff4e1    Qdrantのscroll機能を活用したページネーション* 追加情報：`timestamp`, `context_id`, `emotion`, `importance`

    style F fill:#ffe1e1

    style G fill:#e1ffe1    """

    style H fill:#ffe1f5

    style I fill:#f5e1ff    offset = (page - 1) * per_page---* 感情はLLMか小型分類器で推定

```

    results = client.scroll(

**データフロー**:

1. MCPクライアントがツール呼び出し        collection_name=collection,  　→ 「安堵」「焦燥」「達成」「虚無」など有限ラベルで十分

2. FastMCPがペルソナコンテキスト設定（`X-Persona`ヘッダー）

3. ツールが`get_current_persona()`でペルソナ取得        limit=per_page,

4. ペルソナ別Qdrantアダプター動的生成

5. Qdrantコレクション（`memory_{persona}`）へ読み書き        offset=offset,## 現在の主要課題

6. SQLiteへメタデータ保存

        with_payload=True,

**Phase 24との違い**:

- Phase 24: グローバル`vector_store`廃止 → 動的アダプター生成導入        with_vectors=False### 2️⃣ 記憶保存層（Qdrant）

- Phase 25: FAISS完全削除 → Qdrant専用実装に統一

    )

---

    # フォーマット + 返却### 1. Phase 25の計画

## 開発メモ

```

### Qdrant起動方法

**候補**:* Qdrantの各ベクトルに `timestamp`, `emotion`, `importance`, `persona`, `tags` をpayloadで付ける

**ローカル開発**:

```bash**3-3. 高速メタデータ更新**

./start_local_qdrant.sh

# または```python- [ ] Advanced Analytics（時系列分析、感情推移可視化）* 検索時はスコア計算を次のように拡張：

docker run -d -p 6333:6333 -p 6334:6334 \

  -v $(pwd)/qdrant_storage:/qdrant/storage \async def update_memory_tags_only(

  qdrant/qdrant:latest

```    key: str,- [ ] Export/Import機能（JSON、CSV、Markdown）



**本番環境**:    tags: List[str]

```yaml

# docker-compose.yml) -> str:- [ ] Multi-user support（認証、権限管理）  ```

services:

  qdrant:    """

    image: qdrant/qdrant:latest

    ports:    ベクトル再生成なしでタグのみ更新（超高速）- [ ] API拡張（RESTful API、WebSocket）  score = α * cosine_similarity + β * time_decay + γ * emotion_similarity

      - "6333:6333"

    volumes:    """

      - ./qdrant_storage:/qdrant/storage

```    point_id = key_to_point_id(key)- [ ] パフォーマンス最適化（並列処理、キャッシュ強化）  ```



**設定**:    client.set_payload(

```json

{        collection_name=collection,* emotionを単純なタグではなく、感情埋め込み（例えばdim=8〜16）で保持すると、

  "qdrant_url": "http://localhost:6333",  // 開発

  "qdrant_url": "http://nas:6333",        // 本番        payload={"tags": tags},

  "qdrant_collection_prefix": "memory_"

}        points=[point_id]### 2. Webダッシュボード改善  「近い感情の体験」を自然に呼び戻せる

```

    )

### 次回作業開始時のチェックリスト

    # SQLiteも更新- [ ] リアルタイム統計更新

1. ✅ Qdrantサーバー起動確認（`curl http://localhost:6333/collections`）

2. ✅ `get_memory_stats`動作確認（`mcp_memory_get_memory_stats()`）```

3. ✅ ペルソナ別分離確認（`X-Persona: nilou` で記憶作成→`memory_nilou`コレクション確認）

4. ⏳ Phase 25 Step 3開始判断- [ ] 知識グラフのインタラクティブ編集### 3️⃣ 再想起層（RAG）



---**3-4. ハイブリッド検索（Qdrant 1.7+）**



## 参考リンク```python- [ ] Personaごとの統計比較



- [Qdrant Documentation](https://qdrant.tech/documentation/)async def search_memory_hybrid(

- [Qdrant Filtering](https://qdrant.tech/documentation/concepts/filtering/)

- [Qdrant Scroll API](https://qdrant.tech/documentation/concepts/points/#scroll-points)    query: str,- [ ] タグ編集UI* 入力質問や文脈に対してQdrantで検索

- [Qdrant Payload](https://qdrant.tech/documentation/concepts/payload/)

- [Qdrant Hybrid Search](https://qdrant.tech/articles/hybrid-search/)    keywords: List[str],



---    top_k: int = 5* 類似内容＋近い感情＋近い時期の記憶を取得



**最終更新**: 2025-11-02 Phase 25 Step 2完了) -> str:


    """### 3. ドキュメント完全化* それらを**生成モデルの内部文脈として融合**

    セマンティック検索 + キーワード検索の融合

    """- [ ] API仕様書（OpenAPI）  → “今の自分の気分”や“過去の体験”が語り口に滲む

    # Qdrant 1.7+のハイブリッド検索機能を使用

    # スパースベクトル（BM25） + デンスベクトル（Embedding）- [ ] コントリビューションガイド

```

- [ ] トラブルシューティング拡充### 4️⃣ 再構築層（optional）

---

- [ ] ベストプラクティス集

## 最近の完了事項

* 一定期間ごとに記憶群を要約し、“内省ログ”を自動生成

### ✅ Phase 24: Dynamic Persona-Specific Qdrant Writes (2025-11-01)

**問題発見**:---* これが「自己物語」を形成する基盤になる

- グローバル`vector_store`がdefaultペルソナのみ初期化

- 全記憶が`memory_default`コレクションへ誤書き込み* 実装上は週次バッチで：



**解決策**:## 技術的負債

- リクエスト時にペルソナ別QdrantVectorStoreAdapter動的生成

- `vector_utils.py` Lines 428-451修正  ```



**成果**:### 優先度: 高  SELECT * FROM memories WHERE timestamp BETWEEN ...

- ✅ memory_nilouコレクション 89→90ポイント（書き込み成功）

- ✅ Personaごとのコレクション分離が正常動作- [ ] ユニットテスト追加（core/, tools/）  → LLMでサマリ生成 → 保存



---- [ ] 型ヒント完全化（mypy対応）  ```



### ✅ Docker Image Optimization (2025-11-01)- [ ] エラーハンドリング統一化

- PyTorchをCUDA版(6.6GB) → CPU版(184MB)に変更

- Multi-stage build導入### 🔮 人格を感じさせるためのポイント

- イメージサイズ: 8.28GB → 2.65GB (**68.0%削減**)

### 優先度: 中

---

- [ ] ログレベル設定（DEBUG/INFO/WARNING/ERROR）* **時間減衰**：古い感情は霞ませる（weightを下げる）

### ✅ Phase 23: Qdrant Backend & Production Migration (2025-10-31 - 2025-11-01)

- デュアルバックエンド実装（FAISS/Qdrant）- [ ] 設定バリデーション強化* **想起確率のゆらぎ**：完全再現ではなく確率的に呼び出す

- 本番Qdrant移行完了（84 memories → http://nas:6333）

- 開発/本番環境分離（config.dev.json / config.json）- [ ] デッドコード削除（旧tools_memory.py等）* **再書き込み**：再参照時にemotionを微更新（“思い出が変わる”）



---* **多様な感情表現**：単純なポジティブ/ネガティブではなく、多次元的に扱う



## 現在の主要課題### 優先度: 低



### Phase 25実装- [ ] パフォーマンスプロファイリング## 最新の完了タスク

- [ ] ステップ1完了: `get_memory_stats`動作確認

- [ ] ステップ2完了: FAISS完全削除- [ ] メモリリーク検証- ✅ Phase 22: Webダッシュボード実装（Jinja2, Tailwind, Chart.js, API, Persona切り替え, セキュリティ, テスト, ドキュメント更新）

- [ ] ステップ3完了: Qdrant機能フル活用

- [ ] セキュリティ監査- ✅ Phase 21: アイドル時自動整理（重複検出・提案・バックグラウンドワーカー）

### Phase 26候補

- Advanced Analytics（時系列分析、感情推移可視化）- ✅ Phase 20: 知識グラフ生成（NetworkX, PyVis, Obsidian連携、インタラクティブHTML）

- Export/Import機能（JSON、CSV、Markdown）

- Multi-user support（認証、権限管理）---- ✅ Phase 19: AIアシスト機能（感情分析自動化、transformers pipeline）

- API拡張（RESTful API、WebSocket）

- ✅ Phase 18: パフォーマンス最適化（インクリメンタルインデックス、クエリキャッシュ）

---

## 運用状況- ✅ Phase 17: メモリ管理強化（統計ダッシュボード、関連検索、重複検出、統合）

## メモ

- ✅ Phase 16: 検索機能強化（ハイブリッド検索、ファジー検索、Dataviewクエリ対応）

### Phase 25の意義

- **トークン効率**: `list_memory`廃止で大規模記憶に対応### 本番環境- ✅ Phase 15: ドキュメント一新 & リポジトリ公開

- **スケーラビリティ**: Qdrant専用化でクラウドスケール可能

- **機能強化**: Qdrant固有機能をフル活用- **Qdrant**: http://nas:6333- ✅ Phase 14: バグ修正（Rerankerエラー、データベースマイグレーションバグ）



### Phase 24からの教訓- **記憶数**: 84 memories (nilou: 90)- ✅ Phase 13: コンテキスト管理強化（persona_context.json構造改善、メモリタグ付け）

- 動的生成パターンは Persona分離に最適

- グローバル変数は動的Personaと相性が悪い- **稼働時間**: 安定稼働中- ✅ Phase 12: 時間経過認識機能（経過時間表示、キャッシュインフラ追加）

- Qdrantのcollection単位管理は強力

- **エラー**: なし

### 今後の注意点

- Qdrant必須化により、ローカル開発もQdrant必要---

- Docker Composeでローカル Qdrantを簡単起動

- 移行ツール不要（Qdrant一択）### 開発環境


- **Backend**: FAISS（デフォルト） or Qdrant (localhost:6333)## Qdrant移行 設計メモ（ドラフト）

- **ポート**: 8000（開発）、26262（本番）- 切替フラグ: `storage_backend` = `sqlite` | `qdrant`（env: `MEMORY_MCP_STORAGE_BACKEND`）

- **設定ファイル**: config.dev.json- Qdrant設定: `qdrant_url`, `qdrant_api_key`(任意), `qdrant_collection_prefix`（env対応）

- コレクション命名: `memory_{persona}`（prefix上書き可）

---- 埋め込み次元: モデルから動的検出（`get_sentence_embedding_dimension()`）

- 抽象インターフェース: `add/update/delete/search/rebuild/get_vector_count`

## 次のマイルストーン- 段階導入: 1) 接続・作成 2) 並行書き込み（ミラー）3) 既存全件移行 4) 切替 5) FAISSはフォールバックとして維持



### Phase 25候補タスク---

1. **Advanced Analytics**

   - 時系列記憶分析## 技術・設計メモ

   - 感情推移グラフ- Personaごとに独立したSQLite/FAISS/コンテキスト

   - タグ共起分析- MCPサーバーはFastMCP custom_routeでAPI/HTML/ファイル配信を統合

   - Persona間比較統計- AIアシスト: 感情分析・重複検出・自動整理・要約

- Webダッシュボード: glassmorphism, ダークグラデ, Chart.js, iframeグラフ, Persona切り替え

2. **Export/Import**- API: /api/personas, /api/dashboard/{persona}, /output/knowledge_graph_*.html

   - JSON完全エクスポート- セキュリティ: Persona名バリデーション、ファイルアクセス制限

   - CSV統計エクスポート- Docker・VS Code・Obsidian連携

   - Markdown知識ベースエクスポート

   - バックアップ/リストア機能---



3. **Multi-user Support**## 今後の拡張・アイデア

   - 認証（JWT、OAuth2）- 自動統合・要約（LLM連携）

   - 権限管理（Read/Write/Admin）- 定期レポート・メモリ健全性スコア

   - Personaアクセス制御- Obsidian統合強化（バックリンク・Dataview）

   - 監査ログ- マルチモーダル対応（画像・音声メモリ）

- コラボレーション・セキュリティ強化

4. **API拡張**

   - RESTful API（FastAPI Router）---

   - WebSocket（リアルタイム通知）

   - GraphQL（柔軟なクエリ）## 過去ログ・参考

   - Webhook（外部連携）- Phase 22以前の完了タスクや議事録は、progress.md や各 Phase のドキュメントを参照

- 重要な変更や決定事項は、GitHub のコミット履歴やプルリクエストを確認

---

## メモ

### Phase 24の教訓
- **グローバル変数の危険性**: 起動時初期化の単一インスタンスは動的Personaと相性が悪い
- **動的生成の重要性**: リクエストごとの動的アダプター生成でPersona分離を実現
- **検証の大切さ**: Qdrantコレクション数を確認することで問題を早期発見

### ベストプラクティス
- X-Personaヘッダーは常にリクエスト時に取得
- ペルソナ別リソース（DB、ベクトルストア、コンテキスト）は完全分離
- 動的生成でメモリ効率と分離を両立

### 今後の注意点
- Qdrantバックエンド使用時は動的アダプター生成を維持
- FAISSバックエンドはグローバルvector_store継続使用
- 新規バックエンド追加時は動的生成パターンを検討
