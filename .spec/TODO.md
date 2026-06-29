# TODO - タスクリスト v10

## 優先度：🔴（ブロッカー・本番必須）
- [x] T035: E-1 RuntimeConfigManager 優先順位を override > env > default に変更（30m）
- [x] T036: E-2 LLM APIキーを Settings 統合 + RuntimeConfigManager 管轄化（1h）
- [x] T037: E-3 SearXNG URL / agent-browser パス の RuntimeConfigManager 管轄化（30m）
- [x] T038: E-4 WebUI 設定ダッシュボード拡充（APIキー欄・全カテゴリ・envソース表示）（1.5h）
- [x] T039: F-1 chat.message フックで synthetic part メモリ注入（1.5h, plugins/opencode-memory-sync）
- [x] T040: F-2 session.compacted イベントで compaction recovery（1h, plugins/opencode-memory-sync）
- [x] T041: F-3 warmup 非同期化（30m, plugins/opencode-memory-sync）
- [x] T042: G-1 sandbox コンテナの /home 一括バインドマウント（15m, docker-compose.yml）
- [x] T043: G-2 config ペルソナの dangling mount 除去（5m, docker-compose.yml）
- [x] T044: G-3 default ペルソナの docker-compose マウント除去（G-1で自動解決）
- [x] T045: H-1 Dockerfile の memory_mcp → nous 修正（15m）
- [x] T046: H-2 docker-compose nous を ghcr.io/solidlime/nous:latest に（5m）
- [x] T047: H-3 GitHub Actions docker.yml のイメージ名修正確認（15m）

## 優先度：🟡（重要・後方互換）
- [ ] T001: A-1 SearXNG docker-compose化（30m）
- [x] T002: A-2 Dockerfile.sandbox多言語ランタイム追加（2h）(Chunk 1-3で実装済み: 単一sandboxコンテナ + docker exec方式)
- [ ] T003: A-4 本番ビルド + 全起動確認（1h, A-1,A-2依存）
- [ ] T004: B-1 5ツールMCP登録 — browser/search/image_generate/read_pdf/list_skills（2h）
- [ ] T005: B-5-1 memory_create/search/update 戻り値形式統一 (MCP→dict)（1.5h, B-1依存）
- [x] T006: C-2 JavaScript sandboxセッション追加（2h, A-2依存）(Chunk 1-3で実装済み: 単一sandboxコンテナ + docker exec方式)

## 優先度：🟡（重要・後方互換）
- [ ] T007: A-3 SearXNG環境変数化（15m, A-1依存）
- [ ] T008: A-5 Docker security hardening（15m, A-1依存）
- [ ] T009: A-6 /health エンドポイント追加（30m）
- [x] T010: B-2 execute_code → sandbox 名前統一（30m）(Chunk 1-3で実装済み: 単一sandboxコンテナ + docker exec方式)
- [ ] T011: B-3 context_update → update_context 統合（1h）
- [ ] T012: B-4 _NOUS_TOOL_NAMES フィルタ修正（5m, B-2依存）
- [ ] T013: B-5-2 memory_create/search/update 実装統合・委譲（2h, B-5-1依存）
- [x] T014: C-5 Bash ネイティブ実行化（1h）(Chunk 1-3で実装済み: 単一sandboxコンテナ + docker exec方式)
- [x] T015: C-6 allowed_languages 更新 + get_supported_languages ツール追加（5m, C-2~C-5依存）(Chunk 1-3で実装済み: 単一sandboxコンテナ + docker exec方式)

## 優先度：🟢（改善・新機能）
- [ ] T016: B-6 ツール説明環境変数カスタマイズ（30m）
- [x] T017: C-3/C-4 Go/Rust sandboxセッション追加（2h, A-2依存）(Chunk 1-3で実装済み: 単一sandboxコンテナ + docker exec方式)
- [ ] T018: D-1 PDF OCR対応（2h）
- [ ] T019: D-2 Agent Skills標準移行（基本）（4h）
- [ ] T020: D-3 メモリ 4-tier lifecycle（基本）（6h, B-5-2依存）
- [ ] T021: D-4 メモリ検索ハイブリッド強化（4h, D-3依存）
- [ ] T048: I-1 Settings.default_persona → None に変更（5m）
- [ ] T049: I-2 MCP ツールのペルソナ未指定エラー処理（middleware.py, chat_config.py）（30m）
- [ ] T050: I-3 WebUI 初期セットアップ画面（persona.py ルート + セットアップ HTML）（1h）
- [ ] T051: I-4 default 削除禁止コード除去（persona.py, sections/persona.py）（15m）
- [ ] T052: I-5 テスト更新 + 後方互換確認（30m）

## 優先度：🟢（改善・新機能 続き）
- [x] T053: J-23 ConsolidationWorker 実装 + summarization_worker 削除（1h）

## 並行実行計画

```
フェーズ1（並行）:
  T001 (A-1) ── T002 (A-2) ── T009 (A-6)
  T004 (B-1) ── T010 (B-2) ── T011 (B-3)
  T018 (D-1) ── T019 (D-2)

フェーズ2（フェーズ1一部完了後）:
  T007 (A-3) ── T008 (A-5) ── T003 (A-4)
  T012 (B-4) ── T005 (B-5-1) ── T013 (B-5-2) ── T016 (B-6)
  T006 (C-2) ── T014 (C-5) ── T017 (C-3/C-4) ── T015 (C-6)

フェーズ3（B-5-2完了後）:
  T020 (D-3) ── T021 (D-4)

## @oracle レビュー (2026-06-27) からの追加タスク

### 🔴 P0: テスト計画の穴を埋める
- [ ] T022: NEW-01 tombstone化→memory_read除外→find_by_key取得可能のテスト追加
- [ ] T023: NEW-02 tombstonedメモリがmemory_search結果から除外されるテスト追加
- [ ] T024: NEW-03 Import/Export往復データ同一性テスト追加
- [ ] T025: NEW-04 ChatのDOMPurify XSS防御テスト追加
- [ ] T026: NEW-05 /healthエンドポイント到達性報告テスト追加
- [ ] T027: DK-08 初回起動目標値を120s→300sに修正

### 🟡 P1: カバレッジ拡充
- [ ] T028: セキュリティテスト (XSS注入/パストラバーサル/MCPインジェクション)
- [ ] T029: データ整合性テスト (Qdrant↔SQLite同期ズレ/tombstone→Qdrant物理削除)
- [ ] T030: ネットワーク障害テスト (SSE再接続中メッセージ欠落/Qdrant-SearXNG断→復帰)
- [ ] T031: 優先度修正反映 (AD-01 P0→P1, CH-16 P3→P1, IE-01/02 P1→P0)

### 🟢 P2: 拡張テスト
- [ ] T032: パフォーマンステスト (10000件/100000件スケーラビリティ)
- [ ] T033: アップグレード/マイグレーション後方互換性テスト
- [ ] T034: 設定二重管理（.env vs WebUI）競合パターンテスト
```

---

## 柱K: MCPツール ヘルタ実使用レビュー改善 (2026-06-29)

### 🔴 高優先度（ヘルタの毎日使う体験に直結）
- [ ] T042: K-1 memory_search スコアを 0-1 正規化（`_tools_memory.py: _tool_memory_search`）
- [x] T043: K-2 memory_read に total_count 返却（`_tools_memory.py: _tool_memory_read`）
- [x] T044: K-3 sandbox_execute のエラーメッセージ改善（Permission denied 表示）

### 🟡 中優先度（一貫性・信頼性）
- [ ] T045: K-4 memory_delete の docstring 修正（query パラメータの扱い明確化）
- [ ] T046: K-5 item_* 7ツール → item 1ツールに統合（operation パラメータ）

### 🟢 低優先度（仕上げ）
- [ ] T047: K-6 sandbox_context の pip_packages 実装 or 削除
- [ ] T048: K-7 memory_create の感情自動付与に auto_emotion フラグ追加
```
