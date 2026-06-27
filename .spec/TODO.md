# TODO - タスクリスト v8

## 優先度：🔴（ブロッカー・本番必須）
- [ ] T001: A-1 SearXNG docker-compose化（30m）
- [ ] T002: A-2 Dockerfile.sandbox多言語ランタイム追加（2h）
- [ ] T003: A-4 本番ビルド + 全起動確認（1h, A-1,A-2依存）
- [ ] T004: B-1 5ツールMCP登録 — browser/search/image_generate/read_pdf/list_skills（2h）
- [ ] T005: B-5-1 memory_create/search/update 戻り値形式統一 (MCP→dict)（1.5h, B-1依存）
- [ ] T006: C-2 JavaScript sandboxセッション追加（2h, A-2依存）

## 優先度：🟡（重要・後方互換）
- [ ] T007: A-3 SearXNG環境変数化（15m, A-1依存）
- [ ] T008: A-5 Docker security hardening（15m, A-1依存）
- [ ] T009: A-6 /health エンドポイント追加（30m）
- [ ] T010: B-2 execute_code → sandbox 名前統一（30m）
- [ ] T011: B-3 context_update → update_context 統合（1h）
- [ ] T012: B-4 _MEMORY_MCP_TOOL_NAMES フィルタ修正（5m, B-2依存）
- [ ] T013: B-5-2 memory_create/search/update 実装統合・委譲（2h, B-5-1依存）
- [ ] T014: C-5 Bash ネイティブ実行化（1h）
- [ ] T015: C-6 allowed_languages 更新 + get_supported_languages ツール追加（5m, C-2~C-5依存）

## 優先度：🟢（改善・新機能）
- [ ] T016: B-6 ツール説明環境変数カスタマイズ（30m）
- [ ] T017: C-3/C-4 Go/Rust sandboxセッション追加（2h, A-2依存）
- [ ] T018: D-1 PDF OCR対応（2h）
- [ ] T019: D-2 Agent Skills標準移行（基本）（4h）
- [ ] T020: D-3 メモリ 4-tier lifecycle（基本）（6h, B-5-2依存）
- [ ] T021: D-4 メモリ検索ハイブリッド強化（4h, D-3依存）

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
```
