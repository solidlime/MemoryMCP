# HANDOFF - 2026-05-16

## 使用ツール
OpenCode (deepseek-v4-pro)

## 現在のタスクと進捗
- [x] MCPツール flat化リファクタリング Phase 1-3 完了（13 commits）
- [x] get_context デフォルト軽量化（~600-800 tokens, -90%）
- [x] context_note 導入（update_context → get_context 自動復元）
- [x] ツール定義を自己説明的に改善（LLMが自然に使う設計）
- [x] テスト: 821 passed, 7 skipped
- [x] **本番デプロイ済み（NAS herta-memory）**

## 次のセッションで最初にやること

### 🔬 本番動作テスト
1. **`get_context()` を呼ぶ** → 軽量出力を確認
   - `📌 Now:` 行に context_note が表示されるか
   - Recent + Current context が表示されるか
   - Speech Style が引き継がれているか

2. **`update_context(context_note="...")` を呼ぶ**
   - 感情更新と同時に context_note を設定
   - 再度 get_context で反映確認

3. **新 flat ツール全般の動作確認**
   - `memory_search(query="...")` 
   - `goal_manage(operation="create", ...)` / `promise_manage`
   - `memory_stats()`, `memory_create(...)`
   - `sandbox_files(operation="list")` / `sandbox(code="...")`

4. **会話継続テスト**
   - `context_note` が別セッションで復元されるか
   - `Current context` タグ合成が適切か

### 🛠 改善候補（テスト結果を見て判断）
- `get_context` の `Current context` タグ合成の精度
- `memory_search` のデフォルト importance_weight/recency_weight 調整
- past commitments が多すぎる場合の自動アーカイブ

## 試したこと・結果
- ✅ MCPツール 6 god-tool → 20 flat単一目的ツールに再編
- ✅ builtin.py if/elif チェーン廃止 → dispatch dict 化
- ✅ コア関数 str→dict 化（共有4関数）
- ✅ get_context デフォルト軽量: 感情・状態・装備・目標・約束・直近記憶・コンテキスト合成
- ✅ 全ユニットテスト 821 passed

## 注意点
- NAS 本番環境は `docker-compose up -d --build` でデプロイ済み
- `get_context` はデフォルトで軽量モード。全量が必要なら `mode="full"`
- `update_context` の context_note は 1行50字以内推奨
- `memory_search` の旧名 `search_memory` は削除済み
- `goal_create/achieve/cancel` → `goal_manage(operation=...)` に統一
- `sandbox_image` 削除 → `sandbox_files(operation="read")` で画像読取
