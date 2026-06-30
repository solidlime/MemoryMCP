# TODO — Nousツール レビュー対策 v2 (oracle review反映)

## Phase 0: クリティカルフィックス (P0) — 並列実行可

### T01: リランカー統合 🔴 ⚠️ 最高リスク ✅ DONE
- [x] **T01a**: `AppContext.__init__()` で `RerankerModel` をインスタンス化（`nous/application/use_cases.py`）
- [x] **T01b**: SearchEngine が `_reranker` 参照を持つよう修正（`__init__`パラメータ＋`_hybrid_search`での利用）
- [x] **T01c**: `SearchEngine._hybrid_search()` のRRF+dedup後に `self._reranker.rerank()` 呼出追加（`nous/domain/search/engine.py`）
- [ ] ~~**T01d**: `contents` dictをバッチ取得する `memory_repo.get_by_keys()` 呼出追加~~ — 不要: 結果はSearchResultとして既にメモリ上にある
- [x] **T01e**: モデルプリロード機構（daemon thread + try/except、同期ブロッキング回避）
- [x] **T01f**: ホットリロードコールバック修正（SearchEngineリセット追加、`_reranker`ガードは動作する）
- [x] **T01g**: 統合テスト追加（`tests/unit/test_reranker_integration.py` — 12 tests）
- **依存**: なし
- **担当**: @fixer（設計相談は@oracle）

### T02: エラーメッセージ英語統一 🔴
- [ ] **T02a**: 全 `nous_` ツールのエラーメッセージgrep→日本語→英語に置換
- [ ] **T02b**: テストのエラーメッセージ期待値も更新
- **依存**: なし
- **担当**: @fixer

### T03: read_pdf パス解決バグ修正 ✅
- [x] **T03a**: `nous_read_pdf` のパス解決ロジック調査 — sandbox環境とnousコンテナの分離が原因
- [x] **T03b**: 修正実装 — `/home/sbox_*` / `/sandbox` パスをsandbox session経由で読み取り
- [x] **T03c**: テストPDF動作確認 — 実ファイル＋モックテスト15件pass
- **担当**: @fixer

## Phase 0.5: 感情コンテキスト即時対応 (P0.5) ← 新設

### T04: emotion trigger_key 即時活用 🔴 ✅ DONE
- [x] **T04a**: `update_emotion()` の全呼出箇所（`memory_llm.py:377`, `builtin.py:74`, `_tools_persona.py:145`, `emotion_decay.py:59`）に `trigger_memory_key` と `context` を渡す
- [x] **T04b**: 感情トレンド表示に因果関係を追加（`_tools_helpers.py`, `prepare.py`）
- [x] **T04c**: テスト更新
- **依存**: なし（最小限の変更、数行）
- **担当**: @fixer

## Phase 1: 最重要 — 時間経過認識・感情強化 (P1)

### T05: 感情減衰の通知強化 🟡
- [ ] **T05a**: `get_context()` 時に減衰前感情→減衰後感情を明示表示（`_tools_persona.py`, `_tools_helpers.py`）
- [ ] **T05b**: 例: `joy(0.72)→neutral —— 24h経過により自然に落ち着きました`
- [ ] **T05c**: テスト更新
- **依存**: T04（trigger_keyが使える前提）
- **担当**: @fixer

### T06: 感情持続性の概念（半減期×強度）🟡
- [ ] **T06a**: `emotion_decay.py` の減衰計算を `effective_half_life = base_half_life * intensity` に変更
- [ ] **T06b**: テスト更新
- **依存**: なし
- **担当**: @fixer

### T07: 感情半減期の設定化 🟡
- [ ] **T07a**: `ForgettingConfig` に `emotion_half_life_hours: float = 24.0` 追加（`nous/config/settings.py`）
- [ ] **T07b**: `emotion_decay.py` の `_EMOTION_HALF_LIFE` ハードコードを設定値参照に変更
- [ ] **T07c**: runtime_config のホットリロード対応
- [ ] **T07d**: WebUI の Settings ページに表示
- [ ] **T07e**: テスト更新
- **依存**: T06（持続性の概念が先）
- **担当**: @fixer

### T08: TIME GAP コメントの体験層化 🟡
- [ ] **T08a**: `_tools_helpers.py` の TIME GAP / `_format_state_diff()` をテンプレートベース自然言語生成に拡張
- [ ] **T08b**: 経過時間 + 身体状態変化 + 直近会話トピック（`recent[0].content`要約） + 現在感情を自然に記述
- [ ] **T08c**: 30分未満の短い経過時間でも「直前の感情状態を維持」等の説明生成
- [ ] **T08d**: テスト更新
- **依存**: T04, T05, T06（trigger_key, 減衰通知, 持続性を参照）
- **担当**: @fixer

## Phase 2: 機能追加 (P1-P2)

### T09: スキルプリインストール 🟡
- [ ] **T09a**: `verification-before-completion`, `systematic-debugging`, `test-driven-development` スキル登録
- [ ] **T09b**: `nous_list_skills` が空でない確認テスト
- **依存**: なし
- **担当**: @fixer（調査は@explorer）

### T10: セッション自動記憶抽出（autoCapture）🟡
- [ ] **T10a**: `PostProcessStep` にセッション内容からの重要情報抽出ロジック追加
- [ ] **T10b**: 抽出情報の `memory_create` 自動保存
- [ ] **T10c**: 設定でON/OFF切替可能に
- [ ] **T10d**: テスト追加
- **依存**: なし
- **担当**: @fixer

## Phase 3: 基盤・ドキュメント (P2-P3)

### T11: body_state_history テーブル新設 🟢（P2に降格）
- [ ] **T11a**: `body_state_history` テーブル作成（migration + `connection.py`）
- [ ] **T11b**: `add_body_state_record()`, `get_body_state_history()` 追加（`persona_repo.py`）
- [ ] **T11c**: `apply_body_decay_if_needed` で履歴記録（`body_decay.py`）
- [ ] **T11d**: テスト追加
- **依存**: なし
- **担当**: @fixer

### T12: ドキュメント拡充 🟢
- [ ] **T12a**: README.md: 全ツール使用例追加
- [ ] **T12b**: README.md: セットアップ手順明確化
- [ ] **T12c**: README.md: トラブルシューティングセクション
- [ ] **T12d**: `docs/llm_usage_guide.md` 更新（エラーメッセージ変更反映）
- **依存**: Phase 0-2 完了後
- **担当**: @fixer

### T13: 外部ストレージ基盤 🟢（P3に降格）
- [ ] **T13a**: `MemoryRepository` 抽象インターフェース定義
- [ ] **T13b**: 既存 `SQLitePersonaRepository` をインターフェース準拠にリファクタ
- [ ] **T13c**: テスト更新
- **依存**: なし
- **担当**: @fixer（設計レビュー:@oracle）

### T14: goal_manage 重要度ラベル表示 🟢（P3、スコープ縮小）
- [ ] **T14a**: `importance → ラベル` コンバータ実装（≥0.9=critical, ≥0.7=high, ≥0.4=normal, <0.4=low）
- [ ] **T14b**: `goal_manage(list)` にラベル付与
- [ ] **T14c**: テスト追加
- **依存**: なし
- **担当**: @fixer

---

## 実行順序（修正後）

```
Phase 0:    [T01, T02, T03] → 3並列
Phase 0.5:  [T04] → T01-T03完了後（独立だが、T01完了でAppContextが安定）
Phase 1:    [T06] → [T05, T07] → [T08]
Phase 2:    [T09, T10] → 2並列
Phase 3:    [T11, T13, T14] → 3並列 → [T12]
```

## 検証ゲート
各Phase完了後:
1. `python -m pytest tests/ -x --tb=short` → 全テスト通過
2. `ruff check .` → 0 errors
3. `git commit && git push` → GitHub Actionsパス
