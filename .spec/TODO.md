# TODO - コードベース健全化リファクタリング（2026-06-20〜21）

## P0: 巨大ファイル分割 🔴

### P0-1: tools.py 分割
- [x] P0-1a: `_tools_memory.py` — memory_create/read/update/delete/search
- [x] P0-1b: `_tools_persona.py` — get_context, update_context
- [x] P0-1c: `_tools_item.py` — item_add/remove/update/search/equip/unequip/history
- [x] P0-1d: `_tools_goal.py` — goal_manage, promise_manage
- [x] P0-1e: `_tools_sandbox.py` — sandbox, sandbox_files
- [x] P0-1f: `_tools_skill.py` — invoke_skill
- [x] P0-1g: `tools.py` をTOOL_DISPATCH + 再エクスポートに縮小

### P0-2: chat.py 軽量クリーンアップ
- [x] P0-2a: CSS/JSを静的ファイルに分離 (chat.py 2714→417行)
- [x] P0-2b: W293空白行スペース修正 → ruff --fix で全自動修正

## P1: 重複コード共通化 🟠
- [x] P1-1〜P1-3: 全完了

## P2: 軽量クリーンアップ 🟡
- [x] P2-1〜P2-3: 全完了

## P3: ドキュメント刷新 🟢
- [x] P3-1〜P3-7: 全完了

## ブラウザテスト 🧪
- [x] LLM Chat (herta / OpenRouter gemma-4-31b-it) 動作確認
- [x] MCP tools (memory_create, sandbox execute) 動作確認
- [x] ファイルアップロード動作確認
- [x] sandbox グローバル無効化問題を特定 (MEMORY_MCP_SANDBOX__ENABLED=false)

## 最終確認 🧪
- [x] ruff check → 0 errors
- [x] pytest → 1085 pass, 1 fail (test_settings 既存バグ)
- [x] git commit + push (SSH remote)
