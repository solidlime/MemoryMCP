# PLAN - やりたいこと

## 2026-06-20: コードベース健全化（本セッション）

### 背景
context-mode移植はL2(EventBus+SSE)+L3(Plugin)まで完了。残るL1(FTS5等)は後日。
コードが肥大化・複雑化してきたので、今のうちに全コードベースの健全化（リファクタリング）を実施したい。

### やること
- 巨大ファイルの分割（chat.py 2557行, tools.py 1953行）
- 重複コードの共通化（importanceバリデーション, emotion/emotion_type統一）
- 握り潰しエラーのログ出力化（except:pass → logger.warning）
- 死にコード・DEPRECATED削除
- ruff全件修正（既存19件含む）
- ドキュメント棚卸し（SPEC/PLAN/TODO/KNOWLEDGE/MEMORY/HANDOFF/README）

### やらないこと（今回）
- FTS5全文検索（M1）
- ingest/batch/doctor/upgrade ツール（M2-M6）
- 大規模UIリプレース
- web_searchブラウザテスト（WSL不安定）
- テスト再構築（R4）

---

## 2026-06-12: context-mode 機能移植（完了）

### 背景
[mksglu/context-mode](https://github.com/mksglu/context-mode)（17.2k★）を分析し、MemoryMCPに移植価値のある機能を特定。
context-modeの成功要因は **MCP（共通ツール）+ Plugin（プラットフォーム固有フック）** のレイヤー分離にある。
MemoryMCPも同様の構造に再編しつつ、検索・イベント記録・リアルタイム同期を実装する。

### 全体アーキテクチャ

```
                         ┌──────────────────────────────────┐
                         │     MemoryMCP HTTP Server        │
                         │  REST API + SSE + WebUI          │
                         │  EventBus (pub/sub)              │
                         │  SQLite + FTS5 + Qdrant          │
                         └────────────┬─────────────────────┘
                                      │
             ┌────────────────────────┼────────────────────────┐
             ▼                        ▼                        ▼
   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
   │  MCP Server     │    │  Plugin         │    │  Plugin         │
   │  (全プラット     │    │  OpenCode       │    │  将来拡張       │
   │   フォーム共通)  │    │  (TypeScript)   │    │  (Cursor等)     │
   │                 │    │                 │    │                 │
   │ memory_create   │    │ PreToolUse      │    │ 各プラット      │
   │ memory_search   │    │ PostToolUse     │    │ フォームの      │
   │ get_context     │    │ SessionStart    │    │ フックAPI       │
   │ update_context  │    │ Stop/PreCompact │    │                 │
   │ item_* ×7       │    │                 │    │ 責務:           │
   │ sandbox ×2      │    │ 責務:           │    │ 全イベント捕捉  │
   │ goal/promise ×2 │    │ 全イベント捕捉  │    │ → HTTP POST     │
   │ [新] ingest     │    │ → HTTP POST     │    │ → MemoryMCP     │
   │ [新] batch      │    │ → MemoryMCP     │    │                 │
   │ [新] doctor     │    │                 │    │ ~50-100行/      │
   │ [新] upgrade    │    │ ~80-100行       │    │ プラットフォーム│
   └────────┬────────┘    └────────┬────────┘    └────────┬────────┘
            │                      │                        │
            ▼                      ▼                        ▼
   全LLMクライアント         OpenCode               Cursor, Gemini CLI,
   (Claude Code,            に対してのみ             VS Code Copilot, etc.
    Gemini CLI,              セッション全体          （必要になったら追加）
    Cursor, etc.)            のイベントを捕捉

プラグインの本質: 全プラットフォームで「捕まえたイベントをHTTP POSTするだけ」。
コアロジック（EventBus, FTS5, SSE, セッション記録）はMemoryMCPサーバーに集約。
```

### 3つの開発レイヤー

| レイヤー | 内容 | 優先度 |
|----------|------|--------|
| **L1: MCPサーバー拡張** | FTS5検索、ingest、batch、近接性ランキング。全プラットフォーム共通 | 🔴 |
| **L2: インフラ** | EventBus + SSEエンドポイント。MCP/Plugin/WebUI間のリアルタイム同期基盤 | 🔴 |
| **L3: OpenCode Plugin** | OpenCode用の薄いTypeScriptプラグイン。全セッションイベントを捕捉→L2にHTTP POST | 🔴 |

---

## L1: MCPサーバー拡張（全プラットフォーム共通）

### M1: FTS5全文検索エンジン 🔴

**概要**: `memory_search` のキーワード検索を SQLite LIKE → FTS5 + BM25 に置換。

**実装方針**:
- マイグレーション v023: `CREATE VIRTUAL TABLE memories_fts USING fts5(content, tags, title, tokenize='porter unicode61')`
- INSERT/UPDATE/DELETE triggers で memories テーブルと自動同期
- `search_keyword()`: `SELECT ... FROM memories JOIN memories_fts ... WHERE memories_fts MATCH ? ORDER BY bm25(memories_fts)`
- フォールバック: FTS5初期化失敗時は既存LIKE検索に戻す
- 日本語: `unicode61` tokenizerでN-gram的に分割。まずこれで実装し品質評価後にbigram化判断

**変更ファイル**: `migration/v023`, `infrastructure/sqlite/memory_repo.py`, `domain/search/strategies.py`, `config/settings.py`

### M2: 外部コンテンツ取り込み（ingest ツール） 🟡

**新規MCPツール**: `ingest(source, source_type="url"|"markdown"|"text", chunk_size=500, chunk_overlap=50, tags=None, importance=0.6)`

- URL→httpx fetch→html2text→チャンク分割→`memory_create`
- チャンク分割: 段落境界を考慮。超過時は文境界で分割
- 元ソースメタデータも別memoryとして保存

**変更ファイル**: `api/mcp/tools.py`, `domain/memory/ingest.py`（新規）, `config/settings.py`

### M3: バッチツール実行 🟡

**新規MCPツール**: `batch(operations: list[dict]) -> dict`

- 複数MCP操作を1ラウンドトリップで実行
- 許可ツールを制限（sandbox等の副作用が大きいものは除外）
- エラーハンドリング: 個別操作の失敗は他に影響しない

**変更ファイル**: `api/mcp/tools.py`

### M4: 近接性リランキング 🟡（M1に依存）

**概要**: マルチタームクエリの単語間距離スコアリング。既存RRFチェーンに追加。

- `ProximityRanker`: クエリ内全単語が20単語以内→1.0、100単語以上→0.1
- `ChainedRanker` のチェーン: RRF → Proximity → ForgettingCurve → TopicAffinity

**変更ファイル**: `domain/search/ranker.py`, `config/settings.py`

### M5+M6: upgrade + doctor 🟢（低優先・後回し）

- `upgrade()`: pip install --upgrade → 結果返却。`allow_auto_upgrade` 設定で制御
- `doctor()`: DB/Qdrant/設定/依存のヘルスチェックレポート

**変更ファイル**: `api/mcp/tools.py`

---

## L2: インフラ（EventBus + SSE）

### E1: EventBus 🔴

**概要**: MCPツール・Plugin・WebUIチャット間のpub/sub基盤。全てのイベントを疎結合に接続。

```python
class EventBus:
    async def publish(event_type: str, data: dict) -> None
    def subscribe(event_type: str, handler: Callable) -> None
```

**イベント種別**:

| イベント | 発行元 | 購読者 |
|----------|--------|--------|
| `memory.created` | MCP `memory_create` | SSE Broadcaster → WebUI, SessionEventRecorder |
| `memory.updated` | MCP `memory_update` | SSE → WebUI |
| `memory.deleted` | MCP `memory_delete` | SSE → WebUI |
| `context.updated` | MCP `update_context` | SSE → WebUI |
| `tool.called` | 全MCPツール | SessionEventRecorder |
| `chat.message` | WebUI chatSend() | SessionEventRecorder |
| `chat.llm_response` | WebUI InferenceStep | SessionEventRecorder |
| `session.compact` | WebUI CompressStep | SessionEventRecorder |
| `session.started` | WebUI PrepareStep | SessionEventRecorder |
| `events.ingested` | HTTP API（Pluginから） | SessionEventRecorder, SSE |

**変更ファイル**: `application/event_bus.py`（新規）, `api/mcp/tools.py`（全ツールにpublish追加）

### E2: SSEエンドポイント 🔴

**エンドポイント**: `GET /api/events/{persona}?topics=memory,context,tool`

- Server-Sent Events でリアルタイム通知
- WebUIのJSが `EventSource` で購読
- **別PCからのMCP操作もSSE経由で即座にWebUIに反映される**

**変更ファイル**: `api/http/routers/events.py`（新規）, `api/http/sections/chat.py`（JS側EventSource追加）

### E3: Plugin用HTTP取り込みAPI 🔴

**エンドポイント**: `POST /api/events/ingest`

- OpenCode Pluginから受け取ったイベントをEventBusに流す
- `{events: [{type, summary, detail, metadata, timestamp}, ...], session_id, persona}`

**変更ファイル**: `api/http/routers/events.py`

---

## L3: OpenCode Plugin（TypeScript、新規）

### P1: プラグイン本体 🔴

**場所**: MemoryMCPリポジトリ内 `plugins/opencode-memory-sync/`

OpenCodeのプラグインAPIを使って、セッション中の全アクティビティを捕捉しMemoryMCPにHTTP POSTする。
**責務はイベント捕捉のみ**。ツール定義はMCP側が持つので二重管理にならない。

**フック**:

| フック | 捕捉するもの | HTTP送信先 |
|--------|-------------|-----------|
| `PreToolUse` | 全ツール呼出（ツール名+パラメータ要約） | `POST /api/events/ingest` |
| `PostToolUse` | ツール結果（成功/失敗、要約） | 同上 |
| `SessionStart` | セッション開始 | 同上 |
| `Stop` | セッション終了＋要約生成リクエスト | 同上 |
| `PreCompact` | 圧縮前スナップショット（現在のコンテキスト要約） | 同上 |

**コード量見込み**: ~80-100行

### P2: 将来の他プラットフォーム展開

OpenCode Pluginと同じ責務（イベント捕捉→HTTP POST）を各プラットフォームのフックAPIで実装するだけ。
1プラットフォームあたり ~50-100行。

---

## 優先順位と依存グラフ

```
L2: E1(EventBus) ──── 最優先。全レイヤーの基盤
├── L2: E2(SSE) ── E1に依存
├── L2: E3(Plugin API) ── E1に依存
│
├── L1: M1(FTS5) ── 依存なし、E1と並行可
│   └── L1: M4(近接性) ── M1に依存
├── L1: M2(ingest) ── 依存なし、並行可
├── L1: M3(batch) ── 依存なし、並行可
├── L1: M5+M6 ── 独立、低優先
│
├── L3: P1(Plugin) ── E3に依存（POST先が必要）
│
└── WebUI: SSE受信 ── E2に依存
```

**最初の一手**: E1, E2, E3, M1, M2, M3 の6つは同時に着手できる。
**L3(P1)** はE3ができてから。

### 制約
- 既存MCPツール名・シグネチャは変更しない（後方互換）
- 新規追加ツールは新しい名前で（`ingest`, `batch`, `doctor`, `upgrade`）
- DBマイグレーション番号: v023（FTS5）, v024（session_events）
- OpenCode PluginはMemoryMCPリポジトリ内 `plugins/` サブディレクトリに配置

---

## 過去のプラン（履歴）

以下は過去の開発フェーズ。完了済みまたは棚卸し済み。

<details>
<summary>2026-05-16 MCPツール統合（完了）</summary>

- sandbox_image → sandbox_files 統合 ✅
- MCPツール flat名再編（20ツール）✅
- goal/promise 6→2ツール ✅
- エンティティ・矛盾・メンタルモデルをLLMツールから削除 ✅
- docstring圧縮 ✅
- builtin.py と MCP tools.py 統合 ✅

</details>

<details>
<summary>2026-05-16 大規模リファクタ（棚卸し）</summary>

- 多次元感情対応・auto-snapshot・body_state追加
- WebUI感情/身体状態追従
- テスト再構築

</details>

<details>
<summary>2026-05-17 実運用フィードバック（棚卸し）</summary>

- 感情モデルロールバック（未着手）
- 身体状態減衰修正（未着手）
- Goal/Promiseライフサイクル改善（未着手）
- WebUI Action廃止（未着手）
- Itemツールbuiltin対応（未着手）
- Skills DB定期更新（未着手）
- Speech更新促進（未着手）

</details>
