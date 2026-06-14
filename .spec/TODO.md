# TODO - context-mode 機能移植（2026-06-12）

## L2: インフラ（EventBus + SSE）🔴 最優先

### E1: EventBus ✅ 完了
- [x] E1-1: `application/event_bus.py` 新規 — `EventBus` クラス（pub/sub）
- [x] E1-2: `api/mcp/tools.py` — 4ツールに `event_bus.publish()` 追加（memory_create/update/delete + update_context）
- [x] E1-3: EventBus ユニットテスト（7テストパス）

### E2: SSEエンドポイント ✅ 完了
- [x] E2-1: `api/http/routers/events.py` 新規 — `GET /api/events/{persona}` SSEエンドポイント
- [x] E2-2: `api/http/sections/base.py` — init関数にEventSource接続 + トースト通知追加
- [x] E2-3: SSE ユニットテスト（3テストパス、TestSSEBridge）
- [x] 🐶 ドッグフーディング: MCP→EventBus→SSEパイプラインE2E確認済み

### E3: Plugin用HTTP取り込みAPI
- [ ] E3-1: `api/http/routers/events.py` — `POST /api/events/ingest` エンドポイント
- [ ] E3-2: 取り込み→EventBus連携テスト

---

## L1: MCPサーバー拡張 🔴

### M1: FTS5全文検索
- [ ] M1-1: マイグレーション v023 作成（memories_fts + triggers + 全既存データ再インデックス）
- [ ] M1-2: `infrastructure/sqlite/memory_repo.py` — `search_keyword()` → FTS5 MATCH + bm25
- [ ] M1-3: `domain/search/strategies.py` — `fts_enabled` パラメータ追加
- [ ] M1-4: `config/settings.py` — `fts_enabled: bool = True`
- [ ] M1-5: FTS5 ユニットテスト（MATCH, bm25, フォールバック, 日本語）

### M2: 外部コンテンツ取り込み
- [ ] M2-1: `domain/memory/ingest.py` 新規 — `IngestService`
- [ ] M2-2: `api/mcp/tools.py` — `ingest` ツール追加
- [ ] M2-3: `config/settings.py` — ingest関連設定
- [ ] M2-4: `pyproject.toml` — httpx, html2text 依存追加
- [ ] M2-5: ingest ユニットテスト（URL/markdown/text, チャンク分割）

### M3: バッチツール実行
- [ ] M3-1: `api/mcp/tools.py` — `batch` ツール追加
- [ ] M3-2: batch ユニットテスト（複数操作、エラーハンドリング、許可制限）

### M4: 近接性リランキング（M1完了後）
- [ ] M4-1: `domain/search/ranker.py` — `ProximityRanker` 追加
- [ ] M4-2: `domain/search/ranker.py` — `ChainedRanker` チェーンに追加
- [ ] M4-3: `config/settings.py` — `proximity_window`
- [ ] M4-4: 近接性 ユニットテスト

### M5+M6: upgrade + doctor（低優先・後回し）
- [ ] M5-1: `api/mcp/tools.py` — `upgrade` ツール
- [ ] M6-1: `api/mcp/tools.py` — `doctor` ツール

---

## L3: OpenCode Plugin 🔴

### P1: プラグイン本体（E3完了後）
- [ ] P1-1: `plugins/opencode-memory-sync/` ディレクトリ作成
- [ ] P1-2: `package.json` + `tsconfig.json` セットアップ
- [ ] P1-3: プラグイン本体実装（PreToolUse/PostToolUse/SessionStart/Stop/PreCompact）
- [ ] P1-4: `POST /api/events/ingest` へのHTTP送信ロジック
- [ ] P1-5: 動作確認（OpenCodeで読み込んでMemoryMCP WebUIにイベントが届くか）

---

## 🧪 最終確認
- [ ] T001: 全ユニットテスト実行
- [ ] T002: CI パス確認
- [ ] T003: SPEC.md / KNOWLEDGE.md / MEMORY.md 更新

## 依存グラフ
```
E1 ──┬── E2 ── WebUI SSE受信
     ├── E3 ── P1 (Plugin)
     │
M1 ──┼── 独立
     │   └── M4
M2 ──┤
M3 ──┤
     │
M5+M6（後回し）
```

## 並列実行: E1+M1+M2+M3 が同時着手可
