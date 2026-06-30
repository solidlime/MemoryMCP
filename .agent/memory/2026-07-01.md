# MEMORY

## プロジェクト概要
Nous: 日本語特化の永続記憶 MCP サーバー。SQLite + Qdrant + Ebbinghaus 忘却曲線。WebUIダッシュボード付き。
3レイヤー構造（L1:MCP拡張, L2:EventBus基盤, L3:OpenCode Plugin）。

## 学習した知識・教訓

### sandbox_context JSON化責務をラッパー層に統一（2026-06-29）
- `_tool_sandbox_context()` の戻り値を `str`（自前json.dumps）→ `dict` に変更
- MCPラッパー `sandbox_context()` 側で `json.dumps(r, ensure_ascii=False)` するように統一
- `sandbox_files` と同じパターン（core→dict, wrapper→json.dumps）に揃えた
- sandbox無効時・サービス不可時のスケルトン戻り値（pip_packages=[]含むdict）は維持

### sandbox_context pip_packages + auto_emotion（2026-06-29）
- `_tool_sandbox_context()` は常にJSONスケルトンを返す設計。sandbox無効時も空pip_packages含むdictを返し、エラー文字列を返さない
- `session.get_context()` は既に pip3 list --user --format=json をパースして pip_packages を返す（service.py L453-468）
- `_tool_memory_create()` の auto_emotion フラグ: 現状常にTrue。将来 explicit emotion 指定追加時は False 分岐

### item_* 7ツール → item 1ツール統合（2026-06-29）
- `_tool_item(operation, ...)` 統合関数: operation="add/remove/equip/unequip/update/search/history" で分岐
- 旧7ツールは完全削除。内部関数は維持し `_tool_item()` が呼出
- デザインパターン: `sandbox_files(operation=...)` と同一設計

### 4-tier lifecycle 論理削除（2026-06-27）
- `lifecycle_status TEXT DEFAULT 'active'` カラム追加 (v028)
- `memory_delete` は論理削除 (tombstone)。Qdrantポイントは物理削除
- 全SELECTに `WHERE lifecycle_status != 'tombstoned'` フィルタ
- `find_by_key()` は tombstoned も取得可能（リカバリ用）
- InMemory test repos にも `tombstone()` 追加必須

### ツール設計の統一パターン（継続的）
- MCPツール設計: core関数はdict/構造化データを返し、MCPラッパーでjson.dumpsする
- sandbox_files, sandbox_context がこのパターン準拠済み
- sandbox_execute, sandbox_reset は文字列戻り値（exec結果そのまま）で別扱い

### テスト自動化ルール
- sandboxテスト: `registered_tools` fixtureでMCPラッパー関数を呼び、戻り値は `json.loads()` でパースして検証
- テストは MCPラッパー経由で呼ぶ（コア関数直呼びではない）

### プロジェクトの現在の状態
- 全ユニットテスト通過: 1210 passed, 7 skipped
- pytest-benchmark 未インストール（7 skipped の原因）
- ruff check 0 errors 維持
