# TODO: ツール対策 + UI/UX改善 2026-06-27 (v7 — 完了)

## 🔴 クリティカルパス（前提・後方依存あり）

### 【#0】 memory_llm.py テスト新規作成（#1 の前提）
- [x] 0.1-0.5 テスト作成 + 確認 — 44 tests ✅

### 【#1】 promise_manage 完全削除 + goal_manage 統合 + "list" 追加
- [x] 1.1-1.27 全レイヤー削除＋scope移行＋テスト書き換え — 9ファイル変更、0 regression ✅

### 【#2】 memory_update 安全化
- [x] 2.1-2.5 実装＋テスト — 両層に7種バリデーション追加 ✅

### 【#15】 builtin.py ハンドラのパラメータ検証テスト
- [x] 15.1-15.5 テスト作成 — 55 tests ✅

### 【#16】 definitions.py スキーマ整合性テスト
- [x] 16.1-16.5 テスト作成 — 8 tests ✅

### 【#4】 browser description 強化
- [x] 4.1-4.3 実装＋確認 — #4+#5+#6 まとめて ✅

### 【#5】 sandbox_files required 関連改善
- [x] 5.1-5.2 実装＋確認 — #4+#5+#6 まとめて ✅

### 【#6】 制限値のツール定義可視化
- [x] 6.1-6.4 実装＋確認 — #4+#5+#6 まとめて ✅

### 【#3】 memory_search フィルタ追加
- [x] 3.1-3.6 実装＋テスト — フィルタパラメータ追加 ✅

## 🟡 必須タスク（並行・後続可）

### ツール機能改善

### 【#7】 memory_create 重複検出
- [x] 7.1-7.3 確認＋テスト — MCP層移植 + chat.js UI ✅

### 【#8】 execute_code session_id 対応
- [x] 8.1-8.5 実装＋テスト — MCP層に追加 ✅

### 【#9】 description 短文化（全13ツール）
- [x] 9.1-9.3 実装＋確認 — 全13ツール短縮 (max 216→43字) ✅

### 【#10】 context_update 自動化
- [x] 10.1-10.3 実装＋確認 — context_note自動反映配線 ✅

### 【#11】 sandbox_files append/edit 追加
- [x] 11.1-11.4 実装＋テスト — description修正 + テスト ✅

### 【#12】 search パラメータ確認
- [x] 12.1-12.3 確認→クローズ — 実装済み確認 ✅

### 【#14】 README context_recall 記述削除
- [x] 14.1-14.2 削除 — 2行削除 ✅

### UI/UX改善

### 【#18】 インラインCSS除去 + CSS変数化 + テーマ破綻修正
- [x] 18.1-18.12 全サブタスク — CSS変数化、重複除去、dead code削除 ✅

### 【#19】 空状態（Empty State）+ CTA表示
- [x] 19.1-19.6 全サブタスク — memories/activity/timeline/chat ✅

### 【#20】 スラッシュコマンド・ショートカット可視化
- [x] 20.1-20.4 全サブタスク — /help追加、候補ポップアップ ✅

### 【#21】 chat.js defer化
- [x] 21.1 defer属性追加 ✅

### 【#22】 レスポンシブ改善
- [x] 22.1-22.6 全サブタスク — ブレイクポイント追加、CSS変数化 ✅

### 【#23】 軽微UI修正まとめ
- [x] 23.1-23.11 全サブタスク — モーダル、SSEバックオフ、RAFバッチ化 ✅

### テスト改善

### 【#17】 テスト保守性改善
- [x] 17.1-17.5 フィクスチャ集約＋ヘルパー化＋await置換＋アサーション具体化 ✅

### ドッグフーディング
- [x] サーバー起動テスト (port 26262)
- [x] MCP API 全ツール確認 (promise_manage完全消滅確認)
- [x] memory_update バリデーション動作確認
- [x] memory_create + memory_search 動作確認
- [x] goal_manage scope/list 動作確認
- [x] goal_manage scope=self フィルタバグ修正
- [x] @designer 視認レビュー → 6件指摘 → 全修正

## 最終ステータス
- **1134 passed, 7 skipped, 0 failed**
- **ruff: All checks passed**
- **変更ファイル: 30+ ファイル**
- **新規テスト: ~160 tests**
