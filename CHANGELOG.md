# Changelog

All notable changes to Memory-MCP will be documented in this file.

## [Unreleased]

### Removed - 2026-02-17 (Deprecated Tables: Promises & Goals Removal)

#### 1. 専用テーブル（promises/goals）の完全削除

**問題:**
- promises/goalsテーブルが存在するが、タグベース方式と重複
- データ管理が二重化され、メンテナンス負荷が増大
- タグベース方式が推奨されているにも関わらず、レガシーシステムが残存

**削除対象:**
- テーブル: `promises`, `goals`
- 関数（6個）: `save_promise()`, `get_promises()`, `update_promise_status()`, `save_goal()`, `get_goals()`, `update_goal_progress()`
- ハンドラー: `handle_promise()`, `handle_goal()`

**移行ガイド:**
```python
# 旧方式（削除済み）
memory(operation="promise", content="...")

# 新方式（タグベース）
memory(operation="create", content="...",
       context_tags=["promise"],
       persona_info={"status": "active", "priority": 8})

# 完了マーク
memory(operation="update", query="memory_20250217_143022",
       persona_info={"status": "completed"})
```

**後方互換性:**
- `operation="promise"` / `"goal"` は非推奨メッセージを返す
- 既存データは影響なし（memoriesテーブルのタグベースデータは保持）

**効果:**
- データ管理の一元化
- コードベースの簡素化（~300行削減）
- タグベース方式への統一

**変更ファイル:**
- `core/memory_db.py`: テーブル定義削除、関数6個削除
- `tools/context_tools.py`: get_promises/get_goalsインポート削除、表示部分削除
- `tools/handlers/context_handlers.py`: handle_promise/handle_goal削除、非推奨メッセージ追加
- `tools/unified_tools.py`: context_operationsリスト更新、docstring更新

---

### Changed - 2026-02-17 (Promises & Goals: Tag-based Display)

#### 1. get_context()でタグベースPromises/Goalsを表示

**問題:**
- 🤝 Promises & Goalsセクションが専用テーブル（promises/goalsテーブル）からのみ取得
- "promise"や"goal"タグを持つメモリ（推奨方式）が表示されない
- メモリキーが表示されないため、LLMがupdateで使用するキーが不明

**修正:**
- タグベース（推奨方式）と専用テーブル（レガシー）の両方を表示
- タグベース: `[memory_key]` 形式でキーを表示
- 専用テーブル: `[P001]`, `[G001]` 形式でID表示（後方互換性）

**新しい表示形式:**
```
🤝 Promises & Goals:
   🏷️ Tagged Promises (2):
      1. [memory_20250217_143022] 週末にダンス披露...
         2日前 | ⭐0.80
   🏷️ Tagged Goals (1):
      1. [memory_20250216_120000] Pythonマスター...
         3日前 | ⭐0.75
   ✅ Table Promises (1):     # Legacy
      [P001] データベース最適化... [priority: 8]
```

**効果:**
- LLMがメモリキーを使ってupdateできる
- タグベース方式（推奨）が優先的に表示
- レガシーシステムとの互換性維持

**変更ファイル:**
- `tools/context_tools.py`: Promises & Goals表示ロジック改善

---

### Changed - 2026-02-17 (UX Improvements: Context Display & Operation Robustness)

#### 1. get_context() 出力の改善

**Memory Statistics削減:**
- 冗長な統計情報（Total Memories, Total Characters, Date Range）を削除
- Recent Memories のみを表示（最新5件のプレビュー）
- トークン消費をさらに削減

**Current Equipment表示強化:**
- 未装備部位を明示的に表示（例: `top: (未装備)`）
- 標準スロット定義: top, bottom, shoes, outer, accessories, head
- 装備選択の指針を追加: 「相手との関係性・時間帯・状況・会話の文脈に応じて適切な装備を選択してください」

**効果:**
- コンテキスト出力がさらに簡潔に
- 未装備部位が明確化され、装備管理が容易に
- 状況に応じた装備選択を促進

**変更ファイル:**
- `tools/context_tools.py`: get_context()関数の出力フォーマット改善

#### 2. Docstring改善（記憶作成の促進とタグ指示）

**記憶作成頻度の明示:**
- 「些細な出来事も含めて毎ターン記憶作成推奨」を明記
- CRITICAL WORKFLOWセクションに記憶作成の重要性を強調

**タグ使用の明確化:**
- タグは推奨だが必須ではない（タグなしでも記憶作成OK）
- タグ形式を明示: 単語形式（1-3 words, lowercase, no spaces）
- 例: `["promise", "milestone", "anniversary", "daily_routine"]`

**効果:**
- LLMが積極的に記憶を作成するように促進
- タグ使用のハードルを下げつつ、適切な形式を指導
- より豊富な記憶データベースの構築

**変更ファイル:**
- `tools/unified_tools.py`: memory() docstring更新
- `tools/context_tools.py`: get_context() docstring更新

#### 3. Operation誤記の吸収処理

**問題:**
- LLMが `operation="update_context, create_memory_if_not_exists"` のようなカンマ区切りの誤った値を渡す
- `operation="create_memory"` のように存在しない接尾辞を付ける

**修正:**
- カンマが含まれる場合、最初の有効なoperationのみを抽出
- `_if_not_exists`, `_memory` などの一般的な誤記を自動除去
- memory()とitem()の両方で正規化処理を実装

**例:**
- `"update_context, create_memory_if_not_exists"` → `"update_context"`
- `"create_memory"` → `"create"`

**効果:**
- LLMの操作ミスに対して堅牢に
- エラーメッセージではなく意図した操作を実行
- ユーザー体験の向上

**変更ファイル:**
- `tools/unified_tools.py`: memory()とitem()にoperation正規化処理追加

---

### Changed - 2026-02-17 (Major Refactoring: Simplification & Token Reduction)

#### 1. Memory Operations大幅削減（26→10種類）

**削減されたContext Operations:**
- `sensation`, `emotion_flow`, `situation_context` - 冗長な感情トラッキング
- `favorite`, `preference`, `anniversary` - タグベースメモリで代替可能

**削減されたItem Operations:**
- `item/rename`, `item/stats` - 使用頻度が低い機能

**残存Operations（10種類）:**
- Memory: `create`, `read`, `update`, `delete`, `search`, `stats`, `check_routines`
- Context: `promise`, `goal`, `update_context`

**影響:**
- ツールリストが簡潔になり、LLMの理解が向上
- 機能は失われず、タグベースメモリで同等の表現が可能

**変更ファイル:**
- `tools/unified_tools.py`: context_operationsリスト削減
- `tools/handlers/context_handlers.py`: 6個の廃止ハンドラー削除、import整理

#### 2. get_context()出力の簡素化（60-70%削減）

**削除されたセクション:**
- Reunion Context（再会強度・別離期間の複雑な計算）
- Emotional Alerts（約束遅延・長期不在・未解決感情アラート）
- Routine Check Available（ルーティンヒント）
- Pending Tasks/Plans Found（タスク一覧ヒント）
- 各種操作ガイド（promise/goal設定方法、read_memory tip等）
- User/Persona情報の記憶指示（システムプロンプトで対応）
- Recent Emotion Changes（最新5件の感情変化）
- 装備ヒント（"状況に応じて衣装を検討してください"）

**修正されたセクション:**
- Anniversaries → 30日以内のもののみ表示（from 全件表示）

**保持されたセクション:**
- Persona Context（Basic Info, Relationship, Equipment）
- Preferences（好きなもの・嫌いなもの）
- Physical Sensations（最新の身体感覚）
- Time Information（現在時刻・前回会話）
- Memory Statistics（総記憶数・文字数・期間）
- Recent Memories（最新5件のpreview）
- Promises & Goals（アクティブな約束・目標）
- Upcoming Anniversaries（30日以内の記念日アラート）

**効果:**
- トークン消費を大幅削減（~80行 → ~30行）
- 本質的な情報のみを提供
- システムプロンプトとの役割分担が明確化

**変更ファイル:**
- `tools/context_tools.py`: get_context()関数の大幅簡素化

#### 3. Docstring改善（LLMフレンドリー化）

**新しいDocstring構造:**
- 🎯 CRITICAL WORKFLOW - 最優先で読むべき使用フロー
- 📋 OPERATIONS - 利用可能な操作リスト
- 🏷️ SPECIAL TAGS - タグベース機能の説明
- 💡 QUICK EXAMPLES - 即座に使える実例
- ✅ VALID / ❌ INVALID - 明確な使用ルール

**変更内容:**
- `memory()` docstring: 37%削減、操作リスト簡素化
- `item()` docstring: 装備誤用の防止ルール強化（"濡れた服"、"涙"等は状態説明のみ）
- `get_context()` docstring: 冗長な指示セクション削除

**効果:**
- LLMが理解しやすいシンプルな構造
- 絵文字ヘッダーで視認性向上
- 誤用パターンの明示による品質向上

**変更ファイル:**
- `tools/unified_tools.py`: memory(), item() docstring更新
- `tools/context_tools.py`: get_context() docstring更新

#### 4. Knowledge Graph修正

**問題:**
- 新規追加したpersonaでKnowledge Graphが空になる
- `build_knowledge_graph()` 呼び出し時に `persona` パラメータが欠落

**修正:**
- `src/dashboard.py` の knowledge_graph ルートで `persona=persona` を追加

**変更ファイル:**
- `src/dashboard.py`: line 787にpersonaパラメータ追加

---

### Added - 2026-02-15 (Phase 43: Bug Fixes & Hybrid Search Optimization)

#### 1. MEMORY_ROOT定義のバグ修正 (dashboard.py)

**問題:**
- `src/dashboard.py` で `MEMORY_ROOT` が `src/memory/` を参照していた
- `MEMORY_MCP_DATA_DIR` 環境変数が未設定の場合、`SCRIPT_DIR`（src/）をベースにしていた
- knowledge_graph生成は正しく `data/memory/{persona}/` に保存しているが、ダッシュボードは `src/memory/` を参照
- **結果**: knowledge_graphが更新されてもダッシュボードに反映されない

**修正:**
- `src.utils.config_utils.ensure_memory_root()` を使用するように変更
- `data/memory/` ディレクトリを一貫して使用

**変更ファイル:**
- `src/dashboard.py`: MEMORY_ROOT定義を修正

#### 2. Anniversaries自動マイグレーション (起動時実行)

**問題:**
- anniversariesのマイグレーション処理は実装されていたが、`get_context()` 呼び出し時のみ実行
- ダッシュボードから直接アクセスした場合や、`get_context()` を経由しない場合、マイグレーションが実行されない
- **結果**: `persona_context.json` の `anniversaries` が memories テーブルに移行されない

**修正:**
- サーバー起動時に全personaの `persona_context.json` をチェック
- `anniversaries` データが存在する場合、自動的に memories テーブルにマイグレーション
- マイグレーション後、`persona_context.json` から `anniversaries` を削除

**変更ファイル:**
- `memory_mcp.py`: 起動時処理に anniversaries マイグレーションチェックを追加

#### 3. Reciprocal Rank Fusion (RRF) によるハイブリッド検索の最適化

**従来の問題:**
- ハイブリッド検索（`mode="hybrid"`）は semantic + keyword の結果を単純に並べていただけ
- 重複削除やスコアベースの統合が実装されていなかった
- 検索精度が最新のトレンドに対応していなかった

**RRF実装:**
- Reciprocal Rank Fusion アルゴリズムを実装
  - Formula: `score(d) = Σ 1 / (k + rank_i(d))`
  - 標準的な k=60 を使用
- semantic検索とkeyword検索の結果をランクベースでマージ
- 重複を自動的に削除し、統合スコアでソート
- 軽量（O(n log n)）でML不要、外部API不要

**新しいヘルパー関数:**
- `_extract_memory_keys()`: 検索結果文字列からメモリキーを抽出
- `_reciprocal_rank_fusion()`: RRFアルゴリズムでランクリストをマージ
- `_get_memories_by_keys()`: キーリストから詳細情報を取得
- `_format_hybrid_results()`: RRF結果をフォーマット

**変更ファイル:**
- `tools/search_tools.py`: RRFヘルパー関数追加、hybridモード実装を書き換え

**利点:**
- より高精度な検索結果
- 重複のない統合結果
- 軽量（DS920+等のNASでも快適に動作）
- 最新の検索トレンドに対応

---

### Added - 2026-02-14 (Phase 42: Usability Improvements for Self-Management)

#### Phase 1: Promises & Goals 一覧表示

**get_context に Promises & Goals の実データ表示を追加:**
- `get_context()` で active promises と active goals を直接表示
- 最大5件まで一覧表示（それ以上は件数のみ）
- 各 Promise/Goal の ID、内容プレビュー、期限、優先度/進捗を表示
- 設定がない場合は説明メッセージと設定方法のヒントを表示

**変更ファイル:**
- `tools/context_tools.py`: get_promises, get_goals をインポートし、直接データ取得・表示

#### Phase 2: 呼び方・呼ばれ方の記憶指示追加

**get_context にユーザー/ペルソナ情報の記憶指示を追加:**
- User Information セクションに記憶すべき情報のヒントを追加
  - ユーザー名が未設定の場合の記憶方法
  - ニックネーム、呼び方（preferred_address）の記憶方法
- Persona Information セクションにも同様のヒントを追加
  - ペルソナのニックネーム、呼ばれ方の記憶方法
- 既に設定されている場合は指示を表示しない

**変更ファイル:**
- `tools/context_tools.py`: User/Persona Information セクションに条件付き指示を追加

#### Phase 3: Context操作パラメータ改善（スキーマエラー削減）

**memory() 関数に直接パラメータを追加:**
- `arousal`, `heart_rate`, `fatigue`, `warmth`, `touch_response` パラメータ追加
- トップレベルパラメータを `persona_info` に自動マージする処理を追加
- `user_info` も `handle_context_operation` に渡せるように改善

**handle_update_context を拡張:**
- `user_info` フィールド（name, nickname, preferred_address）の更新に対応
- `physical_state`, `mental_state`, `environment`, `relationship_status`, `action_tag` の更新に対応
- `physical_sensations` の全フィールド（arousal, heart_rate, fatigue, warmth, touch_response）に対応
- 更新するフィールドがない場合のエラーメッセージを改善（使用例を表示）

**変更ファイル:**
- `tools/unified_tools.py`: memory() にパラメータ追加、マージロジック実装
- `tools/handlers/context_handlers.py`: handle_context_operation に user_info 追加、handle_update_context を拡張

#### Phase 4: Item操作自動追加機能（インベントリエラー削減）

**equip 操作に auto_add 機能を追加:**
- `item()` 関数に `auto_add: bool = True` パラメータ追加（デフォルトで有効）
- インベントリにないアイテムを自動で追加してから装備
- カテゴリ自動推定機能（`_auto_detect_category`）
  - アイテム名のキーワードから shoes, accessory, top, bottom, weapon, armor などを推定
  - 日本語・英語の両方に対応

**類似アイテム提案機能:**
- difflib を使ったファジーマッチング（cutoff=0.6）
- 存在しないアイテムと類似するアイテムを提案
- auto_add=False の場合は詳細なエラーメッセージと提案を表示

**変更ファイル:**
- `tools/unified_tools.py`: item() に auto_add パラメータ追加
- `tools/handlers/item_handlers.py`: handle_item_operation に auto_add 渡す処理追加
- `tools/equipment_tools.py`: equip_item に auto_add ロジックと _auto_detect_category 実装

#### Phase 5: ダッシュボード操作頻度表示

**新しい API エンドポイント追加:**
- `/api/memory-usage-stats/{persona}`: 記憶項目ごとの操作頻度統計
- operations テーブルから key ごとに集計
  - 総操作回数、create/read/update/delete/search の内訳
  - 初回アクセス日時、最終アクセス日時
  - 最終アクセスからの経過日数
  - 記憶の存在確認とコンテンツプレビュー

**フィルタリング・ソート機能:**
- `sort_by`: frequency, last_access, key
- `order`: asc, desc
- `min_days_inactive`: 一定期間アクセスがないアイテムをフィルタ
- `max_access_count`: アクセス回数が少ないアイテムをフィルタ

**サマリー統計:**
- 総キー数
- 低使用率アイテム数（≤3回アクセス）
- 30日間非アクティブアイテム数
- 削除済みキー数

**変更ファイル:**
- `src/dashboard.py`: `/api/memory-usage-stats/{persona}` エンドポイント追加

#### Phase 6: インベントリ操作後の装備品表示

**add_to_inventory と remove_from_inventory に装備品表示を追加:**
- アイテムを追加した後、現在の装備品が表示されるようになった
- アイテムを削除した後も、現在の装備品が表示されるようになった
- equip/unequip と同じフォーマットで統一された UX

**変更ファイル:**
- `tools/equipment_tools.py`: add_to_inventory, remove_from_inventory に装備品表示ロジック追加

#### Phase 7: Anniversary 自動マイグレーション & 統合表示

**persona_context.json からの自動マイグレーション:**
- `migrate_anniversaries_to_memories()` 関数追加（core/memory_db.py）
- get_context() 実行時に persona_context.json の anniversaries を自動マイグレーション
- MM-DD ベースの重複検出で既存の記念日と衝突を回避
- マイグレーション後は persona_context.json から anniversaries フィールドを削除

**Anniversary Calendar 統合表示:**
- `/api/anniversaries/{persona}` を拡張してタグベース + コンテキストベースの両方をマージ
- 下位互換性を保ちながら統合された記念日リストを返す
- ダッシュボードで両方のソースからの記念日を表示

**変更ファイル:**
- `core/memory_db.py`: migrate_anniversaries_to_memories() 追加
- `tools/context_tools.py`: get_context() でマイグレーション自動実行
- `src/dashboard.py`: /api/anniversaries エンドポイントを拡張

#### Phase 8: 操作頻度グラフ表示（Admin タブ）

**Memory Usage Statistics カード追加:**
- Admin タブに3種類の可視化を追加
  - **Pie Chart**: 操作タイプ別の割合（create/read/update/delete/search）
  - **Horizontal Bar Chart**: トップ20アクセス頻度の記憶項目
  - **Low-Usage Table**: 3回以下のアクセスしかない記憶項目の一覧
    - key, content preview, read/update counts, last access, days inactive を表示

**JavaScript 統合:**
- `loadMemoryUsageStats()` 関数追加
- `/api/memory-usage-stats/{persona}?max_access_count=3` からデータ取得
- Chart.js による動的グラフ生成
- Admin タブへの切り替え時に自動ロード

**変更ファイル:**
- `templates/dashboard.html`: Memory Usage Statistics カード UI、loadMemoryUsageStats() 関数、switchTab() 統合

#### Phase 9: Anniversary オペレーション完全統一（タグベース）

**anniversary オペレーションを memories テーブルに変更:**
- `handle_anniversary()` を全面的に書き換え
- persona_context.json への保存を廃止し、memories テーブルに 'anniversary' タグ付きで保存
- Add: save_memory_to_db() で anniversary タグ付きメモリを作成
- List: get_anniversaries() でタグベースの記念日を取得・表示
- Delete: delete_memory_from_db() でメモリキー指定削除

**タグベースの統一:**
- 'anniversary': 特別な記念日（初めて会った日、関係性のマイルストーン）
- 'milestone': 重要な達成や人生のイベント
- 'first_time': 初めての体験で覚えておきたいこと
- create オペレーション + context_tags でも記念日作成可能（推奨）

**不要データの削除:**
- `persona_context.json` の default_context から emotion_history フィールドを削除
- emotion_history は emotion_history テーブルに完全移行済み
- anniversaries は memories テーブルに完全移行済み

**ドキュメント更新:**
- `tools/unified_tools.py`: memory() docstring に anniversary タグの使用例を追加
- `.github/skills/memory-mcp/references/context_operations.md`: タグベースの推奨使用方法を追記
- `.github/skills/memory-mcp/references/memory_operations.md`: Anniversary/Milestone Creation セクション追加
- `.github/skills/memory-mcp/SKILL.md`: anniversary オペレーションの説明を更新

**変更ファイル:**
- `tools/handlers/context_handlers.py`: handle_anniversary() 完全書き換え（imports追加、タグベース実装）
- `core/persona_context.py`: default_context から emotion_history 削除、コメント追加
- `tools/unified_tools.py`: memory() docstring 拡張（anniversary tags, examples）
- `.github/skills/memory-mcp/**`: ドキュメント更新

---

### Added - 2025-12-11 (Phase 40-41: Timeline Visualization & Anniversary System)

#### Physical Sensations Timeline (Phase 40)

**ダッシュボード可視化:**
- Physical Sensations Timeline カード追加
- Chart.jsによる5指標の時系列グラフ（過去7日間）
  - fatigue（疲労度）- Red
  - warmth（温かさ）- Orange
  - arousal（覚醒度）- Pink
  - touch_response（触覚反応）- Purple
  - heart_rate_metaphor（心拍数メタファー）- Yellow
- physical_sensations_history テーブルからデータ取得
- `/api/physical-sensations-timeline/{persona}` REST API追加

#### Emotion Flow Timeline改善

**emotion_history テーブル統合:**
- `/api/emotion-timeline/{persona}` を emotion_history テーブル対応に改善
- Phase 40 の emotion_history テーブルから感情変化を取得
- memories テーブルへのフォールバック機能（下位互換性）
- テーブル存在チェックで自動判定

#### Anniversary Calendar System

**タグベース記念日管理:**
- `get_anniversaries()` 関数追加（core/memory_db.py）
- タグベース検出: `anniversary`, `milestone`, `first_time`
- MM-DD形式で月日ごとにグループ化
- `/api/anniversaries/{persona}` REST API追加

**ダッシュボード可視化:**
- Anniversary Calendar カード追加
- 月別カード表示（記念日がある月のみ）
- 日付バッジでクリック可能な UI
- モーダルで記念日の詳細表示（年、プレビュー、importance、emotion、tags）

**推奨タグ使い分け:**
- `anniversary`: 特別な記念日（初めて会った日、関係性のマイルストーン）
- `milestone`: 重要な達成や人生のイベント
- `first_time`: 初めての体験で覚えておきたいこと

**Files Changed:**
- `core/memory_db.py`: get_anniversaries() 関数追加
- `src/dashboard.py`: emotion_timeline改善, anniversaries/physical_sensations_timeline エンドポイント追加
- `templates/dashboard.html`: 3つの新規カードとJavaScript関数追加

### Added - 2025-12-11 (Phase 2-3: Pattern Learning & Situation Analysis)

#### 時間帯別パターン学習

**check_routines 詳細モード:**
- mode="detailed" または query="all" で時間帯別分析を表示
- 時間帯分類：朝(6-11)、昼(12-17)、夜(18-23)、深夜(0-5)
- 各時間帯のよくある行動、主な感情を分析
- 過去30日分のデータからパターンを抽出

**analyze_time_patterns 関数:**
- tools/analysis_tools.py に時間帯分析関数追加
- action_tag、emotionの頻度分析
- トップ10行動、トップ5感情を返却

#### 状況分析システム

**situation_context 操作:**
- 現在の状況を分析（時間、感情、環境、身体感覚）
- 似た状況の過去の記憶を検索
- **指示ではなく情報提供** - 判断はユーザーが行う
- 衣装や会話トーンの参考情報として利用可能

**設計哲学:**
- システムは情報を提供するだけ
- 選択や判断は利用者（Persona）が自分で行う
- 自然な振る舞いを阻害しない設計

### Added - 2025-12-10 (Phase 1: Enhanced Context Tracking)

#### 身体感覚記録システム

**physical_sensations フィールド:**
- fatigue: 疲労度 (0.0-1.0)
- warmth: 温かさ (0.0-1.0)
- arousal: 覚醒度 (0.0-1.0)
- touch_response: 触覚反応 ("normal", "sensitive", "resistant")
- heart_rate_metaphor: 心拍数メタファー ("calm", "elevated", "racing")

**sensation 操作:**
- 身体感覚の表示・更新
- get_context()に💫 Physical Sensationsセクション追加
- リアルタイムな身体状態の追跡

#### 感情変化追跡システム

**emotion_history フィールド:**
- 最新50件の感情変化を記録
- タイムスタンプ、感情タイプ、強度を保存

**emotion_flow 操作:**
- 感情変化の記録・履歴表示
- get_context()に📊 Recent Emotion Changesセクション追加
- 感情の流れを時系列で把握可能

### Added - 2025-12-10 (Smart Search & Anniversary Features)

#### スマート検索の汎用化

**曖昧クエリ自動検出:**
- 短いクエリ（5文字未満）または曖昧なフレーズを自動検出
- 日本語対応: "いつものあれ", "いつもの", "あれ", "例の件", "いつも通り"
- 英語対応: "that thing", "the usual", "you know", "usual thing", "same as always"
- 曖昧なクエリのみ時間・曜日コンテキストを自動拡張

**バイリンガルコンテキスト拡張:**
- 時間帯: 朝/morning, 昼/afternoon, 夕方/evening, 夜/night, 深夜/midnight
- 曜日: 平日/weekday, 週末/weekend

**約束事検索統合:**
- "約束" または "promise" を含むクエリに自動でpromiseタグ追加
- 約束関連の検索精度向上

#### 記念日機能

**anniversary操作:**
- 記念日の追加・削除・一覧表示
- MM-DD形式での日付管理
- 繰り返し設定（recurring: true/false）

**get_context()表示:**
- 🎉 TODAY! - 当日の記念日
- 📅 in X days - 7日以内の記念日
- 🔄 - 繰り返し記念日のマーク

### Removed - 2025-11-19 (Code Cleanup & Consolidation)

#### 重複機能の削除

コードベースの健全性向上のため、重複・非推奨機能を削除。

**削除項目:**

1. **アイドル式要約ワーカー廃止**:
   - `src/utils/summarization_worker.py` 削除
   - Phase 28.4 の機能をPhase 38 のスケジュール式に統合
   - 設定: `summarization.enabled` → `auto_summarization.enabled` に移行
   - スケジューラーをデフォルト有効化（`auto_summarization.enabled = true`）

2. **非推奨関数削除**:
   - `search_memory_rag()` 削除（`read_memory()` を使用）
   - DEPRECATED マーカーのあった後方互換関数を完全削除

**変更点:**

- バックグラウンドワーカー: 4つ→3つに整理
  1. Idle rebuilder (ベクトルストア再構築)
  2. Cleanup worker (重複検知・自動マージ)
  3. Auto-summarization scheduler (日次・週次要約) ← 統合後

**マイグレーションガイド:**

古い設定から新しい設定への移行:
```json
// 旧設定（Phase 28.4）
{
  "summarization": {
    "enabled": true,
    "idle_minutes": 30,
    "frequency_days": 1
  }
}

// 新設定（Phase 38）
{
  "auto_summarization": {
    "enabled": true,           // デフォルトで有効
    "schedule_daily": true,     // 日次要約
    "schedule_weekly": true,    // 週次要約
    "daily_hour": 3,           // 午前3時実行
    "weekly_day": 0            // 月曜実行
  }
}
```

---

### Added - 2025-11-19 (Phase 38: Auto-Summarization Scheduler & Priority Scoring)

#### 自動要約スケジューラー

バックグラウンドで日次・週次の自動要約を実行するスケジューラーを追加。メモリを定期的に圧縮してメタメモリとして保存。

**新機能:**

1. **自動要約スケジューラー**:
   - バックグラウンドワーカースレッドで定期実行
   - 日次要約: 設定した時刻（デフォルト3時）に実行
   - 週次要約: 設定した曜日（デフォルト月曜）に実行
   - 既存の要約ツール群を活用

2. **スケジューラー設定**:
   - `auto_summarization.enabled`: スケジューラー有効化（デフォルト: false）
   - `auto_summarization.schedule_daily`: 日次要約（デフォルト: true）
   - `auto_summarization.schedule_weekly`: 週次要約（デフォルト: true）
   - `auto_summarization.daily_hour`: 実行時刻（デフォルト: 3）
   - `auto_summarization.weekly_day`: 実行曜日（デフォルト: 0=月曜）
   - `auto_summarization.check_interval_seconds`: チェック間隔（デフォルト: 3600秒）

#### 優先度スコアリング

アクセス頻度を考慮した複合スコアリングシステムを実装。重要度・時間減衰・アクセス頻度で記憶に優先度を付与。

**新機能:**

1. **アクセストラッキング**:
   - DBスキーマに `access_count`, `last_accessed` カラム追加
   - `increment_access_count()`: アクセス時に自動カウント
   - 検索結果取得時に自動更新

2. **複合スコアリング**:
   - ベクトル類似度 + 重要度重み + 時間減衰重み + アクセス頻度
   - アクセス頻度: `log1p(access_count) / 10.0` で正規化（10%の重み）
   - 既存の importance_weight, recency_weight と統合

3. **自動マイグレーション**:
   - 既存DBに自動でカラム追加
   - `load_memory_from_db()` で透過的に処理

**設定追加:**

```json
{
  "auto_summarization": {
    "enabled": false,
    "schedule_daily": true,
    "schedule_weekly": true,
    "daily_hour": 3,
    "weekly_day": 0,
    "check_interval_seconds": 3600,
    "min_importance": 0.3
  }
}
```

**テスト:**
- `scripts/test_auto_summary.py`: 要約機能のユニットテスト（5テスト）
- `scripts/test_priority_scoring.py`: 優先度スコアリングのユニットテスト（4テスト）

---

### Added - 2025-11-19 (Phase 36: Enhanced Search & Auto-Cleanup)

#### Hybrid Search & Temporal Filtering

統合検索機能の大幅強化。セマンティック検索とキーワード検索を組み合わせたハイブリッド検索、自然言語での時間フィルタリングに対応。

**新機能:**

1. **ハイブリッド検索モード**:
   - セマンティック検索（70%）とキーワード検索（30%）を統合
   - 両方の利点を活用した高精度検索
   - `mode="hybrid"` で利用可能

2. **時間フィルタリング**:
   - 自然言語対応: 「今日」「昨日」「先週」「今週」「今月」「3日前」
   - 日付範囲指定: `date_range="2025-11-01,2025-11-15"`
   - semantic/hybrid/keywordモード全対応
   - `parse_date_query()` による柔軟な日時解析

3. **メタデータエンリッチメント**:
   - ベクトル埋め込みにメタデータを含める
   - 検索対象: tags, emotion, action_tag, environment, physical_state, mental_state, relationship_status
   - `_build_enriched_content()` ヘルパー関数で統一実装
   - 約120行のコード重複を削減

4. **検索モード統合**:
   - `read` operation廃止 → `search` に統合
   - デフォルトモード変更: `keyword` → `semantic`
   - 4モード対応: semantic, keyword, hybrid, related

**設定追加:**

```json
{
  "auto_cleanup": {
    "enabled": true,
    "idle_minutes": 30,
    "check_interval_seconds": 300,
    "duplicate_threshold": 0.90,
    "min_similarity_to_report": 0.85,
    "max_suggestions_per_run": 20
  }
}
```

**使用例:**

```python
# ハイブリッド検索
memory(operation="search", query="プロジェクト進捗", mode="hybrid")

# 時間フィルタリング
memory(operation="search", query="成果", mode="semantic", date_range="昨日")
memory(operation="search", query="", mode="keyword", date_range="先週")

# タグ + 時間フィルタ
memory(operation="search", query="", mode="keyword",
       search_tags=["technical_achievement"],
       date_range="今週")
```

**Files Changed:**
- `lib/backends/qdrant_backend.py`: Qdrant client.search() 互換性修正
- `tools/search_tools.py`: ハイブリッド検索実装、時間フィルタリング統合
- `tools/crud_tools.py`: read_memory() に date_range パラメータ追加
- `tools/unified_tools.py`: 'read' operation 廃止
- `src/utils/vector_utils.py`: _build_enriched_content() 抽出、コード重複削減
- `scripts/test_date_filter.py`: 時間フィルタリングテスト
- `scripts/test_enriched_search.py`: メタデータ検索精度テスト

**Performance:**
- ベクトル検索精度向上（メタデータ含有により）
- コードメンテナンス性向上（重複削減）
- テストカバレッジ拡充（時間フィルタ、エンリッチ検索）

---

### Changed - 2025-11-17 (Equipment Tools Enhancement)

#### Equipment System Improvements

Enhanced equipment management with more flexible unequip and equip operations.

**Changes:**
1. **`unequip_item()` enhancement**:
   - Now accepts single slot or list of slots
   - Can unequip multiple items at once
   - Example: `unequip_item(["top", "foot"])` or `unequip_item("weapon")`

2. **`equip_item()` behavior change**:
   - No longer automatically unequips all equipment
   - Only equips specified slots
   - More granular control over equipment changes
   - Example: `equip_item({"top": "White Dress"})` keeps other slots equipped

3. **Type hints consistency**:
   - Unified to use `Optional[...]`, `List[...]`, `Dict[...]` style
   - Improved code readability and IDE support

**Migration:**
- Old: `equip_item({...})` auto-unequipped everything → Now: only affects specified slots
- To unequip all: Use `item(operation="equip", equipment={})` in unified tool

**Files Changed:**
- `tools/equipment_tools.py`: Updated `equip_item()` and `unequip_item()` signatures
- `core/equipment_db.py`: Improved type hints

### Changed - 2025-11-16 (Phase 35: Tool Consolidation)

#### Tool Count Reduction (75% reduction: 12 → 3 tools)

Consolidated individual memory and item operations into unified tools to significantly reduce context consumption.

**Before (12 tools):**
- Memory operations: `create_memory`, `update_memory`, `search_memory`, `delete_memory`
- Item operations: `add_to_inventory`, `remove_from_inventory`, `equip_item`, `update_item`, `search_inventory`, `get_equipment_history`, `analyze_item`
- Context: `get_context`

**After (3 tools):**
- **`memory`**: Unified memory interface (operations: create, read, update, delete, search, stats)
- **`item`**: Unified item interface (operations: add, remove, equip, update, search, history, memories, stats)
- **`get_context`**: Unchanged

**Benefits:**
- 75% reduction in tool count (12 → 3)
- Estimated 70-80% reduction in context size
- Simplified API with consistent operation-based interface
- All existing functionality preserved

**Migration Examples:**

```python
# Old way
create_memory(content="User likes strawberry", emotion_type="joy")
search_inventory(category="weapon")

# New way (unified interface)
memory(operation="create", content="User likes strawberry", emotion_type="joy")
item(operation="search", category="weapon")
```

**Files Changed:**
- Added: `tools/unified_tools.py` - Unified tool implementation
- Modified: `tools_memory.py` - Updated tool registration
- Modified: `tools/item_memory_tools.py` - Deprecated `analyze_item`

**Backward Compatibility:**
- All operations available through unified interface
- Internal implementation reuses existing functions
- No breaking changes to functionality

---

## Previous Changes

See git history for earlier changes.
