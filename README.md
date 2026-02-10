# Memory MCP Server

MCP準拠の永続メモリサーバー。Personaごとの記憶を管理し、セマンティック検索とハイブリッド検索で最適な記憶を取得します。

## ✨ 特徴

- 🧠 **永続メモリ** - SQLite + Qdrant でデータとベクトルを管理
- 👤 **Personaサポート** - 複数のキャラクターを管理
- 🔍 **高精度RAG検索** - セマンティック・キーワード・ハイブリッド検索
- 📊 **リッチコンテキスト** - 感情・状態・環境など15カラムで記録
- 🎯 **スマート検索** - 曖昧なクエリも文脈から自動拡張
- 👗 **装備管理** - アイテム・衣装の管理と記憶との関連付け
- 📈 **Webダッシュボード** - 記憶の統計・推移・知識グラフを可視化
- 🚀 **Agent Skills対応** - トークン消費80〜90%削減

## 🚀 クイックスタート

### 前提条件

- Python 3.11+
- Docker (Qdrantサーバー用)

### インストール

```bash
# リポジトリをクローン
git clone https://github.com/solidlime/MemoryMCP.git
cd MemoryMCP

# 依存関係をインストール
pip install -r requirements.txt

# Qdrantサーバーを起動 (Docker)
docker run -d -p 6333:6333 qdrant/qdrant

# または、ローカルQdrantスクリプトを使用 (Linuxの場合)
bash scripts/start_local_qdrant.sh
```

### サーバーの起動

```bash
# MCPサーバーとして起動
python memory_mcp.py
```

デフォルトでは http://localhost:26262 でHTTP APIも公開されます。

### 基本的な使い方

#### GitHub Copilot Skills経由 (推奨)

`.github/skills/memory-mcp/` の設定に従って、GitHub Copilot から直接利用できます。

```python
# セッション開始時に文脈を取得
get_context()

# メモリ作成
memory(operation="create", content="ユーザーは苺が好き",
       emotion_type="joy", importance=0.8)

# 検索
memory(operation="search", query="好きな食べ物", mode="semantic")

# スマート検索（曖昧なクエリも文脈で拡張）
memory(operation="search", query="いつものあれ", mode="smart")

# アイテム追加と装備
item(operation="add", item_name="白いドレス", category="clothing")
item(operation="equip", equipment={"top": "白いドレス"})
```

詳細は [Skills ドキュメント](.github/skills/memory-mcp/SKILL.md) を参照してください。

#### HTTP API経由

```bash
# 文脈を取得
curl http://localhost:26262/api/get_context \
  -H "Authorization: Bearer nilou"

# メモリ作成
curl http://localhost:26262/api/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "create", "content": "プロジェクト完了", "emotion_type": "accomplishment"}'

# 検索
curl http://localhost:26262/api/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "search", "query": "プロジェクト", "mode": "hybrid"}'
```

詳細は [HTTP API リファレンス](docs/http_api_reference.md) を参照してください。

## 📚 主要機能

### 統合ツールAPI (3つの関数のみ)

- **`get_context()`** - 現在のPersona状態・時刻・メモリ統計を取得
- **`memory(operation, ...)`** - メモリ操作（create/read/update/delete/search/stats/check_routines）とコンテキスト操作（promise/goal/favorite/anniversary等）
- **`item(operation, ...)`** - アイテム操作（add/remove/equip/unequip/search/history/memories/stats）

### 検索モード

| モード | 説明 | 用途 |
|--------|------|------|
| `semantic` | セマンティック検索（RAG） | 意味的に類似した記憶を検索 |
| `keyword` | キーワード検索（Fuzzy対応） | 正確な単語・フレーズを検索 |
| `hybrid` | ハイブリッド（semantic 70% + keyword 30%） | バランスの取れた検索（デフォルト） |
| `smart` | スマート検索（曖昧クエリ自動拡張） | 「いつものあれ」などを文脈から判断 |

### 自然言語時間フィルタリング

```python
# 今日の記憶
memory(operation="search", query="", date_range="今日")

# 先週の記憶
memory(operation="search", query="成果", date_range="先週")

# 3日前の記憶
memory(operation="search", query="", date_range="3日前")
```

### ルーティンチェック

```python
# 現在時刻の繰り返しパターンを検出
memory(operation="check_routines")

# 詳細な時間帯別分析
memory(operation="check_routines", mode="detailed")
```

### 記念日管理

```python
# 記念日追加
memory(operation="anniversary", content="結婚記念日",
       persona_info={"date": "2025-11-10", "recurring": True})

# 一覧表示
memory(operation="anniversary")
```

## 🏗️ アーキテクチャ

```
Memory MCP Server
├── コアモジュール (core/)        # DB操作、時間管理、文脈管理
├── ツールモジュール (tools/)      # MCP ツール実装
│   ├── handlers/               # メモリ・コンテキスト・アイテムハンドラー
│   └── helpers/                # クエリ・ルーティンヘルパー
├── ユーティリティ (src/utils/)   # 設定・DB・ベクトル・ログ
├── テスト (tests/)              # 統合テスト
└── ドキュメント (docs/)         # 詳細ドキュメント
```

## 🧪 テスト

```bash
# すべてのテストを実行
python run_tests.py

# 特定のテストのみ
python run_tests.py --test http        # HTTP APIテスト
python run_tests.py --test search      # 検索精度テスト

# 詳細出力
python run_tests.py -v
```

## 📖 ドキュメント

- [完全なREADME](docs/README_FULL.md) - 全機能の詳細説明
- [HTTP API リファレンス](docs/http_api_reference.md) - HTTP APIの仕様
- [Skills ガイド](.github/skills/memory-mcp/SKILL.md) - GitHub Copilot Skills の使い方
- [メモリ操作フローチャート](docs/memory_operation_flowchart.md) - 操作フロー図
- [リファクタリング提案](docs/refactoring_suggestions.md) - 技術的な改善提案

## 🛠️ 設定

### Persona設定

デフォルトでは `nilou` Personaが使用されます。複数のPersonaを使い分けるには、Authorization ヘッダーで指定します。

```bash
# HTTP API
curl -H "Authorization: Bearer <persona_name>" ...

# 環境変数
export PERSONA=nilou
```

### Qdrant設定

デフォルトでは `localhost:6333` に接続します。変更するには環境変数を設定します。

```bash
export QDRANT_URL=http://localhost:6333
```

### タイムゾーン設定

デフォルトは `Asia/Tokyo` です。

```bash
export TIMEZONE=America/New_York
```

## 📊 Webダッシュボード

サーバー起動後、ブラウザで http://localhost:26262 にアクセスすると、記憶の統計・推移・知識グラフを確認できます。

## 🤝 貢献

プルリクエストを歓迎します！大きな変更を加える場合は、まずIssueを開いて議論してください。

## 📝 ライセンス

MIT License - 詳細は [LICENSE](LICENSE) を参照してください。

## 🙏 謝辞

- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Qdrant](https://qdrant.tech/)
- [LangChain](https://langchain.com/)
- [Sentence Transformers](https://www.sbert.net/)

---

**Memory MCP Server** - Built by [solidlime](https://github.com/solidlime) with ❤️
