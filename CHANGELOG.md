# Changelog

All notable changes to Memory-MCP will be documented in this file.

## [Unreleased]

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
