# Memory MCP Server

[![CI](https://github.com/solidlime/MemoryMCP/actions/workflows/ci.yml/badge.svg)](https://github.com/solidlime/MemoryMCP/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)

FastMCP準拠の永続メモリサーバー。LLMエージェントのためのPersona別記憶管理を、Clean Architecture + DDDで実現する。

## ✨ 主要機能

- 🧠 **永続メモリ** — SQLite + Qdrant による構造化データとベクトルの二重管理
- 👤 **Persona分離** — マルチテナント対応。Personaごとに独立したDB・ベクトルコレクション
- 🔍 **ハイブリッドRAG検索** — Semantic / Keyword / Hybrid（RRF統合）の3モード
- 📉 **Ebbinghaus忘却曲線** — `R(t) = e^(-t/S)` に基づく自然な記憶減衰とリコール強化
- 🕒 **Bi-temporal状態管理** — ユーザー情報の変更履歴を完全保持（任意時点で参照可能）
- 🔄 **矛盾検出** — ベクトル類似度ベースで既存記憶との矛盾を自動検出
- 📜 **記憶バージョニング** — 編集履歴の保持とロールバック
- 🕸️ **エンティティグラフ** — 人物・場所・概念の関係性をグラフ構造で管理
- 📦 **日本語特化モデル** — ruri-v3-30m（埋め込み）+ japanese-reranker（リランク）
- 🐳 **Docker対応** — Docker Compose によるワンコマンドデプロイ + GitHub Actions CI/CD
- 📊 **Webダッシュボード** — 記憶の統計・推移・知識グラフをブラウザで可視化
- 🔧 **CLIツール** — import / export / migrate / stats をコマンドラインで実行

## 🏗️ アーキテクチャ

Clean Architecture + DDD に基づくレイヤー構成：

```
┌───────────────────────────────────────────────────────────┐
│                      API Layer                            │
│   api/mcp/  ── 5つのMCPツール（get_context, memory, ...） │
├───────────────────────────────────────────────────────────┤
│                  Application Layer                        │
│   application/  ── UseCases（ビジネスフロー制御）          │
├───────────────────────────────────────────────────────────┤
│                    Domain Layer                           │
│   domain/memory/     ── Memory, MemoryStrength, Search    │
│   domain/persona/    ── PersonaState管理                  │
│   domain/equipment/  ── アイテム・装備                     │
│   domain/search/     ── SearchEngine, Ranker, Strategies  │
├───────────────────────────────────────────────────────────┤
│                 Infrastructure Layer                      │
│   infrastructure/sqlite/     ── SQLite Repository実装     │
│   infrastructure/qdrant/     ── ベクトルストア             │
│   infrastructure/embedding/  ── 埋め込みモデル            │
└───────────────────────────────────────────────────────────┘
```

### ディレクトリ構成

```
memory_mcp/
├── main.py              # エントリポイント（FastMCP + HTTP）
├── config/settings.py   # Pydantic BaseSettings
├── domain/              # ドメイン層（ビジネスロジック）
│   ├── memory/          # Memory, MemoryStrength, Search
│   ├── persona/         # PersonaState管理
│   ├── equipment/       # アイテム・装備
│   └── search/          # SearchEngine, Ranker, Strategies
├── infrastructure/      # インフラ層
│   ├── sqlite/          # SQLite Repository実装
│   ├── qdrant/          # ベクトルストア
│   └── embedding/       # 埋め込みモデル
├── application/         # アプリケーション層（UseCases）
├── api/mcp/             # MCP API層（ツール5本）
├── migration/           # スキーママイグレーション + インポーター
└── cli/                 # CLIツール
```

## 🚀 クイックスタート

### pip でインストール

```bash
# クローン
git clone https://github.com/solidlime/MemoryMCP.git
cd MemoryMCP

# Qdrant起動
docker compose up -d

# 依存関係インストール（CPU版PyTorch）
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# サーバー起動
python -m memory_mcp.main
```

サーバーは `http://localhost:26262` で起動する。

### Docker で起動

```bash
# Docker Compose（推奨）
docker compose up -d

# または直接実行
docker run -d -p 26262:26262 -v ./data:/app/data ghcr.io/solidlime/memorymcp:latest
```

### MCP クライアント設定例

```json
{
  "mcpServers": {
    "memory": {
      "url": "http://localhost:26262/mcp",
      "headers": {
        "Authorization": "Bearer <persona_name>"
      }
    }
  }
}
```

## 🔧 MCPツールAPI

5つのツールで全機能にアクセスする。

### `get_context()`

Persona状態・時刻・メモリ統計のサマリーを取得。セッション開始時に最初に呼ぶ。

```python
result = get_context()
# → persona, emotion, physical_state, recent_memories, promises, goals ...
```

### `memory(operation, ...)`

記憶の作成・読み取り・更新・削除、および矛盾検出・バージョニング・エンティティグラフ操作。

| operation | 説明 |
|-----------|------|
| `create` | 記憶を作成（感情・重要度・タグ付き） |
| `read` | 指定IDの記憶を読み取り |
| `update` | 既存記憶を更新（バージョン履歴あり） |
| `delete` | 記憶を削除 |
| `stats` | メモリ統計を取得 |
| `check_routines` | ルーティンパターンを検出 |
| `check_contradictions` | 既存記憶との矛盾を検出 |
| `history` | 記憶の編集履歴を取得 |
| `entity_search` | エンティティ（人物・場所）を検索 |
| `entity_graph` | エンティティの関係性グラフを取得 |
| `entity_add_relation` | エンティティ間の関係を追加 |

```python
# 記憶を作成
memory(operation="create", content="ユーザーは苺が好き",
       emotion_type="joy", importance=0.8)

# 矛盾を検出
memory(operation="check_contradictions", content="ユーザーはいちごが嫌い")

# 編集履歴を取得
memory(operation="history", memory_key="memory_20250101_120000")

# エンティティグラフ
memory(operation="entity_graph", query="田中さん")
```

### `search_memory(query, ...)`

ハイブリッド検索エンジン。3つのモードを使い分ける。

```python
# セマンティック検索
search_memory(query="好きな食べ物", mode="semantic")

# キーワード検索
search_memory(query="苺 ケーキ", mode="keyword")

# ハイブリッド検索（デフォルト・推奨）
search_memory(query="最近の出来事", mode="hybrid", top_k=10)

# 時間フィルタ付き
search_memory(query="成果", date_range="先週")
```

### `update_context(...)`

感情・状態・ユーザー情報をリアルタイム更新。

```python
# 感情更新
update_context(emotion_type="joy", emotion_intensity=0.8)

# 状態更新
update_context(physical_state="tired", mental_state="focused")

# ユーザー情報更新（Bi-temporal）
update_context(user_info={"name": "太郎", "preferred_address": "太郎さん"})
```

### `item(operation, ...)`

アイテム・装備の管理。

```python
# アイテム追加
item(operation="add", item_name="白いドレス", category="clothing")

# 装備
item(operation="equip", equipment={"top": "白いドレス", "accessories": "花の髪飾り"})

# 装備解除
item(operation="unequip", slots=["top"])

# アイテム検索
item(operation="search", category="clothing")
```

## 🔍 検索機能

### 検索モード

| モード | エンジン | 説明 |
|--------|----------|------|
| `semantic` | Qdrantベクトル検索 | 意味的に類似した記憶を検索。曖昧・抽象的なクエリに強い |
| `keyword` | SQLite LIKE + RapidFuzz | 単語の完全・部分一致検索。固有名詞・IDの検索に強い |
| `hybrid` | RRF統合 | Reciprocal Rank Fusionで両エンジンのランクを統合（**デフォルト**） |

### 自然言語時間フィルタリング

`date_range` パラメータで自然言語の時間表現をサポート：

| 表現 | 例 |
|------|-----|
| 相対日 | `今日` `昨日` `一昨日` `3日前` `N日前` |
| 相対週 | `先週` `N週間前` |
| 相対月 | `先月` `今月` `N月前` `半年前` |
| その他 | `今年` `N時間前` |

```python
search_memory(query="", date_range="今日")
search_memory(query="成果", date_range="先週")
search_memory(query="", date_range="3日前")
```

## ⚙️ 設定

すべての設定は環境変数（`MEMORY_MCP_` プレフィックス）で制御する。Pydantic BaseSettings によるバリデーション付き。

| 環境変数 | デフォルト | 説明 |
|----------|-----------|------|
| `MEMORY_MCP_PORT` | `26262` | サーバーポート |
| `MEMORY_MCP_HOST` | `0.0.0.0` | バインドアドレス |
| `MEMORY_MCP_QDRANT__URL` | `http://localhost:6333` | Qdrant接続先 |
| `MEMORY_MCP_EMBEDDING__MODEL` | `cl-nagoya/ruri-v3-30m` | 埋め込みモデル |
| `MEMORY_MCP_RERANKER__MODEL` | `hotchpotch/japanese-reranker-xsmall-v2` | Rerankerモデル |
| `MEMORY_MCP_TIMEZONE` | `Asia/Tokyo` | タイムゾーン |
| `MEMORY_MCP_DATA_DIR` | `./data` | データディレクトリ |
| `MEMORY_MCP_LOG_LEVEL` | `INFO` | ログレベル |
| `PERSONA` | *(なし)* | デフォルトPersona名 |

Persona識別は Bearerトークン（`Authorization: Bearer <name>`）または `PERSONA` 環境変数で行う。

## 🧪 テスト

```bash
# 全テスト実行（285テスト）
python -m pytest tests/ -q

# ユニットテストのみ
python -m pytest tests/unit/ -q

# E2Eドッグフーディングテスト
python -m pytest tests/e2e/ -q

# カバレッジレポート付き
python -m pytest tests/ --cov=memory_mcp --cov-report=html
```

## 📦 CLIツール

```bash
# 旧データインポート
python -m memory_mcp.cli import --persona herta --input data/herta.zip

# エクスポート
python -m memory_mcp.cli export --persona herta --output backup.jsonl

# スキーママイグレーション
python -m memory_mcp.cli migrate --target latest

# Persona統計
python -m memory_mcp.cli stats --persona herta
```

## 🐳 Docker

### Docker Compose（推奨）

```bash
docker compose up -d
```

`docker-compose.yml` に Memory MCP Server + Qdrant が含まれる。データは `./data` にマウントされる。

### 手動実行

```bash
docker run -d \
  -p 26262:26262 \
  -v ./data:/app/data \
  ghcr.io/solidlime/memorymcp:latest
```

### CI/CD パイプライン

| ワークフロー | トリガー | 内容 |
|-------------|---------|------|
| `ci.yml` | push / PR | テスト + Lint（ruff） |
| `docker.yml` | タグ push | Docker イメージビルド → GHCR |
| `e2e.yml` | 週次 + 手動 | E2Eドッグフーディングテスト |

## 📖 開発者向け情報

### 技術スタック

| カテゴリ | 技術 |
|---------|------|
| 言語 | Python 3.12+ |
| MCPフレームワーク | FastMCP |
| データベース | SQLite（WALモード） |
| ベクトルストア | Qdrant |
| 設定/バリデーション | Pydantic v2 (BaseSettings) |
| 埋め込みモデル | cl-nagoya/ruri-v3-30m（日本語特化） |
| Reranker | hotchpotch/japanese-reranker-xsmall-v2 |
| ロギング | structlog |
| テスト | pytest（285テスト） |
| Linter/Formatter | ruff |
| コンテナ | Docker + GitHub Actions |

### 設計原則

- **Clean Architecture** — 依存方向は外側→内側の一方向。ドメイン層は外部に依存しない
- **DDD** — ドメインモデルがビジネスロジックを集約。Repository パターンでインフラを抽象化
- **Persona分離** — Personaごとに独立したSQLiteファイルとQdrantコレクションを持つ
- **ステートレスHTTP** — `stateless_http=True` で起動。全状態はSQLiteに永続化

## 📝 ライセンス

MIT License — 詳細は [LICENSE](LICENSE) を参照。

## 🙏 謝辞

- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Qdrant](https://qdrant.tech/)
- [Sentence Transformers](https://www.sbert.net/)
- [cl-nagoya/ruri-v3-30m](https://huggingface.co/cl-nagoya/ruri-v3-30m)
- [hotchpotch/japanese-reranker-xsmall-v2](https://huggingface.co/hotchpotch/japanese-reranker-xsmall-v2)

---

**Memory MCP Server** — Built by [solidlime](https://github.com/solidlime) with ❤️
