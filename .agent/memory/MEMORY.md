# MEMORY

## プロジェクト概要

## 学習した知識・教訓

### get_context 出力調整（2026-03-23）
- `memory_preview_length` デフォルトは `src/utils/config_utils.py` の `DEFAULT_CONFIG` で管理（100→200に変更済み）
- 記憶タイムスタンプはUTC保存 → `format_datetime_for_display()` でJST変換が必要（修正済み）
- Memory Blocks（block_write/block_read/block_list/block_delete）は廃止済み。DBレイヤー(`memory_blocks_db.py`)は保持
- Promises & Goals は `context_tags=['promise'/'goal']` のタグベース実装
- get_context のメイン実装は `tools/context_tools.py`、オペレーション処理は `tools/handlers/context_handlers.py`

