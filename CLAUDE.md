# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Docker での起動（推奨）: memory-mcp + Qdrant を一括起動
docker-compose up -d

# 停止
docker-compose down

# ログ確認
docker-compose logs -f memory-mcp
docker-compose logs -f qdrant

# サーバー起動（ローカル開発時: Qdrant は別途起動が必要）
docker run -d -p 6333:6333 -v ./data/qdrant:/qdrant/storage qdrant/qdrant
python -m memory_mcp.main

# 全テスト実行（サーバーが localhost:26262 で起動中であること）
python run_tests.py

# 個別テスト
python run_tests.py --test http      # HTTP APIテスト
python run_tests.py --test search    # 検索精度テスト
python run_tests.py --test migrate   # DBスキーママイグレーション
python run_tests.py -v               # 詳細出力

# PyTorch CPU版（ローカル開発時のみ）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

## アーキテクチャ

### エントリポイント

`memory_mcp.main` が唯一のエントリポイント（`python -m memory_mcp.main`）。FastMCPサーバーとして起動し、HTTP API（port 26262）も同時に公開する。Persona識別はBearerトークン、X-Personaヘッダー、または環境変数（PERSONA / MEMORY_MCP_DEFAULT_PERSONA）で行う（優先順位: Bearer > X-Persona > 環境変数 > "default"）。

### レイヤー構成

```
memory_mcp/
├── main.py              # エントリポイント（FastMCP + HTTP）
├── config/settings.py   # Pydantic BaseSettings（MEMORY_MCP_DATA_ROOT → 全パス自動導出）
├── domain/              # ドメイン層（ビジネスロジック）
├── infrastructure/      # インフラ層（SQLite / Qdrant / Embedding）
├── application/         # アプリケーション層（UseCases）
├── api/mcp/             # MCP API層（ツール5本）
├── migration/           # スキーママイグレーション + インポーター
└── cli/                 # CLIツール
```

### 公開ツールAPI（3本のみ）

| ツール | 主なoperations |
|--------|---------------|
| `get_context()` | なし（状態サマリー返却） |
| `memory(operation, ...)` | `create / read / update / delete / search / stats / check_routines / update_context` |
| `item(operation, ...)` | `add / remove / equip / unequip / update / search / history / memories` |

`memory()` の検索モード: `semantic`（Qdrant）/ `keyword`（SQLite LIKE + RapidFuzz）/ `hybrid`（RRF統合）/ `smart`（クエリ自動拡張）

### 永続化

- **SQLite**: 記憶エントリ・ユーザー状態・装備・Personaコンテキスト（`{data_root}/memory/<persona>/`配下）
- **Qdrant**: ベクトルストア（`memory_<persona>` コレクション）
- **設定**: `memory_mcp/config/settings.py` の Pydantic BaseSettings で管理。環境変数 `MEMORY_MCP_*` プレフィックスで上書き可能。

### デフォルト設定値（主要なもの）

- データルート: `./data`（環境変数 `MEMORY_MCP_DATA_ROOT`、Docker: `/data`）
- 埋め込みモデル: `cl-nagoya/ruri-v3-30m`（日本語特化）
- Rerankerモデル: `hotchpotch/japanese-reranker-xsmall-v2`
- Qdrant: `http://localhost:6333`
- サーバーポート: `26262`
- タイムゾーン: `Asia/Tokyo`

### 設計上の注意点

- サーバーは `stateless_http=True` で起動（セッション管理なし。全状態はSQLiteに保持）
- Personaごとに独立したSQLiteファイルとQdrantコレクションを持つ
- `tools/` 配下のファイル（`crud_tools.py`, `search_tools.py` 等）は `unified_tools.py` のハンドラーから内部的に呼ばれるが、直接MCPツールとして公開されていない
- Ebbinghaus忘却曲線ワーカーはバックグラウンドスレッドで動作し、`recall`時に `boost_on_recall()` で強度を上げる
