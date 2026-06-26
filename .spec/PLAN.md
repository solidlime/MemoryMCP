# PLAN: ツール対策 + UI/UX改善 2026-06-27 (v7 — designerレビュー反映)

## 前提
- MCP後方互換 **不要** — `promise_manage` は全層から完全削除
- chat.js の `/promise` スラッシュコマンド・`fulfillPromise()` 関数も削除
- **全タスクを妥協なく完了させる**。"低優先"カテゴリなし。全項目が必須対応

## 背景
1. WebUIチャットLLM用14ツールの忖度なし評価（類似プロジェクト比較）
2. テスト体系調査（memory_llm.py 他4ファイルテスト0件）
3. @oracle による UI/UX レビュー（17件）
4. @designer による UI/UX デザインレビュー（+16件）

## 全体方針
- 🔴 クリティカルパス上（後方依存あり）、🟡 必須（並行可・後続可）。全完遂
- #0 を #1 の前提条件に。テスト0件での大規模改修は拒否
- #1 に #13 を統合。同一ファイル2回改修を回避
- UI/UX改善はツール改善と独立並行
- 各フェーズ完了時に全テストパス + ruff パス確認

## クリティカルパス
```
#0 (memory_llmテスト)
  │
  ├──→ #1 (promise統合+goal list)
  │         │
  │         ├──→ #2 (update安全化) ──→ #3 (searchフィルタ)
  │         │
  │         ├──→ #15 (builtinテスト) ──→ #4 (browser desc) / #5 (sandbox desc) / #6 (制限値可視化)
  │         │
  │         └──→ #9 (desc短文化) ← #1〜#6 完了後
  │
  └──→ #16 (definitionsテスト) ← #1前後どちらでも可

#18 (CSS断片化解消) ──→ #22 (レスポンシブ)
#19 (空状態+CTA)
#20 (コマンド可視化+ショートカット修正)
#21 (chat.js defer)               ← UI/UX全独立並行
#23 (軽微UI修正まとめ)

#7 (重複検出) #8 (session_id) #10 (context_update) #11 (sandbox append)
#12 (search確認) #14 (context_recall削除) #17 (テスト保守性) ← 独立小タスク群
```

## 🔴 クリティカルパス上（後方依存あり）

### #0. memory_llm.py テスト新規作成（#1 前提条件）
### #1. promise_manage 完全削除 + goal_manage 統合 + "list" 追加
### #2. memory_update 安全化
### #3. memory_search フィルタ追加
### #4. browser description 強化
### #5. sandbox_files required 関連改善
### #6. 制限値のツール定義可視化
### #15. builtin.py ハンドラのパラメータ検証テスト
### #16. definitions.py スキーマ整合性テスト

（上記、詳細は v6 と同一）

## 🟡 必須タスク（並行可・後続可）

### ツール機能改善（#7〜#14）

#### #7. memory_create 重複検出
既に builtin.py L128-146 に実装あり。確認＋テスト追加。chat.js の重複通知UI対応。

#### #8. execute_code session_id 対応
#### #9. description 短文化（全13ツール）
#### #10. context_update 自動化
#### #11. sandbox_files append/edit 追加
#### #12. search パラメータ確認（既存実装確認後クローズ）
#### #14. README context_recall 記述削除

### UI/UX改善（#18〜#23）

#### #18. インラインCSS除去 + CSS変数化 + テーマ破綻修正
**問題**: chat.py/memories.py/persona.py/base.py + JS ファイルに100箇所以上のインラインスタイル。特に `rgba(255,255,255,0.05)` 等のハードコード背景色がライトテーマで破綻。
**designer追加検出**:
- chat.css:591 `var(--border-color)` が未定義 → `var(--glass-border)` に修正
- persona.py:45 `var(--accent)` が未定義 → `var(--accent-purple)` に修正
- chat.py:91 中止ボタンの100文字超インラインスタイル → CSSクラス化
- memories.py:199 ➕ HTMLエンティティ → Lucideアイコンに統一
- base.css L530-540 `.mobile-toggle` クラスがHTMLに実体なし（dead code）→ 削除

**対策**:
- 18.1: 全インラインCSSを base.css/chat.css に移行しCSS変数化
- 18.2: ハードコード背景色を var(--glass-bg) 系変数に全置換
- 18.3: base.css 重複定義除去（scrollbar, .glass transition）
- 18.4: .chat-help-tooltip 重複統合
- 18.5: 未定義CSS変数（--border-color, --accent）を正しい変数名に修正
- 18.6: .form-textarea ライトテーマ背景をCSS変数準拠に
- 18.7: 中止ボタンのインラインスタイルCSSクラス化
- 18.8: ➕ HTMLエンティティ → Lucideアイコンに
- 18.9: .mobile-toggle dead code 削除
- 18.10: ダーク/ライト両テーマで全タブ手動確認

#### #19. 空状態（Empty State）+ CTA表示
**問題**: memories/activity/timelineタブのデータ0件時に白紙。Personaゼロ時にCTA不在。
**designer追加検出**:
- チャットウェルカム限定すぎ。「APIキーとプロバイダーを設定してください」→ 設定パネルへの導線なし
- チャット履歴復元中に skeleton なし（chat.js restoreChatHistory）
- Settings情報過多（50+フィールド、9アコーディオン）。初回ユーザーに圧倒的

**対策**:
- 19.1: memories/js/activity/js/timeline の空状態表示
- 19.2: Personaゼロ時に「Personasタブで作成してください」CTA追加
- 19.3: チャットウェルカムに設定パネル開き方の導線追加
- 19.4: チャット履歴復元中の skeleton 追加

#### #20. スラッシュコマンド・ショートカット可視化
**designer追加検出**:
- **キーボードショートカット配列が11タブ中10個しかない**（activity 欠落）— base.js:475
- タブ定義がナビ生成・ショートカット・loadTab() の3箇所に分散し single source of truth がない

**対策**:
- 20.1: chat-welcome にスラッシュコマンド一覧表示
- 20.2: `/help` スラッシュコマンド追加
- 20.3: キーボードショートカット配列に activity 追加、タブ定義を single source of truth に統合
- 20.4: `/` 入力時のコマンド候補ポップアップ（簡易版）

#### #21. chat.js defer化
base.py:28 の `<script>` タグに `defer` 属性追加。

#### #22. レスポンシブ改善
**designer追加検出**:
- chat.css:339-351 モバイル設定パネルで `width:0` + `transform: translateX(100%)` が競合
- chat.css チャット高さ計算 `calc(100vh - 200px)` がマジックナンバー。ヘッダー折り返し時に破綻
- chat.css:34 チャットバブル `max-width:85%` がワイドスクリーンで過大

**対策**:
- 22.1: 900-1100px帯ブレイクポイント追加
- 22.2: タブバー右端スクロールインジケーター追加
- 22.3: モバイルトースト中央寄せ
- 22.4: モバイル設定パネル `width:0` 削除、`transform` のみで制御
- 22.5: チャット高さ計算をCSS変数化（`--header-height`, `--tabbar-height`）
- 22.6: チャットバブル max-width に `min(85%, 720px)` 制限追加

#### #23. 軽微UI修正まとめ
**designer追加検出**:
- `confirm()` / `alert()` ネイティブダイアログがガラスモーフィズムから乖離 → カスタム確認モーダル化
- モーダルにフォーカストラッピングなし（アクセシビリティ）
- `fadeInUp` アニメーションが毎タブ切替で再発火（初回のみに）
- `animateCount` 4並列 RAF が Overview 初回ロード時にレイアウトシフト → batch化
- Ctrl+F検索のセレクタが英語 placeholder に依存 → 属性ベースに変更
- SSE再接続がバックオフなし無限ループ → exponential backoff

**対策**:
- 23.1: バージョン文字列を `__version__` から動的注入
- 23.2: Emotion選択 `<option><i>` → テキストのみに修正
- 23.3: モーダル閉鎖アニメーションのレースコンディション修正
- 23.4: タブ切替時のDOM状態保持
- 23.5: Lucideアイコン二重初期化整理
- 23.6: confirm/alert → カスタム glassmorphism 確認モーダル
- 23.7: モーダルにフォーカストラッピング追加（Tab/Escape）
- 23.8: fadeInUp を初回のみに制限
- 23.9: animateCount RAF を batch化
- 23.10: Ctrl+F セレクタを `[data-search]` 属性ベースに変更
- 23.11: SSE再接続に exponential backoff（5s→10s→20s→60s上限）

### テスト改善

#### #17. テスト保守性改善
mock_app_context 集約、patch ボイラープレートヘルパー化、await 置換、アサーション具体化。

## スコープ外（判断済み）
- 新ツールの追加
- 外部MCPクライアント統合改善
- _tools_sandbox.py 大規模リファクタリング
- CHANGELOG.md 履歴修正
- chat.js のテストフレームワーク導入
- チャット設定パネルの情報量削減（別案件。現状の機能性を維持しつつ別途UX設計必要）
