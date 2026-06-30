# SPEC — Nousツール レビュー対策 v2 (2026-06-30, oracle review反映)

## 変更履歴
- v1: 初版
- v2: oracle review反映 → R04順序逆転、R07/R09スコープ縮小、欠落項目追加

## 背景
全20ツールの操作テストと競合調査を経て問題特定。oracleにより「死んでいるコードに命を吹き込むことを優先せよ」との指摘。

## 要件一覧

### R01: リランカー実装統合 [P0] ⚠️ 最高リスク
- **現状**: `RerankerModel` 完全実装済みだがインスタンス化も呼出もゼロ
- **やること**:
  - `AppContext` で `RerankerModel` インスタンス化
  - `SearchEngine._hybrid_search()` の RRF 後に `rerank()` 呼出
  - **重要**: 初回検索の同期ブロッキング対策（モデルプリロード）
  - **重要**: SearchEngineへのreranker注入パターン（ホットリロード整合性）
  - `contents` dict のバッチ取得（memory_repo.get_by_keys()）
  - ホットリロードコールバック修正（`_reranker is None` ガード外す）
- **モデル**: `hotchpotch/japanese-reranker-xsmall-v2`

### R02: エラーメッセージの英語統一 [P0]
- **現状**: 日本語と英語が混在
- **やること**: 全ツールのエラーメッセージを英語に統一

### R03: read_pdf パス解決バグ修正 [P0]
- **現状**: sandbox内・ホスト内どちらのファイルも `ファイルが見つかりません`
- **やること**: パス解決ロジックの調査と修正

### R04: 時間経過認識・感情トラッキング強化 [P1 - 最重要]

**oracle指摘**: 計算層（FSRS v6, 減衰）は正確。表現層（矢印表示）は機能的だが機械的。体験層（ペルソナが「時間が経った」と実感しているように感じさせる）が不在。

**修正後の順序**: trigger_key活用を最優先に（数行変更で土台ができる）

- **(a) emotion trigger_key 即時活用** [最優先]:
  - `update_emotion()` 呼出箇所に `trigger_memory_key` を渡す（現在全箇所 None）
  - `memory_llm.py:377`, `builtin.py:74` はコンテキストを持っているので可能
  - 感情トレンド表示に因果関係を追加（「〇〇の記憶がトリガー → 怒り」）

- **(b) 感情減衰の通知強化**:
  - `get_context()` 時に「減衰前の感情 → 減衰後の感情」を明示表示
  - 例: `joy(0.72)→neutral —— 時間経過により自然に落ち着きました`

- **(c) 感情持続性の概念**:
  - 半減期を動的に: `effective_half_life = base_half_life * intensity`
  - 強い感情は長く持続、弱い感情は早く消える

- **(d) 感情半減期の設定化**:
  - `ForgettingConfig` に `emotion_half_life_hours: float = 24.0` 追加
  - `emotion_decay.py` のハードコードを設定参照に変更

- **(e) TIME GAP コメントの体験層化**:
  - テンプレートベースで自然言語生成（LLM不要）
  - 経過時間 + 身体状態の変化 + 直近会話トピック + 現在の感情を自然に記述
  - 30分未満でも「直前の感情状態を維持」表示

- **(f) body_state_history** [P2に降格、優先度低]:
  - body_state_history テーブル新設
  - 履歴記録 + 取得メソッド追加

### R05: スキルプリインストール [P1]
- `verification-before-completion`, `systematic-debugging`, `test-driven-development` を初期登録

### R06: セッション自動記憶抽出（autoCapture）[P1]
- `PostProcessStep` でセッション内容から重要情報抽出→`memory_create`

### R07: 外部ストレージ基盤整備 [P3] ← P2から降格
- **oracle判定**: YAGNI。実際の需要が顕在化するまでは過剰投資
- Repositoryインターフェース抽象化のみ（本格実装は需要発生後）

### R08: ドキュメント拡充 [P2]
- READMEツール使用例、セットアップ手順、トラブルシューティング

### R09: goal_manage 重要度ラベル表示 [P3] ← スコープ縮小
- **oracle判定**: カテゴリ分類はタグでカバー可能。重要度ラベル表示のみに縮小
- `importance >= 0.9 → critical`, `>= 0.7 → high`, `>= 0.4 → normal`, `< 0.4 → low`

## 範囲外
- R07の本格実装（PostgreSQL/Supabase対応）
- R09のカテゴリ分類（タグ運用で代替）
- ニューラルリランク導入
- 7因子スコアリング
- 感情考慮リランキング（R01-R04の相互作用は将来課題）

## 検証基準
- 全既存テストが通過すること
- 新規追加コードにはテストを付与
- ruff check 0 errors
- GitHub Actions パス
