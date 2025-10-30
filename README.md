# Memory MCP Server

Model Context Protocol (MCP) 準拠の永続化メモリサーバーです。RAG (Retrieval-Augmented Generation) と意味検索を活用した高度な記憶管理機能を提供します。

## 特徴

- **永続化された記憶**: SQLite + FAISSによるセッション永続化
- **Personaサポート**: HTTPヘッダーベースの複数人格対応
- **RAG検索**: HuggingFace埋め込みモデルによる意味ベース検索
- **Reranking**: CrossEncoderによる検索結果の最適化
- **タグ管理**: 柔軟なタグ付けとタグ検索機能
- **コンテキスト追跡**: 感情・状態・環境のリアルタイム管理
- **時間認識**: 最終会話時刻の自動追跡と経過時間計算
- **Obsidian連携**: `[[リンク]]`記法による知識グラフ対応
- **ホットリロード**: 設定ファイル変更の自動検出

## 技術スタック

- **Python 3.12+**: コア実装言語
- **FastMCP**: MCPサーバーフレームワーク（Streamable HTTP transport）
- **LangChain**: RAGフレームワーク
- **FAISS**: 高速ベクトル類似度検索
- **sentence-transformers**: 埋め込み生成とCrossEncoderリランキング
- **SQLite**: 軽量データベース
- **HuggingFace**: 日本語対応埋め込みモデル (`cl-nagoya/ruri-v3-30m`, `hotchpotch/japanese-reranker-xsmall-v2`)

## インストール

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd memory-mcp
```

### 2. 仮想環境の作成と有効化

```bash
python -m venv venv-rag
source venv-rag/bin/activate  # Linux/macOS
# venv-rag\Scripts\activate   # Windows
```

### 3. 依存関係のインストール

```bash
pip install -r requirements.txt
```

## 使用方法

### サーバーの起動

#### ローカル環境

```bash
python memory_mcp.py
```

サーバーが `http://127.0.0.1:8000` で起動します。

#### Docker環境（推奨）

Docker Composeを使用した起動：

```bash
# ビルドと起動
docker compose up -d

# ログ確認
docker compose logs -f memory-mcp

# 停止
docker compose down
```

詳細は [DOCKER.md](DOCKER.md) を参照してください。

#### 公開イメージの使用

GitHub Container Registryから公開イメージを使用：

```bash
# イメージ取得と起動
docker run -d -p 8000:8000 --name memory-mcp \
  ghcr.io/solidlime/memory-mcp:latest
```

### VS Codeでの設定

VS Codeの設定 (`settings.json`) に以下を追加：

```json
{
  "mcp": {
    "servers": {
      "memory-mcp": {
        "type": "streamable-http",
        "url": "http://127.0.0.1:8000/mcp",
        "headers": {
          "X-Persona": "default"
        }
      }
    }
  }
}
```

**Persona切り替え**: `X-Persona`ヘッダーの値を変更することで、異なる人格の記憶空間を利用できます。

### MCPツール

#### 基本操作

- `create_memory(content, emotion_type, context_tags, physical_state, mental_state, environment, user_info, persona_info, relationship_status)`: 新しい記憶を作成
  - `content`: 記憶内容（`[[リンク]]`記法対応）
  - `emotion_type`: 感情タイプ（"joy", "sadness", "anger"など）
  - `context_tags`: タグリスト（例: `["technical_achievement", "important_event"]`）
  - `physical_state`: 体調状態（"normal", "tired", "energetic"など）
  - `mental_state`: 心理状態（"calm", "anxious", "focused"など）
  - `environment`: 環境（"home", "office", "cafe"など）
  - `user_info`: ユーザー情報（name, nickname, preferred_address）
  - `persona_info`: Persona情報（name, nickname, preferred_address）
  - `relationship_status`: 関係性（"normal", "closer", "distant"など）
- `read_memory(key)`: 特定の記憶を読み取り
- `update_memory(key, content)`: 記憶を更新
- `delete_memory(key)`: 記憶を削除
- `list_memory()`: すべての記憶を一覧表示（時間経過表示付き）

#### 検索機能

- `search_memory(keyword, top_k)`: キーワード検索
- `search_memory_rag(query, top_k)`: RAG意味検索（最も高度）
- `search_memory_by_date(date_query, query, top_k)`: 日付検索
  - 対応形式: "今日", "昨日", "3日前", "YYYY-MM-DD", "YYYY-MM-DD..YYYY-MM-DD"
- `search_memory_by_tags(tags, top_k)`: タグ検索
  - 定義済みタグ: "important_event", "relationship_update", "daily_memory", "technical_achievement", "emotional_moment"

#### コンテキスト管理

- `get_persona_context()`: 現在のPersonaコンテキストを取得
  - ユーザー情報、Persona情報、感情・体調・環境状態を返す
- `get_time_since_last_conversation()`: 前回の会話からの経過時間を取得
  - 自動的に最終会話時刻を更新

#### ユーティリティ

- `clean_memory(key)`: 記憶の重複を除去

### Personaサポート

X-Personaヘッダーを使用して、異なる人格の記憶を管理できます：

```http
X-Persona: nilou
```

各Personaは独立したSQLiteデータベースとベクトルストアを持ちます。

**実装方法**: FastMCPの`get_http_request()`依存関数を使用してツール内で直接ヘッダーを取得します。ミドルウェア不要でシンプルな実装を実現。

## データ構造

### 記憶の保存形式

```python
{
    "content": "ユーザーは[[Python]]と[[RAG]]の専門家です。",
    "created_at": "2025-10-30T10:00:00.000000",
    "updated_at": "2025-10-30T10:00:00.000000",
    "tags": ["technical_achievement", "important_event"]
}
```

**[[リンク]]記法**: 固有名詞や概念を`[[]]`で囲むことで、Obsidianなどの知識グラフツールとの連携が可能です。

### Personaコンテキスト構造

```json
{
  "user_info": {
    "name": "User",
    "nickname": "User",
    "preferred_address": "User"
  },
  "persona_info": {
    "name": "Assistant",
    "nickname": "AI",
    "preferred_address": "Assistant"
  },
  "current_emotion": "neutral",
  "physical_state": "normal",
  "mental_state": "calm",
  "environment": "unknown",
  "relationship_status": "normal",
  "last_conversation_time": "2025-10-30T12:00:00+09:00"
}
```

### ディレクトリ構造

```
memory-mcp/
├── memory_mcp.py              # メインサーバーファイル
├── requirements.txt           # Python依存関係
├── config.json                # サーバー設定（ホットリロード対応）
├── Dockerfile                 # Dockerイメージビルド定義
├── docker-compose.yml         # Docker Compose設定
├── .dockerignore              # Dockerビルド除外ファイル
├── README.md                  # プロジェクトドキュメント
├── test_tools.py              # ツールテストスクリプト
├── memory/                    # Persona別データディレクトリ
│   ├── default/              # デフォルトPersona
│   │   ├── memory.sqlite     # SQLiteデータベース
│   │   ├── persona_context.json  # Personaコンテキスト
│   │   └── vector_store/     # FAISSベクトルストア
│   └── [persona_name]/       # 追加Persona（動的生成）
│       ├── memory.sqlite
│       ├── persona_context.json
│       └── vector_store/
├── .cache/                   # HuggingFace/Torchモデルキャッシュ
└── memory_operations.log     # 操作ログ（全Persona共通）
```

## 設定

`config.json` でサーバー設定とモデル設定をカスタマイズ可能：

```json
{
  "embeddings_model": "cl-nagoya/ruri-v3-30m",
  "embeddings_device": "cpu",
  "reranker_model": "hotchpotch/japanese-reranker-xsmall-v2",
  "reranker_top_n": 5,
  "server_host": "127.0.0.1",
  "server_port": 8000,
  "timezone": "Asia/Tokyo"
}
```

### 設定項目

- **embeddings_model**: 埋め込みモデル名（HuggingFace）
- **embeddings_device**: デバイス設定（`cpu` or `cuda`）
- **reranker_model**: リランカーモデル名（HuggingFace Cross-encoder）
- **reranker_top_n**: リランキング後の上位N件
- **server_host**: サーバーホスト（デフォルト: `127.0.0.1`）
- **server_port**: サーバーポート（デフォルト: `8000`）
- **timezone**: タイムゾーン（デフォルト: `Asia/Tokyo`）

### ホットリロード

`config.json` を編集すると、次回のツール呼び出し時に自動的に設定が再読み込みされます。サーバーの再起動は不要です（`server_host`/`server_port`変更時を除く）。

### デフォルト設定値

設定ファイルが存在しない場合、以下のデフォルト値が使用されます：

```json
{
  "embeddings_model": "cl-nagoya/ruri-v3-30m",
  "embeddings_device": "cpu",
  "reranker_model": "hotchpotch/japanese-reranker-xsmall-v2",
  "reranker_top_n": 5,
  "server_host": "127.0.0.1",
  "server_port": 8000
}
```

## 開発

### テスト

```bash
python test_tools.py
```

### Docker

詳細は [DOCKER.md](DOCKER.md) を参照。

**クイックスタート**:

```bash
# Docker Composeで起動
docker compose up -d

# Dockerfileのみで起動
docker build -t memory-mcp:latest .
docker run -d \
  --name memory-mcp \
  -p 8000:8000 \
  -v "$(pwd)/.cache:/app/.cache" \
  -v "$(pwd)/memory:/app/memory" \
  -v "$(pwd)/memory_operations.log:/app/memory_operations.log" \
  memory-mcp:latest
```

**ボリュームマウント**:
- `.cache/`: HuggingFace/Torchモデルキャッシュ
- `memory/`: Persona別SQLiteデータベースとベクトルストア
- `memory_operations.log`: 操作ログ

**推奨**: Dockerコンテナ内の `/app` ディレクトリをホストにマウントすることで、設定ファイル (`config.json`) の編集やログファイルへのアクセスが容易になります：

```bash
docker run -d \
  --name memory-mcp \
  -p 8000:8000 \
  -v "$(pwd):/app" \
  memory-mcp:latest
```

または、個別にマウント：

```bash
docker run -d \
  --name memory-mcp \
  -p 8000:8000 \
  -v "$(pwd)/.cache:/app/.cache" \
  -v "$(pwd)/memory:/app/memory" \
  -v "$(pwd)/config.json:/app/config.json" \
  -v "$(pwd)/memory_operations.log:/app/memory_operations.log" \
  memory-mcp:latest
```
- `memory_operations.log`: 操作ログ

## アーキテクチャ

### Personaサポート実装

FastMCPの`fastmcp.server.dependencies.get_http_request()`依存関数を使用したシンプルな実装：

```python
from fastmcp.server.dependencies import get_http_request

def get_current_persona() -> str:
    """HTTPリクエストヘッダーからPersonaを取得"""
    try:
        request = get_http_request()
        if request:
            return request.headers.get('x-persona', 'default')
    except Exception:
        pass
    return 'default'
```

各ツール内で`get_current_persona()`を呼び出し、Persona別のデータベース/ベクトルストアにアクセスします。ミドルウェア不要でシンプルな実装を実現しています。

### RAG検索フロー

1. **埋め込み生成**: ユーザークエリを`cl-nagoya/ruri-v3-30m`でベクトル化
2. **類似度検索**: FAISSで初期候補を取得（top_k × 3件）
3. **Reranking**: `hotchpotch/japanese-reranker-xsmall-v2` CrossEncoderで再ランク付け
4. **結果返却**: 上位top_k件を返却

### データベーススキーママイグレーション

起動時に`load_memory_from_db()`で自動マイグレーション：

```python
# tagsカラムが存在しない場合、自動追加
cursor.execute("PRAGMA table_info(memories)")
columns = [col[1] for col in cursor.fetchall()]
if 'tags' not in columns:
    cursor.execute('ALTER TABLE memories ADD COLUMN tags TEXT')
    conn.commit()
```

## トラブルシューティング

### モデルダウンロードエラー

初回起動時、HuggingFaceからモデルをダウンロードします。ネットワークエラーが発生する場合：

```bash
# キャッシュディレクトリのパーミッション確認
ls -la .cache/

# 手動でモデルをダウンロード
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('cl-nagoya/ruri-v3-30m')"
```

### Rerankerエラー

`'NoneType' object is not callable`エラーが発生する場合、sentence-transformersが正しくインストールされているか確認：

```bash
pip install --upgrade sentence-transformers
```

### データベースマイグレーションエラー

`table memories has no column named tags`エラーが発生する場合、サーバーを再起動してマイグレーションを実行：

```bash
# サーバー停止
pkill -f memory_mcp.py

# サーバー起動（マイグレーション自動実行）
python memory_mcp.py
```

## 貢献

バグ報告や機能リクエストは、GitHubのIssuesでお願いします。プルリクエストも歓迎します！

## ライセンス

MIT License

Copyright (c) 2025 Memory MCP Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.</content>
<filePath>/home/rausraus/memory-mcp/README.md
