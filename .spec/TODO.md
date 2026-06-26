# TODO: マルチモーダルLLM対応

## フェーズ1: 画像生成基盤 (DALL-E + SD)
- [x] 1.1 `infrastructure/image_gen/` パッケージ作成
  - [x] 1.1.1 `base.py` — ImageGenProvider 抽象クラス (`generate(prompt, size, quality, n) -> list[GeneratedImage]`)
  - [x] 1.1.2 `dalle.py` — DALL-E 3 実装 (openai.images.generate)
  - [x] 1.1.3 `stability.py` — SD WebUI API 実装 (POST /sdapi/v1/txt2img)
  - [x] 1.1.4 `factory.py` — get_image_gen_provider(config) ファクトリ
- [x] 1.2 `domain/chat_config.py` — image_gen 系フィールド追加
- [x] 1.3 DBマイグレーション — v026 で image_gen カラム追加
- [x] 1.4 `events.py` — ImageGenStartSSE, ImageGenResultSSE 追加
- [x] 1.5 `tools/definitions.py` — image_generate ツール定義 + _BUILTIN_DISPATCH 登録
- [x] 1.6 `tools/builtin.py` — _handle_image_generate() 実装
- [x] 1.7 `sections/chat.py` — 画像生成設定UI (有効/無効, プロバイダ, モデル, SD URL)
- [x] 1.8 `static/chat.js` — image_gen_start / image_gen_result イベント処理, 画像表示
- [x] 1.9 `static/chat.css` — 生成画像のスタイル (ローディングスピナー, 画像カード)

## フェーズ2: PDF解析
- [x] 2.1 `tools/definitions.py` — read_pdf ツール定義 + _BUILTIN_DISPATCH 登録
- [x] 2.2 `tools/builtin.py` — _handle_read_pdf() 実装 (fitz + pdfplumber)
- [x] 2.3 `domain/chat_config.py` — pdf_max_size_mb フィールド追加
- [x] 2.4 DBマイグレーション — v027 で pdf_max_size_mb カラム追加

## フェーズ3: テスト・検証
- [x] 3.1 Python 単体テスト
  - [x] 3.1.1 `test_image_gen_providers.py` — DALL-E / SD モックテスト
  - [x] 3.1.2 `test_read_pdf.py` — PDF解析テスト (テキスト/テーブル/画像抽出)
  - [ ] 3.1.3 `test_chat_service.py` — image_gen_* イベントテスト, ツール呼び出しテスト
- [ ] 3.2 統合テスト
  - [ ] 3.2.1 PDF添付→ツール呼び出し→応答のE2Eフロー
  - [ ] 3.2.2 画像生成→チャットログ表示のE2Eフロー
- [ ] 3.3 ブラウザテスト (agent-browser)
- [ ] 3.4 CI統合 — ruff / pytest / bandit 全パス確認

---

# TODO: コード健全化 2026-06-26

## フェーズ4: sections/ のHTML外出し
- [ ] 4.1 `base.py` — 共通レイアウトテンプレート抽出 (1,238→400行目標)
- [ ] 4.2 `memories.py` — メモリー画面テンプレート抽出 (1,101→350行目標)
- [ ] 4.3 `settings.py` — 設定画面テンプレート抽出 (645→250行目標)
- [ ] 4.4 `coding_agent.py` — コーディングエージェント抽出 (634→250行目標)
- [ ] 4.5 `knowledge_graph.py` — 知識グラフ抽出 (606→250行目標)
- [ ] 4.6 `overview.py` — オーバービュー抽出 (564→200行目標)
- [ ] 4.7 `chat.py` — チャット画面抽出 (451→150行目標)
- [ ] 4.8 `activity.py` — アクティビティ抽出 (378→150行目標)
- [ ] 4.9 `timeline.py` — タイムライン抽出 (361→150行目標)
- [ ] 4.10 全テストパス & ruffパス確認

## フェーズ5: カバレッジ改善
- [ ] 5.1 カバレッジレポート取得 → 未カバーホットスポット特定
- [ ] 5.2 テスト追加で70%到達

## フェーズ6: 設定統一
- [ ] 6.1 lefthook に統一、`.pre-commit-config.yaml` 削除

## フェーズ7: Dependabot ブランチ整理
- [ ] 7.1 放置ブランチ10本のマージ or クローズ
