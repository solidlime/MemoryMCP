# HANDOFF - 2026-06-27 11:04

## 使用ツール
Claude Code (via opencode)

## 現在のタスクと進捗

### ✅ T020 完了 (D-3 4-tier lifecycle basic)
| # | タスク | 状態 |
|---|--------|------|
| T020 | 4-tier lifecycle基本 (active/tombstoned) | ✅ |

### T020 実装内容詳細
1. **DB migration v028**: `lifecycle_status TEXT DEFAULT 'active'` カラム追加
2. **Memory entity**: `lifecycle_status: str = "active"` フィールド追加
3. **SQLiteMemoryRepository**: 
   - save/update に lifecycle_status 対応
   - 全SELECTクエリに `WHERE lifecycle_status != 'tombstoned'` フィルタ
   - `tombstone()` メソッド追加（論理削除）
4. **MemoryService.delete_memory()**: 物理削除→論理削除(tombstone)に変更
5. **Qdrant adapter**: upsert時 payload に lifecycle_status 含める
6. **SearchQuery**: `lifecycle_status` パラメータ追加（デフォルト "active"）
7. **変更ファイル**: 13ファイル (new: 1)
8. **テスト**: 1313 passed, 7 skipped, 0 failed

### ⏳ 残タスク (低優先)
- T019: D-2 Agent Skills標準移行 (SKILL.md形式, Progressive Disclosure)
- T021: D-4 検索ハイブリッド強化 (FTS5+RRF+KNN)
- 将来フェーズ: 30日自動物理削除, as_ofパラメータ, LRU shield, Superseding

## T020 設計判断
- `"active"` tag は Goal/Promise status 専用として維持。lifecycle_status と独立管理
- Goal/Promise の `"active" in tags` チェックは変更なし（異なる意味論）
- tombstoned メモリは `find_by_key()` で取得可能（リカバリ用）
- Qdrant ポイントは tombstone 時に物理削除（検索不能に）
- sqlite3.Row は `.get()` 未対応 → `row["col"] if "col" in row.keys()` で代替

## 注意点
- `sqlite3.Row.get()` is NOT available even in Python 3.14.4
- ベンチマークテストは `pytest-benchmark` 未インストールにつきスキップ（既存）
- 論理削除後の物理削除（30日経過tombstoned）は未実装
