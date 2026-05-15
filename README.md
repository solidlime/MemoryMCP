# MemoryMCP

> 日本語特化の永続記憶 MCP サーバー — SQLite + Qdrant + Ebbinghaus 忘却曲線

[![CI](https://github.com/solidlime/MemoryMCP/actions/workflows/ci.yml/badge.svg)](https://github.com/solidlime/MemoryMCP/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)

## 特徴

- **ハイブリッド検索** — Semantic / Keyword / Hybrid（RRF 統合）/ Smart の 4 モード
- **Ebbinghaus 忘却曲線** — `R(t) = e^(-t/S)` に基づく自動重要度減衰とリコール強化
- **Core Memory Blocks** — 常に `get_context()` に注入される高優先度コンテキスト（MCP + HTTP API）
- **エンティティグラフ** — 人物・場所・概念の関係性を知識グラフで管理
- **Bi-temporal 状態管理** — ユーザー情報の変更履歴を完全保持
- **矛盾検出** — ベクトル類似度ベースで既存記憶との矛盾を自動検出
- **Persona 分離** — マルチテナント対応。Persona ごとに独立した DB・ベクトルコレクション
- **Web ダッシュボード** — `http://localhost:26262` でブラウザから記憶・グラフ・統計を可視化
- 🔮 **Reflection (リフレクション)**: LLM-driven high-level insights from recent memories (Generative Agents style). Auto-triggered by importance accumulation. Configurable threshold & interval.
- 🧠 **Mental Model (メンタルモデル)**: Pattern abstraction from accumulated type-tagged memories. Detects repeated patterns (e.g. "user drinks coffee every morning") and creates abstracted models. Auto-triggered by memory count per type.
- ⚡ **Sandbox Code Execution**: Execute Python/Bash code in isolated Docker containers (sibling-container mode). Supports file operations, package installs. Requires Docker socket mount.
- 🔍 **Memory Enrichment**: Auto-evaluate importance scores and extract entity relations via LLM when memories are created. Configurable provider/model.
- 🧩 **MemoRAG**: Memory Context Snapshot + Clue Generation for enhanced retrieval (query expansion from global context).

## クイックスタート

### Docker（推奨）

```bash
docker-compose up -d
```

`docker-compose.yml` に Memory MCP Server + Qdrant が含まれる。データは `./data` にマウントされる。

### ローカル開発

```bash
# Qdrant 起動
docker run -d -p 6333:6333 -v "$(pwd)/data/qdrant:/qdrant/storage" qdrant/qdrant

# 依存関係（CPU 版 torch）
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# サーバー起動
python -m memory_mcp.main
```

サーバーは `http://localhost:26262` で起動する。

### Sandbox File Persistence

When running in Docker with sibling-container sandbox mode, files created inside the sandbox
at `/sandbox` need a host-side path to persist. If files are not visible on the host:

1. **Set `MEMORY_MCP_SANDBOX__HOST_DATA_ROOT`** to the host-side data path:
   ```yaml
   # docker-compose.yml
   environment:
     MEMORY_MCP_SANDBOX__HOST_DATA_ROOT: /volume1/docker/MemoryMCP/data
   ```

2. **Ensure `docker` Python SDK** is installed (`pip install docker>=7.0.0`)

3. **Verify Docker socket** is mounted: `/var/run/docker.sock:/var/run/docker.sock`

Auto-detection of the host path works in standard Docker setups but may fail
on custom deployments (Synology, Podman, etc.).

## MCP ツール（6 本）

MCP サーバー（`/mcp` エンドポイント）経由で LLM に露出されるツール群。

### `get_context()`

現在のペルソナ状態・記憶サマリー・装備・感情・Block・約束・目標を一括返却する。セッション開始時に最初に呼ぶ。

```python
result = get_context()
# → persona, emotion, physical_state, equipment, blocks, recent_memories, promises, goals, stats ...
```

### `memory(operation, ...)`

記憶の CRUD・矛盾検出・バージョニング・Core Memory Blocks・エンティティグラフ操作。

| operation | 説明 |
|---|---|
| `create` | 記憶を作成（感情・重要度・タグ付き） |
| `read` | 指定 key の記憶を取得 |
| `update` | 既存記憶を更新（バージョン履歴あり） |
| `delete` | 記憶を削除 |
| `check_contradictions` | 既存記憶との矛盾を検出 |
| `history` | 記憶の編集履歴を取得 |
| `stats` | メモリ統計を取得 |
| `block_write` | Core Memory Block を書き込み |
| `block_read` | Block を読み取り |
| `block_list` | Block 一覧を取得 |
| `block_delete` | Block を削除 |
| `entity_search` | エンティティ（人物・場所・概念）を検索 |
| `entity_graph` | エンティティの関係性グラフを取得 |
| `entity_add_relation` | エンティティ間の関係を追加 |
| `enrich` | 既存記憶の LLM 補完（重要度再評価 + エンティティ関係抽出）を再実行 |
| `run_mental_model` | メンタルモデル抽象化を手動トリガー |
| `refresh_context_snapshot` | グローバルコンテキストスナップショットを再構築 |

```python
# 記憶を作成
memory(operation="create", content="ユーザーは苺が好き", importance=0.8, emotion_type="joy")

# Block に書き込み
memory(operation="block_write", block_name="user_model", content="Pythonエンジニア、簡潔な説明を好む")

# エンティティグラフ
memory(operation="entity_graph", entity_id="user_tanaka", depth=2)
```

### `search_memory(query, top_k=5, ...)`

ハイブリッド検索エンジン（常に keyword + semantic の RRF 統合）。

```python
# ハイブリッド検索（デフォルト）
search_memory(query="最近の出来事", top_k=10)

# 日付フィルタ付き（自然言語）
search_memory(query="成果", date_range="先週")

# 重要度ブースト
search_memory(query="ユーザー情報", importance_weight=0.3, min_importance=0.6)
```

**`date_range` 表現例**: `今日` `昨日` `先週` `先月` `3日前` `7d` `2025-01-01~2025-06-01`

### `update_context(...)`

感情・状態・ユーザー情報をリアルタイム更新。`user_info` の変更は Bi-temporal で履歴保持される。

```python
update_context(emotion="joy", emotion_intensity=0.8)
update_context(physical_state="tired", mental_state="focused", environment="home office")
update_context(user_info={"name": "太郎", "preferred_address": "太郎さん"})
```

| パラメータ | 説明 |
|---|---|
| `emotion` / `emotion_intensity` | 感情タイプと強度（0.0–1.0） |
| `physical_state` / `mental_state` | 身体的・精神的状態 |
| `environment` | 現在の環境（例: `"home office"`） |
| `user_info` | `name` / `nickname` / `preferred_address` の辞書 |
| `persona_info` | ペルソナ自身の情報（`nickname`, `active_promises` 等） |
| `fatigue` / `warmth` / `arousal` | 身体感覚（0.0–1.0）|
| `speech_style` | 発話スタイル（例: `"甘えた口調"`） |

### `item(operation, ...)`

アイテム・装備の管理。**物理アイテムのみ**対象。

| operation | 説明 |
|---|---|
| `add` | アイテムを追加 |
| `remove` | アイテムを削除 |
| `equip` | 装備スロットを設定（`top/bottom/shoes/outer/accessories/head`） |
| `unequip` | 指定スロットを解除 |
| `update` | アイテム情報を更新（wet/dirty 等） |
| `search` | アイテムを検索（`query` or `category`） |
| `history` | 装備変更履歴を取得 |

```python
item(operation="equip", equipment={"top": "白いドレス", "accessories": "花の髪飾り"})
item(operation="search", category="clothing")
```

### `sandbox(code, language="python")`

Execute code in an isolated Docker sandbox (sibling-container mode). Requires Docker socket mount.

| パラメータ | 説明 |
|---|---|
| `code` | 実行するコード文字列（Python / Bash） |
| `language` | 言語: `"python"`（デフォルト）または `"bash"` |

```python
# Python コード実行
sandbox("import pandas as pd; print(pd.DataFrame({'a': [1,2,3]}))")

# Bash コマンド実行
sandbox("ls -la /sandbox/", language="bash")

# パッケージインストール
sandbox("import subprocess; subprocess.run(['pip', 'install', 'requests'], capture_output=True)")

# ファイル作成（/sandbox 以下は永続化可能）
sandbox("open('/sandbox/output/result.txt', 'w').write('hello')")
```

## WebUI チャット組み込みツール（15 本）

WebUI チャット（`/chat/{persona}`）で LLM に注入されるビルトインツール。MCP ツールの簡易ラッパー + サンドボックス専用ツールで構成。

### メモリ操作（12 本）

| ツール名 | 説明 | 対応 MCP |
|---|---|---|
| `memory_create` | 記憶を作成（content, importance, tags, emotion_type） | `memory(operation="create")` |
| `memory_search` | 記憶を検索（query, top_k=1〜200） | `search_memory()` |
| `memory_update` | 既存記憶を更新（query → 検索 → 上書き） | `memory(operation="update")` |
| `context_update` | 感情・状態を更新（emotion, mental_state） | `update_context()` |
| `context_recall` | タグ指定で記憶を取得（tags, top_k） | `search_memory(tags=...)` |
| `goal_create` | 目標を作成（content, importance=0.75） | `memory(tags=["goal","active"])` |
| `goal_achieve` | 目標を達成（content 部分一致） | `memory(operation="update", tags=["goal","achieved"])` |
| `goal_cancel` | 目標をキャンセル | `memory(operation="update", tags=["goal","cancelled"])` |
| `promise_create` | 約束を記録（content, importance=0.8） | `memory(tags=["promise","active"])` |
| `promise_fulfill` | 約束を遂行 | `memory(operation="update", tags=["promise","fulfilled"])` |
| `promise_cancel` | 約束をキャンセル | `memory(operation="update", tags=["promise","cancelled"])` |
| `invoke_skill` | スキルを独立コンテキストで実行 | （Builtin 専用） |

### サンドボックス操作（3 本）

| ツール名 | 説明 | 対応 MCP |
|---|---|---|
| `execute_code` | コード実行（Python/Bash、matplotlib 画像自動表示） | `sandbox()` |
| `sandbox_files` | ファイル操作（list/read/write/delete、画像は自動 base64） | （Builtin 専用） |
| `sandbox_image` | 画像ファイルの表示・分析（PIL リサイズ + マジックバイト検出） | （Builtin 専用） |

### MCP ↔ Builtin 対応表

| 機能 | MCP ツール | Builtin ツール | 備考 |
|---|---|---|---|
| 記憶 CRUD | `memory(operation=...)` | `memory_create/update` | Builtin は簡易ラッパー |
| 検索 | `search_memory()` | `memory_search/context_recall` | Builtin は上限200件 |
| 状態更新 | `update_context()` | `context_update` | Builtin は感情・状態のみ |
| Goal 管理 | `memory(tags=["goal"])` | `goal_create/achieve/cancel` | Builtin はタグ自動付与 |
| Promise 管理 | `memory(tags=["promise"])` | `promise_create/fulfill/cancel` | Builtin はタグ自動付与 |
| コード実行 | `sandbox()` | `execute_code/sandbox_files/sandbox_image` | Builtin は 3 ツールに分割 |
| エンティティグラフ | `memory(entity_*)` | — | MCP 専用 |
| 矛盾検出 | `memory(check_contradictions)` | — | MCP 専用 |
| メンタルモデル | `memory(run_mental_model)` | — | MCP 専用 |
| 会話インポート | `memory(import_conversation)` | — | MCP 専用 |
| アイテム管理 | `item()` | — | MCP 専用 |
| スキル実行 | — | `invoke_skill` | Builtin 専用 |

## 設定

すべての設定は環境変数（`MEMORY_MCP_` プレフィックス）で制御する。ネストした設定は `__` 区切りで指定する。

| 環境変数 | デフォルト | 説明 |
|---|---|---|
| `MEMORY_MCP_DATA_ROOT` | `./data` | データ保存先（全サブパスを自動導出） |
| `MEMORY_MCP_SERVER__PORT` | `26262` | HTTP ポート |
| `MEMORY_MCP_SERVER__HOST` | `0.0.0.0` | バインドアドレス |
| `MEMORY_MCP_QDRANT__URL` | `http://localhost:6333` | Qdrant 接続先 |
| `MEMORY_MCP_EMBEDDING__MODEL` | `cl-nagoya/ruri-v3-30m` | 埋め込みモデル |
| `MEMORY_MCP_RERANKER__MODEL` | `hotchpotch/japanese-reranker-xsmall-v2` | Reranker モデル |
| `MEMORY_MCP_TIMEZONE` | `Asia/Tokyo` | タイムゾーン |
| `MEMORY_MCP_LOG_LEVEL` | `INFO` | ログレベル |
| `MEMORY_MCP_DEFAULT_PERSONA` | `default` | デフォルト Persona 名 |
| `PERSONA` | *(なし)* | デフォルト Persona 名（`MEMORY_MCP_DEFAULT_PERSONA` より優先） |
| `MEMORY_MCP_SANDBOX__ENABLED` | `true` | Sandbox コード実行を有効化 |
| `MEMORY_MCP_SANDBOX__PROVIDER` | `llm_sandbox` | Sandbox プロバイダー |
| `MEMORY_MCP_SANDBOX__DOCKER_HOST` | *(auto)* | Docker ホスト URL（空 = ソケット自動検出） |
| `MEMORY_MCP_SANDBOX__HOST_DATA_ROOT` | *(auto)* | ホスト側データディレクトリ絶対パス（sibling-container 永続化用） |
| `MEMORY_MCP_SANDBOX__TIMEOUT` | `30` | コード実行タイムアウト（秒） |
| `MEMORY_MCP_MEMORY_ENRICHMENT__ENABLED` | `true` | 記憶作成時の LLM 補完（重要度・関係抽出）を有効化 |
| `MEMORY_MCP_MEMORY_ENRICHMENT__PROVIDER` | `openrouter` | LLM プロバイダー |
| `MEMORY_MCP_MEMORY_ENRICHMENT__API_KEY` | *(なし)* | LLM API キー |
| `MEMORY_MCP_MEMORY_ENRICHMENT__MODEL` | `openai/gpt-4o-mini` | LLM モデル |
| `MEMORY_MCP_MEMORY_ENRICHMENT__BASE_URL` | `https://openrouter.ai/api/v1` | LLM API ベース URL |
| `MEMORY_MCP_MEMORY_ENRICHMENT__MIN_CHARS` | `10` | 補完をスキップする最小文字数 |
| `MEMORY_MCP_MEMORAG__ENABLED` | `true` | MemoRAG コンテキストスナップショットを有効化 |
| `MEMORY_MCP_MEMORAG__CLUE_GENERATION_ENABLED` | `false` | LLM ベースのクエリ手がかり生成を有効化 |
| `MEMORY_MCP_FORGETTING__ENABLED` | `true` | Ebbinghaus 忘却曲線を有効化 |
| `MEMORY_MCP_FORGETTING__DECAY_INTERVAL_SECONDS` | `3600` | 減衰ワーカー実行間隔（秒） |
| `MEMORY_MCP_FORGETTING__MIN_STRENGTH` | `0.01` | 最小記憶強度 |

### Persona 識別の優先順位

| 優先順位 | 方法 | 例 |
|---|---|---|
| 1 | Bearer トークン | `Authorization: Bearer herta` |
| 2 | X-Persona ヘッダー | `X-Persona: herta` |
| 3 | 環境変数 | `PERSONA=herta` / `MEMORY_MCP_DEFAULT_PERSONA=herta` |
| 4 | デフォルト | `"default"` |

## Claude Desktop 設定

```json
{
  "mcpServers": {
    "memory": {
      "url": "http://localhost:26262/mcp",
      "headers": {
        "X-Persona": "your_name"
      }
    }
  }
}
```

## アーキテクチャ

Clean Architecture + DDD に基づくレイヤー構成：

```
┌───────────────────────────────────────────────────────────┐
│                      API Layer                            │
│   api/mcp/  ── 6 つの MCP ツール                          │
│   api/http/ ── Web ダッシュボード + REST API + 15 ビルトインツール │
├───────────────────────────────────────────────────────────┤
│                  Application Layer                        │
│   application/  ── UseCases（ビジネスフロー制御）          │
├───────────────────────────────────────────────────────────┤
│                    Domain Layer                           │
│   domain/memory/     ── Memory, MemoryStrength, Search    │
│   domain/persona/    ── PersonaState 管理                 │
│   domain/equipment/  ── アイテム・装備                     │
│   domain/search/     ── SearchEngine, Ranker, Strategies  │
├───────────────────────────────────────────────────────────┤
│                 Infrastructure Layer                      │
│   infrastructure/sqlite/     ── SQLite Repository 実装    │
│   infrastructure/qdrant/     ── ベクトルストア             │
│   infrastructure/embedding/  ── 埋め込みモデル            │
└───────────────────────────────────────────────────────────┘
```

### ディレクトリ構成

```
memory_mcp/
├── main.py              # エントリポイント（FastMCP + HTTP）
├── config/settings.py   # Pydantic BaseSettings
├── domain/              # ビジネスロジック
│   ├── skill.py              # Skills system
│   └── shared/
│       └── time_utils.py     # 日付範囲パース、時刻ユーティリティ
├── infrastructure/      # SQLite / Qdrant / Embedding
├── application/         # UseCases
│   ├── chat/            # チャットサブパッケージ
│   │   ├── service.py             # ChatService（SSEストリーミング）
│   │   ├── session_store.py       # セッション管理（SQLite永続化）
│   │   ├── memory_llm.py          # MemoryLLM（自動記憶抽出）
│   │   ├── pattern_detector.py    # メンタルモデル抽象化
│   │   ├── summarizer.py          # セッション要約（LLM）
│   │   └── tools/                 # 組み込みツール定義・実行
│   │       ├── definitions.py     # 15 ツールのスキーマ定義
│   │       └── builtin.py         # ツール実装
│   ├── sandbox/          # Sandbox コード実行（Docker sibling-container）
│   └── chat_service.py   # 後方互換 re-export
├── api/mcp/             # MCP ツール 6 本
├── api/http/            # Web ダッシュボード + REST API
└── migration/           # スキーママイグレーション
```

### データディレクトリ

```
$MEMORY_MCP_DATA_ROOT/     # デフォルト: ./data（Docker: /data）
├── memory/{persona}/      # Persona 別 DB（memory.sqlite 等）
├── import/                # Auto-import 用 ZIP 配置ディレクトリ
│   └── done/              # 処理済み ZIP 移動先
├── cache/                 # モデルキャッシュ（HF_HOME 等を自動設定）
└── config/                # 設定ファイル
```

## チャット機能

WebUI（`http://localhost:26262/chat/{persona}`）またはREST APIで、ペルソナとリアルタイムチャットができる。

### SSE API

```
POST /api/chat/{persona}
Content-Type: application/json

{"message": "こんにちは", "session_id": "my-session"}
```

レスポンスは SSE ストリーム。以下のイベントが流れる：

| イベント | 説明 |
|---|---|
| `text_delta` | LLM テキストの増分 |
| `tool_call` | ツール呼び出し |
| `tool_result` | ツール実行結果 |
| `debug_info` | セッション・記憶・MemoryLLM結果などのデバッグ情報 |
| `done` | 完了 |

### チャット設定

`GET/POST /api/chat/{persona}/config` でチャット設定を取得・更新する。

| フィールド | デフォルト | 説明 |
|---|---|---|
| `provider` | `anthropic` | LLMプロバイダー（`anthropic` / `openai` / `gemini`） |
| `model` | `claude-opus-4-5` | 使用モデル |
| `api_key` | *(なし)* | APIキー（保存後はマスク表示） |
| `system_prompt` | *(なし)* | ペルソナのシステムプロンプト |
| `auto_extract` | `true` | MemoryLLMによる自動記憶抽出 |
| `extract_model` | *(model と同じ)* | MemoryLLM専用モデル |
| `extract_max_tokens` | `512` | MemoryLLMの最大トークン数 |
| `max_window_turns` | `3` | 会話ウィンドウのターン数 |
| `max_tool_calls` | `5` | 1ターンの最大ツール呼び出し数 |
| `enable_memory_tools` | `true` | 組み込み memory ツールを注入するか |
| `mcp_servers` | `[]` | 追加 MCP サーバーの設定リスト |
| `enabled_skills` | `[]` | 有効化するスキル名のリスト |
| `reflection_enabled` | `true` | Reflection（高次洞察）を有効化 |
| `reflection_threshold` | `1.0` | Reflection トリガー重要度累積閾値 |
| `reflection_min_interval_hours` | `1.0` | Reflection 最小実行間隔（時間） |
| `mental_model_enabled` | `true` | メンタルモデル抽象化を有効化 |
| `mental_model_min_samples` | `3` | メンタルモデル生成に必要な最小サンプル数 |
| `sandbox_enabled` | `true` | コード実行（Docker Sandbox）を許可 |
| `debug_mode` | `false` | デバッグログ出力を有効化 |
| `retrieval_recency_weight` | `0.3` | 検索スコアの再近性重み |
| `retrieval_importance_weight` | `0.3` | 検索スコアの重要度重み |
| `retrieval_relevance_weight` | `0.4` | 検索スコアの関連性重み |

### チャットログ永続化

会話履歴は SQLite (`chat_sessions` テーブル) に自動保存される。サーバーを再起動しても `session_id` が同じであれば会話を継続できる。TTL（デフォルト7日）を超えたセッションは自動削除される。

### MemoryLLM（自動記憶抽出）

`auto_extract: true` の場合、各ターン終了後に MemoryLLM が非同期で起動し、会話から以下を自動抽出する：

- **facts**: ユーザーの好み・個人情報・約束・重要な出来事
- **context_update**: ペルソナの感情・状態変化
- **inventory_update**: 服・持ち物の変化

## テスト

```bash
# 全テスト実行
python -m pytest tests/ -q

# ユニットテストのみ
python -m pytest tests/unit/ -q

# カバレッジレポート付き
python -m pytest tests/ --cov=memory_mcp --cov-report=html
```

## CLI ツール

```bash
# インポート
python -m memory_mcp.cli import --persona herta --input data/herta.zip

# エクスポート
python -m memory_mcp.cli export --persona herta --output backup.jsonl

# スキーママイグレーション
python -m memory_mcp.cli migrate --target latest

# Persona 統計
python -m memory_mcp.cli stats --persona herta
```

## CI/CD

| ワークフロー | トリガー | 内容 |
|---|---|---|
| `ci.yml` | push / PR | テスト + Lint（ruff） |
| `docker.yml` | タグ push | Docker イメージビルド → GHCR |
| `e2e.yml` | 週次 + 手動 | E2E ドッグフーディングテスト |

## 技術スタック

| カテゴリ | 技術 |
|---|---|
| 言語 | Python 3.12+ |
| MCP フレームワーク | FastMCP |
| データベース | SQLite（WAL モード） |
| ベクトルストア | Qdrant |
| 設定/バリデーション | Pydantic v2 (BaseSettings) |
| 埋め込みモデル | cl-nagoya/ruri-v3-30m（日本語特化） |
| Reranker | hotchpotch/japanese-reranker-xsmall-v2 |
| ロギング | structlog |
| Linter/Formatter | ruff |

## ライセンス

MIT License — 詳細は [LICENSE](LICENSE) を参照。

## 謝辞

- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Qdrant](https://qdrant.tech/)
- [cl-nagoya/ruri-v3-30m](https://huggingface.co/cl-nagoya/ruri-v3-30m)
- [hotchpotch/japanese-reranker-xsmall-v2](https://huggingface.co/hotchpotch/japanese-reranker-xsmall-v2)

---

**MemoryMCP** — Built by [solidlime](https://github.com/solidlime) with ❤️
