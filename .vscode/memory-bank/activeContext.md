# Active Context: Memory MCP

## 現在の作業フォーカス

### プロジェクト状態

- **フェーズ**: Phase 16 - 検索機能強化 🔍 → Phase 17準備中（検索ツール統合）
- **ステータス**: Phase 16完了。検索ツールの整理統合を実施中。

# Active Context: Memory MCP

## 現在の作業フォーカス

### プロジェクト状態

- **フェーズ**: Phase 20 - AIアシスト機能（知識グラフ生成） �
- **ステータス**: Phase 20完了！知識グラフ生成機能実装、generate_knowledge_graphツール追加✨

### 最新の完了タスク（Phase 20）

1. ✅ **Phase 20 Step 1: 知識グラフライブラリ導入**
   - NetworkX: グラフ構造の構築と分析
   - PyVis: インタラクティブHTML可視化
   - `requirements.txt` に networkx>=3.0, pyvis>=0.3.0 追加
   - 既にvenv-ragにインストール済み

2. ✅ **Phase 20 Step 2: analysis_utils.py 新モジュール作成**
   - Phase 20以降の分析機能を集約（221行）
   - extract_links_from_memories(): メモリから[[リンク]]抽出
   - build_knowledge_graph(): NetworkXグラフ構築（ノード=リンク、エッジ=共起）
   - export_graph_json(): JSON形式エクスポート（統計付き）
   - export_graph_html(): PyVis可視化（物理演算、インタラクティブ）
   - Persona対応（全関数でpersona引数サポート）

3. ✅ **Phase 20 Step 3: generate_knowledge_graph ツール実装**
   - 2つの出力形式: json（データ）、html（可視化）
   - フィルタリングパラメータ: min_count, min_cooccurrence, remove_isolated
   - 統計情報: ノード数、エッジ数、密度、平均接続数
   - HTML出力: output/knowledge_graph_{persona}_{timestamp}.html
   - `memory_mcp.py` にツール追加（79行）、`tools_memory.py` に登録

4. ✅ **Phase 20 テスト**
   - nilou Persona: 71メモリ、23メモリにリンク含む
   - 生成結果: 18ノード、56エッジ
   - トップ接続: memory_mcp.py（11接続）、README.md（9接続）、らうらう（6接続）
   - JSON出力: 9156文字
   - HTML出力: 13KB、インタラクティブ可視化成功

5. ✅ **ドキュメント更新**
   - README.md: Phase 20セクション追加（知識グラフ生成詳細）
   - progress.md: Phase 20詳細セクション追加
   - activeContext.md: 最新状況反映（このファイル）

### 過去の完了タスク（Phase 19）

1. ✅ **Phase 19 Step 1: 感情分析パイプライン実装**
   - transformers pipeline 導入（sentiment-analysis）
   - モデル: lxyuan/distilbert-base-multilingual-cased-sentiments-student（66MB、軽量）
   - `vector_utils.py` に sentiment_pipeline、initialize_sentiment_analysis()、analyze_sentiment_text() 追加
   - initialize_rag_sync() から自動初期化

2. ✅ **Phase 19 Step 2: analyze_sentiment ツール実装**
   - テキストから感情を自動検出（joy/sadness/neutral）
   - 信頼度スコア付き結果
   - 感情別絵文字と解釈を表示
   - `memory_mcp.py` にツール追加、`tools_memory.py` に登録

3. ✅ **Phase 19 テスト**
   - 喜びのテキスト: joy 68.76% ✅
   - 悲しみのテキスト: sadness 91.78% ✅
   - 中立のテキスト: 検出精度確認
   - 全テストケース正常動作

4. ✅ **ドキュメント更新**
   - README.md: Phase 19セクション追加（感情分析機能）
   - progress.md: Phase 19詳細セクション追加
   - activeContext.md: 最新状況反映（このファイル）

### 過去の完了タスク（Phase 18）

1. ✅ **Phase 18 Step 1: インクリメンタルインデックス**
   - FAISS増分更新実装（add_documents/delete）
   - `vector_utils.py` の3関数改修（add/update/delete_memory_to_vector_store）
   - ハイブリッドアプローチ: try 増分更新 → except dirty flag フォールバック
   - 即座保存: すべての変更を即座にディスクに永続化

2. ✅ **Phase 18 Step 2: クエリキャッシュ**
   - cachetools.TTLCache 導入（maxsize=100, ttl=300秒）
   - `db_utils.py` にキャッシュインフラ追加
   - `memory_mcp.py` で create/update/delete 時にキャッシュクリア
   - スレッドセーフ: Lock保護されたキャッシュアクセス

3. ✅ **Phase 18 テスト**
   - 作成・更新・削除の全操作で正常動作確認
   - インクリメンタルインデックスが即座に検索に反映
   - キャッシュクリアが正常動作（最新データが検索可能）

4. ✅ **ドキュメント更新**
   - README.md: Phase 18セクション追加（技術詳細）
   - progress.md: Phase 18詳細セクション追加
   - activeContext.md: 最新状況反映（このファイル）

### 過去の完了タスク（Phase 17）

1. ✅ **Phase 17 Step 1: memory://stats リソース**
   - 統計ダッシュボード実装（総数、タグ・感情分布、タイムライン、リンク分析）
   - `get_memory_stats()` 関数追加
   - 過去7日間の棒グラフ表示

2. ✅ **Phase 17 Step 2: find_related_memories ツール**
   - 関連メモリ検索機能実装
   - `find_similar_memories()` 関数を vector_utils.py に追加
   - embeddings距離による類似度計算
   - 類似度スコアと経過時間を表示

3. ✅ **Phase 17 Step 3: detect_duplicates ツール**
   - 重複検出機能実装
   - `detect_duplicate_memories()` 関数を vector_utils.py に追加
   - 閾値ベースの重複ペア検出（デフォルト0.85）
   - 類似度順ソート

4. ✅ **Phase 17 Step 4: merge_memories ツール**
   - メモリ統合機能実装
   - 複数メモリを1つに統合（2-10個）
   - タグ結合、最古タイムスタンプ保持
   - 元メモリ削除オプション

5. ✅ **ドキュメント更新**
   - README.md: Phase 17機能の使用例追加
   - progress.md: Phase 17詳細セクション追加
   - activeContext.md: 最新状況反映（このファイル）

### 過去の完了タスク

1. ✅ **Phase 14: バグ修正**
   - Rerankerエラー修正（CrossEncoder実装変更）
   - データベースマイグレーションバグ修正

2. ✅ **Phase 15: ドキュメント一新 & リポジトリ公開**
   - README.md一新（技術的内容に集中）
   - DOCKER.md新規作成（完全なDockerガイド）
   - .gitignore作成
   - .vscode/memory-bank/一新（プライベート情報削除）
```
   - GitHubリポジトリ公開（https://github.com/solidlime/MemoryMCP）
   - GitHub Actions自動化（Dockerイメージ自動ビルド＆プッシュ）
   - MIT License適用

3. ✅ **Phase 16: 検索機能強化（完了）**
   - ハイブリッド検索実装（キーワード + RAG統合、スコアウェイト調整）
   - ファジー検索追加（タイポ・表記ゆれ対応、partial_ratio + 単語マッチング）
   - タグAND/OR検索（match_mode="any"/"all"）
   - 高度な複合検索（日付範囲 + タグ + キーワード/ファジー同時適用）
   - parse_date_query()ヘルパー関数化
   - rapidfuzzライブラリ導入
   - 全テスト成功、GitHubプッシュ完了

### 現在のフォーカス（Phase 16.5: 検索ツール統合 + 安定化 → 完了）

**課題**: 検索ツールが多すぎる（8個）→ 使う側が混乱

**統合計画（実施済み）**:
- 現在の8個のツールを **2個** に統合
  1. `search_memory` - 構造化検索（キーワード、ファジー、日付、タグ）
  2. `search_memory_rag` - 意味検索（自然言語クエリ、embeddings）

**削除対象（機能統合済み）**:
- `search_memory_hybrid` → `search_memory`に機能統合
- `search_memory_by_date` → `search_memory`に機能統合  
- `search_memory_by_tags` → `search_memory`に機能統合
- `search_memory_advanced` → `search_memory`に機能統合

**理由**:
- RAGは特殊な検索方式（embeddings + reranker）で自然言語に特化
- その他の構造化検索は1つのツールで十分対応可能
- シンプルで明確な役割分担

### 安定化と改善（完了）
- 読み取り系の全ツールを`memory_store`ではなくSQLite DB直読みへ統一
- `search_memory_rag`のタイムスタンプ表示バグ修正（DBからcreated_at取得）
- ベクトルストア再構築をDB直読み化し、`rebuild_vector_store_tool`を追加
- 書き込み時はDirtyフラグ→アイドル時バックグラウンド再構築（`config.json`の`vector_rebuild`で制御）
- tasks.jsonを強化（停止待機の確実化、Restartタスク追加）

### リファクタ（Step 2 完了）

- persona/パス解決を `persona_utils.py` に分離
- ベクタ/RAGロジックを `vector_utils.py` に分離（埋め込み・Reranker初期化、再構築、Dirty/アイドルワーカー）
- MCPツール登録を `tools_memory.py` に分離し「動的登録」へ移行（デコレータを `memory_mcp.py` から撤去）
- `memory_mcp.py` はエントリーポイントとしてスリム化（読み書きツール本体はプレーン関数のまま）
- E2Eテスト（`test_tools.py`）でCRUD/検索（構造化+RAG）/時間認識/コンテキスト更新を検証し全てグリーン

### 次期フェーズ候補（Phase 18以降）

**優先度: 高**

1. **パフォーマンス改善（Phase 18候補）**
   - インクリメンタルインデックス（個別メモリのembeddings更新）
   - キャッシュ最適化（SQLiteクエリ結果キャッシュ）
   - 並列処理対応（embeddings生成の並列化）

2. **AIアシスト機能（Phase 19候補）**
   - トピックモデリング（BERTopic）
   - メモリ自動要約（LLM統合）
   - 感情分析自動化（テキストから自動検出）

3. **Obsidian統合強化**
   - 自動バックリンク生成
   - グラフビュー対応
   - Dataviewクエリ対応

4. **エクスポート/インポート**
   - Markdown一括エクスポート
   - JSON/YAML形式サポート
   - 他MCPサーバー連携

**優先度: 中**

5. **メモリアーカイブ機能**
   - アーカイブフラグ追加（SQLite新カラム）
   - 通常検索から除外
   - 専用検索で閲覧可能

6. **アーキテクチャ改善**
```
   - プラグインシステム
   - WebSocket対応
   - REST API追加

**優先度: 低（アイデア段階）**

7. **マルチモーダル対応**
   - 画像メモリ（スクリーンショット保存・検索）
   - 音声メモリ（文字起こし＋保存）
   - リンクプレビュー（URL自動取得）

8. **コラボレーション**
   - メモリ共有機能
   - コメント機能
   - バージョン管理

9. **高度な分析**
   - トピックモデリング
   - 知識グラフ生成
   - 時系列分析

10. **セキュリティ**
    - メモリ暗号化
    - アクセス制御
    - 監査ログ

## 技術的な注意点

1. ✅ **RAG有効化**: embeddings + reranker の統合完了

### Reranker実装2. ✅ **キャッシュ移動**: HF関連キャッシュを `./.cache` に設定

- `sentence_transformers.CrossEncoder`を直接使用3. ✅ **設定管理**: `mcp_config.json` でモデル切り替え可能

- `langchain.retrievers.document_compressors`は使用しない（削除された）4. ✅ **Docker対応**: `Dockerfile`, `docker-compose.yml`, `DOCKER.md` 完全版作成

5. ✅ **メモリバンク更新**: ドキュメント正規化とMCP移行完了

### データベースマイグレーション6. ✅ **メモリ保存形式SQLite化**: JSONからSQLiteデータベースに移行完了

- 起動時に`load_memory_from_db()`を必ず呼び出す7. ✅ **複数人格メモリ実装**: Persona別ディレクトリ構造（memory/{persona}/memory.sqlite）完了

- `tags`カラムの自動追加処理が含まれる8. ✅ **Persona別ベクトルストア**: memory/{persona}/vector_store/ に分離完了

9. ✅ **レガシーデータ移行**: 旧形式から新形式へ自動移行実装完了

### Personaサポート10. ✅ **全ツールテスト**: create/read/update/delete/list/search/search_rag/search_by_date/clean 動作確認完了

- FastMCP の`get_http_request()`依存関数を使用11. ✅ **FastMCP依存関数実装**: get_http_request()によるPersona取得

- ミドルウェア不要のシンプル実装12. ✅ **ミドルウェア削除**: BaseHTTPMiddleware完全削除

13. ✅ **get_current_persona()実装**: ツール内でヘッダー直接取得

## 次のステップ候補14. ✅ **全ツール更新**: current_persona.get() → get_current_persona()

15. ✅ **defaultメモリのnilou移行**: 10件のメモリとベクトルストアをコピー

### 優先度: 中16. ✅ **README更新**: FastMCP依存関数のアーキテクチャ説明追加

- パフォーマンス最適化17. ✅ **全メモリバンク更新**: projectbrief, techContext, progress, activeContext

  - ベクトルストアのインデックス最適化18. ✅ **Dockerfile作成**: Multi-stage build, ヘルスチェック, ポート8000公開

  - 埋め込みモデルのバッチ処理19. ✅ **docker-compose.yml作成**: ボリュームマウント, 環境変数, 自動再起動

20. ✅ **DOCKER.md完全更新**: クイックスタート, トラブルシューティング, 本番デプロイ

### 優先度: 低21. ✅ **.dockerignore最適化**: ビルド高速化、イメージサイズ削減

- 追加機能22. ✅ **README Docker セクション追加**: Docker Compose使用方法

  - Web UI（オプション）23. ✅ **VS CodeからのPersonaヘッダーテスト**: X-Persona: nilouでリクエスト送信

  - 記憶のエクスポート/インポート機能24. ⏳ **Dockerコンテナテスト**: docker compose up -d で起動確認

  - GraphQL API（オプション）25. ✅ **Phase 12実装完了**: 時間経過認識機能の実装とテスト完了

26. ✅ **時間経過認識機能**: 

## 開発ガイドライン    - get_current_time(): タイムゾーン対応時刻取得

    - calculate_time_diff(): 時間差分計算（naive datetime自動変換）

### コード変更時の注意    - get_time_since_last_conversation(): 会話間経過時間ツール

1. 変更後は必ずテストスクリプトで確認    - 全メモリツールに経過時間表示追加（"3日前"形式）

2. ドキュメント（README.md、DOCKER.md、memory-bank/）を更新27. ✅ **create_memory拡張**: emotion_type, context_tagsパラメータ追加、persona_context.json自動更新

3. GitHubにpush前にprivate情報がないか確認28. ✅ **search_memory_by_date復活**: 日付範囲検索、相対日付表現、キーワードフィルタ対応

29. ✅ **バグ修正**: タイムゾーン問題、clean_memory修正

### 記憶管理のベストプラクティス30. ✅ **Phase 13-1実装完了**: persona_context.json構造改善

1. 重要な記憶には適切なタグを付ける31. ✅ **get_persona_context()更新**: 新しいコンテキスト構造に対応（user_info, persona_info, physical_state, mental_state, environment）

2. `[[リンク]]`記法で固有名詞をリンク化32. ✅ **Phase 13-2実装完了**: メモリタグ付けとコンテキスト更新機能

3. 時間情報を含む記憶は日付を明記33. ✅ **SQLiteスキーマ拡張**: tagsカラム追加、既存DBの自動マイグレーション実装

34. ✅ **create_memory大幅拡張**: physical_state, mental_state, environment, user_info, persona_info, relationship_status対応
35. ✅ **search_memory_by_tags()実装**: タグ検索機能、複数タグOR検索対応
36. ✅ **test_tools.py更新**: Phase 13-2テスト追加（Test 16-20）、全テスト成功
37. ✅ **ドキュメント更新**: README.md, copilot-instructions.md, progress.md, activeContext.md完全更新
38. 📝 **Phase 13-3計画**: セッション継続支援機能の設計

### 直近の変更（2025-10-29 - Phase 13-2実装完了）
  - SQLiteスキーマ拡張:
    - memoriesテーブルにtagsカラム（TEXT型、JSON形式）追加
    - PRAGMA table_info()による自動マイグレーション実装
    - 既存データベースを壊さずにカラム追加成功
  - create_memory()の大幅拡張:
    - 新パラメータ: physical_state, mental_state, environment, user_info, persona_info, relationship_status
    - context_tagsをSQLiteに永続化（JSON形式）
    - persona_context.jsonの全項目を一括更新可能
    - 戻り値に [context updated] 表示追加
  - save_memory_to_db()更新: tagsパラメータ追加、JSON形式で保存
  - load_memory_from_db()更新: tagsカラム読み込み、memory_storeに格納
  - search_memory_by_tags()ツール実装: タグ検索、複数タグOR検索、経過時間表示
  - test_tools.py更新: Phase 13-2テスト追加（Test 16-20）
    - 全パラメータを使った記憶作成テスト
    - persona_context更新確認テスト
    - タグ検索テスト（単一タグ・複数タグ）
    - 全25件の記憶でテスト実行、全テスト成功
  - ドキュメント更新:
    - README.md: 機能一覧更新、データ構造追加
    - copilot-instructions.md: ツール表更新、使用例追加
    - progress.md: Phase 13-2完了マーク、実装詳細
    - activeContext.md: 最新状況反映（このファイル）

### 直近の変更（2025-10-29 - Phase 13-1実装完了）
  - persona_context.json構造変更:
    - important_contexts削除（メモリに保存すべき内容のため）
    - user_info追加: name, nickname, preferred_address
    - persona_info追加: name, nickname, preferred_address
    - physical_state追加: 身体状態の管理
    - mental_state追加: 精神状態の管理
    - environment追加: 環境情報の管理
  - get_persona_context()ツール更新: 新構造に対応、わかりやすい表示
  - create_memory()簡素化: important_contexts保存ロジック削除
  - progress.md更新: Phase 13-1完了、Phase 13-2/13-3計画追加
  - activeContext.md更新: 最新状況反映（このファイル）

### 直近の変更（2025-10-29 - Phase 12実装完了）
  - Phase 12ステップ1-4完全実装: 時間認識基礎関数、時間経過ツール、create_memory拡張、全テスト
  - get_current_time()実装: ZoneInfoによるタイムゾーン対応
  - calculate_time_diff()実装: naive datetime自動変換、日本語フォーマット
  - load_persona_context()/save_persona_context()実装: バックアップ機能付き
  - get_time_since_last_conversation()ツール実装: 自動時刻更新
  - 経過時間表示追加: read_memory, list_memory, search_memory_rag, search_memory_by_date
  - create_memory拡張: emotion_type, context_tags対応、persona_context.json連携
  - search_memory_by_date復活: 今日/昨日/3日前/今週/先週/今月/YYYY-MM-DD/範囲指定
  - バグ修正: タイムゾーンnaive/aware混在問題、clean_memoryのsave_memory_to_file除去
  - test_tools.py更新: Phase 12機能テスト追加、全テスト成功
  - progress.md完全更新: Phase 12完了マーク、実装詳細、バグ修正履歴

### 直近の変更（2025-10-29 - Dockerコンテナ化）
  - Dockerfile作成: python:3.12-slim ベース、Multi-stage build
  - docker-compose.yml作成: ボリュームマウント、環境変数、ヘルスチェック
  - DOCKER.md完全書き直し: クイックスタートからトラブルシューティングまで
  - .dockerignore最適化: 不要ファイル除外、ビルド高速化
  - README.md Docker セクション追加: 使用方法とボリューム説明
  - projectbrief.md更新: Phase 11追加、Docker関連リソース追記
  - progress.md完全更新: Phase 11詳細、完了項目サマリー、技術仕様
  - activeContext.md更新: 最新タスク状況（このファイル）

### 直近の変更（2025-10-29 - FastMCP依存関数実装とドキュメント全更新）
  - FastMCP依存関数導入: `from fastmcp.server.dependencies import get_http_request`
  - ミドルウェア完全削除: PersonaMiddlewareクラスとStarletteインポート削除
  - get_current_persona()実装: HTTPリクエストからX-Personaヘッダーを直接取得
  - フォールバック実装: リクエスト取得失敗時はContextVarを使用
  - 全ツール更新: 8個の@mcp.tool()関数をget_current_persona()に変更
  - パス解決関数更新: get_persona_dir(), get_db_path(), get_vector_store_path()
  - defaultメモリのnilou移行: 10件のメモリとベクトルストアをコピー
  - README.md更新: VS Code設定例、アーキテクチャ説明、実装方法を追加
  - projectbrief.md更新: FastMCP依存関数、Phase 10完了を反映
  - techContext.md更新: get_http_request()の詳細、コード例を追加
  - progress.md完全書き直し: Phase 10の詳細、全フェーズサマリー
  - activeContext.md完全書き直し: 最新の作業状況と完了タスク

## 技術環境

### 実行環境
- **Python**: 3.12.3 (venv-rag)
- **FastMCP**: 0.9.0+ (streamable-http transport)
- **OS**: Linux (WSL / Ubuntu)

### データストレージ
- **SQLite**: memory/{persona}/memory.sqlite
- **FAISS**: memory/{persona}/vector_store/
- **ログ**: memory_operations.log (JSONL)

### モデルキャッシュ
- **場所**: `.cache/`
- **HuggingFace**: `.cache/huggingface/`
- **Transformers**: `.cache/transformers/`
- **Sentence-Transformers**: `.cache/sentence_transformers/`
- **Torch**: `.cache/torch/`

### Docker環境
- **Base Image**: python:3.12-slim
- **Port**: 8000
- **Volumes**: .cache, memory, memory_operations.log
- **Health Check**: curl -f http://localhost:8000/health

## 現在のPersona状況

### nilou Persona
- **データベース**: memory/nilou/memory.sqlite
- **ベクトルストア**: memory/nilou/vector_store/
- **メモリ数**: 10件（defaultから移行）
- **状態**: 稼働中、テスト待ち

### default Persona
- **データベース**: memory/default/memory.sqlite
- **ベクトルストア**: memory/default/vector_store/
- **メモリ数**: 10件（nilouにコピー済み）
- **状態**: バックアップとして保持

## 次の作業ステップ

### 優先度: 高
1. **Dockerコンテナテスト**
   - `docker compose up -d` で起動
   - ログ確認: `docker compose logs -f memory-mcp`
   - ヘルスチェック: `curl http://localhost:8000/health`
   - VS CodeからDocker接続テスト

2. **VS Code X-Personaヘッダーテスト**
   - settings.json に `"X-Persona": "nilou"` 設定
   - ログ確認: `🔄 Request received - Persona from header: nilou`
   - メモリ操作テスト（create, read, search_rag）

### 優先度: 中
3. **最終品質チェック**
   - 全ツール統合テスト
   - パフォーマンステスト（RAG + Reranking速度）
   - エラーハンドリング確認

4. **本番運用開始**
   - Dockerでの継続運用
   - メモリ蓄積の監視
   - ベクトルストアサイズ監視

### 優先度: 低
5. **機能拡張検討**
   - 日付範囲検索の強化
   - メモリ統計・分析機能
   - Obsidianプラグイン開発

## ブロッカー
- **なし**: 全フェーズ完了、Docker環境構築完了

## 成功メトリクス
- ✅ 全11フェーズ完了
- ✅ 全ツール動作確認済み
- ✅ Dockerコンテナ化完了
- ⏳ Docker起動テスト待ち
- ⏳ VS Code Personaヘッダーテスト待ち
- ⏳ 本番運用開始待ち

## 技術的課題
- **なし**: ミドルウェア削除により技術的負債解消

## 学び
1. **FastMCP依存関数**: ミドルウェアよりシンプルで効果的
2. **Persona別ディレクトリ**: データ分離でスケーラビリティ向上
3. **SQLite**: JSONより信頼性とパフォーマンスが優れている
4. **Docker**: 再現可能な環境構築に不可欠
5. **ドキュメント**: メモリバンクがセッション継続に極めて重要

## 備考
- 全ドキュメント最新化完了（README, DOCKER, projectbrief, progress, activeContext, techContext）
- 次セッションはDockerテストから開始予定

## 今後やりたいこと（2025-10-29 計画）

### 設定・構成改善
1. **設定ファイル名変更**: `mcp_config.json` → `config.json`
2. **設定項目追加**: 使用ポート設定（現在はハードコード8000）
3. **ホットリロード**: 設定ファイル変更時の自動再読み込み機能

### ドキュメント改善
4. **README更新**: appディレクトリのホストマウント推奨を記述

### 機能拡張
5. **記憶の定期整理**: 類似記憶をまとめていきたいけど、要約LLMを使うしかないかな・・・要検討
6. **重要度スコアリング**: high/middle/low もしくは1～0でスコアリングし、それを活用したRAG

### 公開・運用
7. **リモートリポジトリpush**: GitHub等への公開
