# TODO - コードベース健全化リファクタリング（2026-06-20）

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
- [ ] P0-2a: 死にコード・重複CSS/JS削除（後回し・要デザイナー）
- [x] P0-2b: W293空白行スペース修正 → ruff --fix で全自動修正

## P1: 重複コード共通化 🟠

- [x] P1-1: `normalize_importance()` 抽出 → 全呼出箇所置換（4ファイル）
- [ ] P1-2: `emotion`/`emotion_type` フィールド名統一（後回し・複雑）
- [x] P1-3: `_VALID_EMOTIONS` を domain 層へ移動

## P2: 軽量クリーンアップ 🟡

- [x] P2-1: `except: pass` → `logger.debug`（token_counter, prepare.py ×2, sandbox SIM105）
- [x] P2-2: DEPRECATEDエンドポイント削除（3箇所 + テスト修正）
- [x] P2-3: ruff全件修正（E402 use_cases.py, W293 auto-fix, SIM105 sandbox）

## P3: ドキュメント刷新 🟢

- [ ] P3-1: SPEC.md 棚卸し（古い計画を details 折りたたみ）
- [ ] P3-2: PLAN.md 更新完了
- [x] P3-3: TODO.md（本ファイル）
- [ ] P3-4: KNOWLEDGE.md 更新
- [ ] P3-5: MEMORY.md アーカイブ＋再生成
- [ ] P3-6: HANDOFF.md 生成
- [ ] P3-7: README.md 刷新

## 後回しタスク 📋

- [ ] web_search ブラウザ動作テスト（WSL Chromeライブラリ不足）
- [ ] P0-2a: chat.py 死にコード・CSS/JS分離（要デザイナー）
- [ ] P1-2: emotion/emotion_type フィールド名統一

## 最終確認 🧪

- [x] T-final: ruff check → 0 errors
- [x] T-final: pytest → 739 pass, 1 fail (test_settings 既存バグ)
- [x] T-final: git commit + push
