# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# サーバー起動（HTTPサーバー + MCPサーバーを同時起動）
python memory_mcp.py

# 全テスト実行（サーバーが localhost:26262 で起動中であること）
python run_tests.py

# 個別テスト
python run_tests.py --test http      # HTTP APIテスト
python run_tests.py --test search    # 検索精度テスト
python run_tests.py --test migrate   # DBスキーママイグレーション
python run_tests.py -v               # 詳細出力

# Qdrantサーバー（必須）
docker run -d -p 6333:6333 qdrant/qdrant
# または docker-compose up -d

# PyTorch CPU版（ローカル開発時のみ）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

## アーキテクチャ

### エントリポイント

`memory_mcp.py` が唯一のエントリポイント。FastMCPサーバーとして起動し、HTTP API（port 26262）も同時に公開する。Persona識別はBearerトークンまたは `PERSONA` 環境変数で行う。

### レイヤー構成

```
memory_mcp.py            # FastMCP初期化・ツール登録・HTTPルート登録
├── tools/unified_tools.py  # 公開MCPツール3本（get_context/memory/item）の薄いラッパー
│   └── tools/handlers/     # 各操作のロジック（memory_handlers/context_handlers/item_handlers）
│       └── tools/helpers/  # クエリ正規化・ルーティン検出
├── core/                   # ステートレスなDB・時刻・ドメインロジック
│   ├── memory_db.py        # SQLite CRUD（記憶エントリ）
│   ├── forgetting.py       # Ebbinghaus忘却曲線ワーカー R(t) = e^(-t/S)
│   ├── user_state_db.py    # Bi-temporalユーザー状態（変更履歴保持）
│   ├── memory_blocks_db.py # Named Memory Blocks（常時コンテキストに載る構造化ブロック）
│   ├── equipment_db.py     # アイテム・装備管理
│   ├── persona_context.py  # Persona状態ファイルの読み書き
│   └── time_utils.py       # タイムゾーン対応・自然言語日付パース
└── src/
    ├── utils/
    │   ├── config_utils.py   # config.json読み込み・環境変数マージ
    │   ├── vector_utils.py   # Qdrantクライアント・RAGパイプライン（最大ファイル）
    │   └── persona_utils.py  # Persona別DBパス解決
    ├── dashboard.py          # Webダッシュボード（HTTPルート）
    └── resources.py          # MCPリソースエンドポイント
```

### 公開ツールAPI（3本のみ）

| ツール | 主なoperations |
|--------|---------------|
| `get_context()` | なし（状態サマリー返却） |
| `memory(operation, ...)` | `create / read / update / delete / search / stats / check_routines / promise / goal / update_context / block_write / block_read` |
| `item(operation, ...)` | `add / remove / equip / unequip / update / search / history / memories` |

`memory()` の検索モード: `semantic`（Qdrant）/ `keyword`（SQLite LIKE + RapidFuzz）/ `hybrid`（RRF統合）/ `smart`（クエリ自動拡張）

### 永続化

- **SQLite**: 記憶エントリ・ユーザー状態・装備・Personaコンテキスト（`data/<persona>/`配下）
- **Qdrant**: ベクトルストア（`memory_<persona>` コレクション）
- **config.json**: `src/utils/config_utils.py` の `load_config()` が読み込む。デフォルト値は `DEFAULT_CONFIG` 参照。

### デフォルト設定値（主要なもの）

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
