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

## MCP ツール（5 本）

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

```python
# 記憶を作成
memory(operation="create", content="ユーザーは苺が好き", importance=0.8, emotion_type="joy")

# Block に書き込み
memory(operation="block_write", block_name="user_model", content="Pythonエンジニア、簡潔な説明を好む")

# エンティティグラフ
memory(operation="entity_graph", entity_id="user_tanaka", depth=2)
```

### `search_memory(query, mode="hybrid", top_k=5, ...)`

ハイブリッド検索エンジン。

| mode | 説明 |
|---|---|
| `hybrid` | キーワード + 意味検索の RRF 統合（**デフォルト・推奨**） |
| `semantic` | Qdrant ベクトル検索（意味的に曖昧なクエリに強い） |
| `keyword` | SQLite FTS + RapidFuzz（固有名詞・ID 検索に強い） |
| `smart` | hybrid + クエリ自動拡張 |

```python
# ハイブリッド検索（デフォルト）
search_memory(query="最近の出来事", mode="hybrid", top_k=10)

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
│   api/mcp/  ── 5 つの MCP ツール                          │
│   api/http/ ── Web ダッシュボード + REST API              │
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
├── infrastructure/      # SQLite / Qdrant / Embedding
├── application/         # UseCases
├── api/mcp/             # MCP ツール 5 本
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
