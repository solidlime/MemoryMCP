# TODO: マルチモーダルLLM対応

## フェーズ1: 画像生成基盤 (DALL-E + SD)
- [x] 1.1 `infrastructure/image_gen/` パッケージ作成
  - [x] 1.1.1 `base.py` — ImageGenProvider 抽象クラス
  - [x] 1.1.2 `dalle.py` — DALL-E 3 実装
  - [x] 1.1.3 `stability.py` — SD WebUI API 実装
  - [x] 1.1.4 `factory.py` — ファクトリ
- [x] 1.2 `domain/chat_config.py` — image_gen 系フィールド追加
- [x] 1.3 DBマイグレーション — v026
- [x] 1.4 `events.py` — ImageGen SSE
- [x] 1.5 `tools/definitions.py` — image_generate ツール定義
- [x] 1.6 `tools/builtin.py` — _handle_image_generate()
- [x] 1.7 `sections/chat.py` — 画像生成設定UI
- [x] 1.8 `static/chat.js` — イベント処理
- [x] 1.9 `static/chat.css` — 画像表示スタイル

## フェーズ2: PDF解析
- [x] 2.1 `tools/definitions.py` — read_pdf ツール定義
- [x] 2.2 `tools/builtin.py` — _handle_read_pdf()
- [x] 2.3 `domain/chat_config.py` — pdf_max_size_mb
- [x] 2.4 DBマイグレーション — v027

## フェーズ3: テスト・検証
- [x] 3.1 Python 単体テスト
  - [x] 3.1.1 `test_image_gen_providers.py`
  - [x] 3.1.2 `test_read_pdf.py`
  - [ ] 3.1.3 `test_chat_service.py` — image_gen_* イベントテスト
- [ ] 3.2 統合テスト
  - [ ] 3.2.1 PDF添付→ツール呼び出し→応答のE2E
  - [ ] 3.2.2 画像生成→チャットログ表示のE2E
- [ ] 3.3 ブラウザテスト (agent-browser)

---

# TODO: コード健全化 2026-06-26

## フェーズ4: sections/ のHTML外出し
- [x] 4.1 `base.py` — CSS/JS抽出 (1,238→136行)
- [x] 4.2 `memories.py` — JS抽出 (1,101→275行)
- [x] 4.3 `settings.py` — JS抽出 (645→40行)
- [x] 4.4 `coding_agent.py` — JS抽出 (634→328行)
- [x] 4.5 `knowledge_graph.py` — JS抽出 (606→181行)
- [x] 4.6 `overview.py` — JS抽出 (564→31行)
- [x] 4.7 `chat.py` — 変更なし
- [x] 4.8 `activity.py` — JS抽出 (378→165行)
- [x] 4.9 `timeline.py` — JS抽出 (361→155行)
- [x] 4.10 全テストパス & ruffパス確認
- [x] 4.11 coding_agent.js 埋め込み欠落バグ修正

## フェーズ5: カバレッジ改善
- [x] 5.1 テスト追加 (runtime_config, use_cases, pattern_detector, compress, prepare)
- [x] 5.2 全体カバレッジ 63→65%（70%は長期目標）

## フェーズ6: 設定統一
- [x] 6.1 lefthook に統一、`.pre-commit-config.yaml` 削除

## フェーズ7: Dependabot ブランチ整理
- [x] 7.1 放置ブランチ10本削除

---

# TODO: ツール改善 2026-06-27

## フェーズA: 低リスク・高効果
- [ ] A1. description 短文化（全14ツール → definitions.py）
- [ ] A2. context_recall 削除（definitions.py + builtin.py）
- [ ] A3. search パラメータ追加（num_results, language）
- [ ] A4. goal/promise description 差別化（A1に含む）
- [ ] A5. 全テストパス & ruffパス確認

## フェーズB: 中リスク・高効果
- [ ] B1. context_update 自動化（memory_create 内で自動スナップショット）
- [ ] B2. sandbox_files の append/Edit 操作追加
- [ ] B3. 全テストパス & ruffパス確認

## フェーズC: 高リスク・高効果
- [ ] C1. memory_create の重複検出
- [ ] C2. execute_code の session_id 対応
- [ ] C3. 全テストパス & ruffパス確認

## フェーズD: 軽微・任意
- [ ] D1. invoke_skill の list_skills 機能追加
- [ ] D2. browser ツール description 改善（A1に含む）
