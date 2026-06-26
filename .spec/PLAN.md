# PLAN: ツール改善 2026-06-27

## 背景
WebUIチャットLLMツール（14個）の忖度なし評価で10の問題点を検出。
類似プロジェクト（Mem0, mnemex, LangGraph, Cline, Claude Code, OpenAI）と比較し、
ツール設計の品質を業界トップレベルに引き上げる。

## 全体方針
- 4フェーズに分割（リスク×効果マトリクスに基づく）
- 各フェーズ完了時に全テストパス + ruff パス確認
- description の短文化が全フェーズの基盤（LLMのツール選択精度に直結）

## フェーズA: 低リスク・高効果（即効性あり）

### A1. description 短文化（全14ツール）
- Claude Code 式「いつ使うか1行 + 必須引数」に統一
- `definitions.py` の全ツール定義を書き換え
- 現状 3〜5行 → 1〜2行に

### A2. context_recall 削除
- `memory_search` に tags パラメータがあるため機能的に重複
- definitions.py / builtin.py / _BUILTIN_DISPATCH から削除
- ツール数 14→13

### A3. search パラメータ追加
- `num_results` (int, default=10, max=50)
- `language` (str, optional)

### A4. goal/promise description 差別化
- goal: 目標の作成・達成・キャンセル
- promise: 約束の作成・履行・キャンセル
- 使い分けが明確になるように description を差別化

## フェーズB: 中リスク・高効果（要テスト）

### B1. context_update 自動化
- `memory_create` 内で context スナップショットを内部実行
- 「memory_create の前に context_update を呼べ」という順序制約を撤廃
- `context_update` ツールは明示的な状態変更用に残す（オプション化）

### B2. sandbox_files の append/Edit 操作追加
- `operation` に `append`（追記）と `edit`（行指定置換）を追加
- Edit: start_line, end_line, new_content パラメータ
- Claude Code の Write（全体）vs Edit（部分）を参考

## フェーズC: 高リスク・高効果（要設計）

### C1. memory_create の重複検出
- 作成前に internal で既存記憶と類似度比較
- セマンティック類似度 > 0.85 なら更新（重複防止）
- Mem0 の単一パス ADD-only extraction を参考

### C2. execute_code の session_id 対応
- `session_id` パラメータ追加 → 同一 sandbox で状態維持
- Jupyter 的セル実行を可能に
- TTL ベースの自動クリーンアップ（デフォルト 300s）

## フェーズD: 軽微・任意

### D1. invoke_skill の list_skills 追加
- LLM が利用可能なスキル一覧を取得可能に

### D2. browser ツール引数整理
- action に応じたサブスキーマ化は見送り
- description 改善で対応（どの action でどの引数が必要か明記）

## スコープ外
- sections/ HTML外出し（完了）
- カバレッジ改善（別案件）
- 新ツール追加（既存品質改善が先）
