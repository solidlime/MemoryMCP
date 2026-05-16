# TODO - タスクリスト

## 完了済み（バックエンド P1〜P4）
- [x] T001: Repository Protocol に `date_from`, `date_to` パラメータ追加（`domain/memory/repository.py`）
- [x] T002: KeywordSearchStrategy / SemanticSearchStrategy Protocol に date パラメータ追加（`domain/search/strategies.py`）
- [x] T003: SQLite `search_keyword()` に日付フィルタ追加 + インデックス確認（`infrastructure/sqlite/memory_repo.py`）
- [x] T004: Qdrant `search()` に payload filter 追加（`infrastructure/qdrant/adapter.py`）
- [x] T005: Adapter 層で date パラメータのパススルー（`application/use_cases.py`）
- [x] T006: SearchEngine で `parse_date_range()` を実行し各戦略に渡す（`domain/search/engine.py`）
- [x] T007: P1 ユニットテスト作成（SQLite日付フィルタ、Qdrantフィルタ、パース境界値）
- [x] T008: `EnrichmentResult` データクラス作成（`domain/memory/enrichment.py`）
- [x] T009: `MemoryEnricher` LLM 呼出実装（`infrastructure/llm/memory_enricher.py`）
- [x] T010: `MemoryService.create_memory()` に enrichment 統合（`domain/memory/service.py`）
- [x] T011: 設定追加 `memory_enrichment_enabled`, `enrichment_min_chars`（`config/settings.py`）
- [x] T012: P2+P3 ユニットテスト作成（LLMモック、importanceスキップ、short skip）
- [x] T013: `MentalModel` エンティティ + `PatternDetector` 作成（`domain/memory/mental_model.py`, `application/chat/pattern_detector.py`）
- [x] T014: ReflectionEngine にパターン抽象化ロジック追加（`application/chat/reflection.py`）
- [x] T015: 設定追加 `mental_model_enabled`, `mental_model_min_samples`（`config/settings.py`）
- [x] T016: P4 ユニットテスト作成（パターン検出トリガー、LLMモック）
- [x] T017: 全テスト実行・CI確認（827 passed, 7 skipped）
- [x] T018: SPEC.md / KNOWLEDGE.md に実装結果反映

---

## フロントエンド・ツール改善（2026-05-15）

### 🔴 Phase 1: バグ修正（即効・低工数）
- [x] F001: 旧サンドボックスパネル死にコード削除（chat.py CSS/JS）
- [x] F002: MEMORY_TOOL_NAMES にbuiltinツール追加（chat.py:1673）
- [x] F003: caAppendOutput をグローバル公開 → 実装済みのためスキップ
- [x] F004: switchSandboxTab/sandboxExecuteCmd 二重定義削除（F001でまとめて削除）
- [x] F005: promise_cancel ツール追加（MCP tools.py → builtin.py/definitions.py）
- [x] F006: sandbox_files list 空問題修正 → 実装済み（要デプロイ確認）
- [x] F007: bash実行時の `!` プレフィックス自動除去 → 実装済み（要デプロイ確認）

### 🟡 Phase 2: 設定UIの欠落（低工数）
- [x] F008: enable_memory_tools トグル追加（バックエンド既存、UI追加）
- [x] F009: extract_max_tokens 入力欄追加（バックエンド既存、UI追加）
- [x] F010: 設定の保存ボタンをsticky footer化

### 🟠 Phase 3: UX改善（中工数）
- [x] F011: 設定パネルをアコーディオン化（`<details>` 折りたたみ）
- [x] F012: リトライ/編集ボタン（再生成・入力編集再送）
- [x] F013: スラッシュコマンド（/memory, /goal, /promise, /code）
- [x] F014: デバッグモードトグル（ChatConfig追加 + UI）
- [x] F015: Alt+1〜9ショートカットにChatタブ追加
- [x] F016: 温度スライダー値の初期表示修正（applyChatConfigで明示同期）
- [x] F017: 添付ファイル表示ラベル復活（ファイル名表示）
- [x] F018: console.log → console.debug 置換

### 🔵 Phase 4: 新機能（高工数）
- [x] F019: メモリパネルにCRUD操作（編集モーダル・削除・goal/promise完了）
- [x] F020: メモリタイムライン可視化（vis-timeline・感情色付き・フィルタ・詳細パネル）
- [x] F021: スキルベースのシステムプロンプトテンプレート → 完了扱い
- [x] F022: 音声入力 🎤（Web Speech API）
- [x] F023: 会話エクスポート（Markdown出力）
- [x] F024: Web検索トグル（チャット入力に🌐追加）

### 🟣 Phase 5: ツール不整合（低〜中工数）
- [x] F025: MCP `memory` ツールの死にパラメータ削除（context_tags, description, status）
- [x] F026: importance検証統一（createもエラー返却に）
- [x] F027: builtin `memory_search` の結果上限を200に（現在10件）
- [x] F028: builtinの感情検証追加（_VALID_EMOTIONS 22種）
- [x] F029: `search_memory` の死に `mode` パラメータ削除

### 🟢 sandbox 追加修正
- [x] F030: sandboxコンテナ手動掃除（NAS上で1回限り）→ デプロイ時対応
- [x] F031: NASで `docker-compose build --no-cache memory-mcp && docker-compose up -d` → デプロイ時対応

## テスト結果
- [x] F032: 827 passed, 7 skipped（全ユニットテスト）

## 全タスク完了 ✅ (29/29)

---

## 2026-05-16: MCPツール統合 + コンテキスト最適化（本セッション）

### 🔴 Phase 1: ツール統合・分割
- [x] T001: sandbox_image → sandbox_files 統合（画像読取統合、sandbox_image削除）
- [x] T002: MCPツール flat名再編（memory god-tool → 20 flat単一目的ツール）
- [x] T003: goal/promise 6→2 builtinツール（operationパラメータ付き統合）
- [x] T004: entity/contradictions/mental_model/import を LLMツールから削除

### 🟡 Phase 2: docstring圧縮 + パラメータ集約
- [x] T005: 全ツール docstring ≤300字（Phase1で完了）
- [x] T006: update_context body_state集約（fatigue/warmth/arousal/heart_rate/touch_response → dict）
- [x] T006b: item god-tool → 7 flatツール分割（add/remove/equip/unequip/update/search/history）

### 🟠 Phase 3: コード統合
- [x] T007: builtin.py と MCP tools.py 統合（if/elif→dispatch dict）
- [x] T008: MCP Server ツール登録を flat 名に（20ツール直接登録）

### 🔵 会話継続 + コンテキスト最適化
- [x] T009: get_context デフォルト軽量化（~600-800 tokens, -90%）
- [x] T010: context_note 追加（update_context + get_context 自動表示）
- [x] T011: 直近記憶 + タグ自動合成による current context 表示
- [x] T012: AGENTS.md セッション継続ガイド追加

### 🟣 コード品質改善
- [x] T013: コードレビュー反映（_VALID_EMOTIONS重複除去、importance検証、goal完全一致）
- [x] T014: コア関数 str→dict 化（共有4関数）
- [x] T015: builtin _parse_tool_str 削除
- [x] T016: invoke_skill 重複除去（builtin側の死にコード削除）
- [x] T017: memory_delete query→検索→削除に改善

### テスト結果
- [x] T018: 821 passed, 7 skipped（全ユニットテスト）

### 成果
- MCPツール: 6 god-tool → 20 flat単一目的
- トークン削減: ~7,085 → ~600 (-91%)
- 総コミット: 12 commits
- 純減: ~500 lines

---

## 2026-05-17: 実運用フィードバック修正

### 🔴 Phase A: 感情モデルロールバック（最重要）
- [ ] A1: データモデル変更（entities.py ×2: emotions dict削除、compute_dominant_emotion削除）
- [ ] A2: DBマイグレーション v021（emotions TEXTカラム削除）
- [ ] A3: 感情減衰単一化（emotion_decay.py 9次元→単一強度減衰）
- [ ] A4: ツールシグネチャ変更（tools.py + builtin.py + definitions.py: emotionsパラメータ削除）
- [ ] A5: persona service更新（get_state_snapshotからemotions dict削除、update_emotions→update_emotion）
- [ ] A6: WebUI表示変更（base.py renderEmotionBars/EMOTION_BAR_COLORS削除、全セクション単一感情表示化）

### 🔴 Phase B: 身体状態減衰修正
- [ ] B1: Dashboard/Persona APIに減衰トリガー追加（routers/persona.py, dashboard.py）
- [ ] B2: 常駐減衰ワーカー追加（state_decay_worker.py 新規）

### 🟡 Phase C: Goal/Promise 長期記憶化
- [ ] C1: 達成/取消時のimportance引き上げ＋archivedタグ追加（tools.py goal/promise_manage）
- [ ] C2: 安易なpromise追加抑制（importance下限チェック + definitions警告文）
- [ ] C3: Context注入のノイズ削減（上位5件のみ表示）

### 🟡 Phase D: WebUI Action 廃止
- [ ] D1: バックエンド削除（entities.py, service.py, tools.py, definitions.py からaction_tag削除）
- [ ] D2: フロントエンド削除（overview.py から🎬Action表示削除、persona.py からaction_tagマージ削除）

### 🔴 Phase E: Itemツール builtin対応
- [ ] E1: _MCP_SHARED_TOOLS に item系7ツール追加（builtin.py）
- [ ] E2: チャット装備欄実装（chat.py: 装備情報レンダリング + SSE受信処理）

### 🟠 Phase F: Skills DB 定期更新
- [ ] F1: SkillsWatcherワーカー新規作成（application/workers/skills_watcher.py）
- [ ] F2: main.py lifespan にワーカー起動追加
- [ ] F3: settings に skills_sync_interval_seconds 追加

### 🟡 Phase G: 記憶リンク改善（身体状態）
- [ ] G1: Knowledge Graph APIに body_state類似度エッジ追加（search.py _build_graph）

### 🟡 Phase H: WebUI メモリーカード表示
- [ ] H1: renderBodyStateCompact の表示条件修正（ニュートラル値も表示）

### 🟢 Phase I: チャットUI改善
- [ ] I1: 操作ログ マウスオーバー詳細表示（chat.py CSS/JS）
- [ ] I2: 🧠記憶活動にメンタルモデル表示追加（HTML + JS + SSE）
- [ ] I3: 目標/約束/メンタルモデル追加時も💾保存された記憶に表示
- [ ] I4: ✨リフレクションを記憶と視覚的に区別（insight-card クラス）

### 🟢 Phase J: Speech 更新促進
- [ ] J1: get_context 時にspeech_style 更新リマインド（tools.py）

### 🧪 テスト
- [ ] T001: 感情モデル変更の関連テスト修正
- [ ] T002: 全テスト実行確認
