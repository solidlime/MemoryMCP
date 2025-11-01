# Docker デプロイメントガイド

Memory MCP ServerをDockerで実行するための完全ガイドです。

## 目次

- [クイックスタート](#クイックスタート)
- [Docker Compose（推奨）](#docker-compose推奨)
- [Dockerfile単独ビルド](#dockerfile単独ビルド)
- [ボリュームマウント](#ボリュームマウント)
- [環境変数](#環境変数)
- [ヘルスチェック](#ヘルスチェック)
- [イメージ配布](#イメージ配布)
- [トラブルシューティング](#トラブルシューティング)

## クイックスタート

### 前提条件

- Docker 20.10+
- Docker Compose 2.0+（推奨）
- 最低2GB RAM（モデルキャッシュ含む）
- ディスク: 5GB以上推奨（モデルキャッシュ + データ）

### 最速起動

```bash
# リポジトリクローン
git clone https://github.com/solidlime/MemoryMCP.git
cd MemoryMCP

# データディレクトリ作成（初回のみ）
mkdir -p data

# Docker Composeで起動
docker compose up -d

# ログ確認
docker compose logs -f memory-mcp
```

サーバーが `http://localhost:26262` で起動します。

**ポート設定について**:
- 開発環境（ローカル起動）: ポート `8000` (config.jsonで設定)
- 本番環境（Docker起動）: ポート `26262` (環境変数で設定、競合回避)

## Docker Compose（推奨）

### 設定ファイル

`docker-compose.yml`:

```yaml
version: '3.8'

services:
  memory-mcp:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: memory-mcp
    ports:
      - "26262:26262"
    volumes:
      # Persist all data (memory, logs, cache) in one mount
      - ./data:/data
      # Persist config file for hot reload
      - ./config.json:/config/config.json:ro
    environment:
      # Cache directories (unified under /data/cache)
      - HF_HOME=/data/cache/huggingface
      - TRANSFORMERS_CACHE=/data/cache/transformers
      - SENTENCE_TRANSFORMERS_HOME=/data/cache/sentence_transformers
      - TORCH_HOME=/data/cache/torch
      # Memory & config paths
      - MEMORY_MCP_CONFIG_PATH=/config/config.json
      - MEMORY_MCP_DATA_DIR=/data
      - MEMORY_MCP_SERVER_PORT=26262
      # Python unbuffered output for better logging
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:26262/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

**ディレクトリ構造**:
```
./data/
├── memory/              # Personaごとのデータベース
│   ├── default/
│   ├── nilou/
│   └── ...
├── logs/                # 操作ログ
│   └── memory_operations.log
└── cache/               # モデルキャッシュ
    ├── huggingface/
    ├── transformers/
    ├── sentence_transformers/
    └── torch/
```

### 基本コマンド

```bash
# ビルドと起動
docker compose up -d

# ビルドを強制的にやり直す
docker compose up -d --build

# ログをリアルタイムで確認
docker compose logs -f memory-mcp

# 停止
docker compose stop

# 停止と削除
docker compose down

# ボリュームも含めて完全削除
docker compose down -v
```

### カスタムポート

デフォルトではポート `26262` を使用しますが、変更も可能です：

```yaml
ports:
  - "9000:26262"  # ホスト:9000 -> コンテナ:26262
```

環境変数でコンテナ内のポートを変更する場合：

```yaml
environment:
  - MEMORY_MCP_SERVER_PORT=8080
ports:
  - "8080:8080"
```

VS Code設定も合わせて変更：

```json
{
  "mcp": {
    "servers": {
      "memory-mcp": {
        "url": "http://127.0.0.1:9000/mcp"
      }
    }
  }
}
```

## Dockerfile単独ビルド

Docker Composeを使わない場合の手順：

### ビルド

```bash
docker build -t memory-mcp:latest .
```

### 起動

```bash
docker run -d \
  --name memory-mcp \
  -p 26262:26262 \
  -v "$(pwd)/data:/data" \
  -v "$(pwd)/config.json:/config/config.json:ro" \
  -e HF_HOME=/data/cache/huggingface \
  -e TRANSFORMERS_CACHE=/data/cache/transformers \
  -e SENTENCE_TRANSFORMERS_HOME=/data/cache/sentence_transformers \
  -e TORCH_HOME=/data/cache/torch \
  -e MEMORY_MCP_CONFIG_PATH=/config/config.json \
  -e MEMORY_MCP_DATA_DIR=/data \
  -e MEMORY_MCP_SERVER_PORT=26262 \
  -e PYTHONUNBUFFERED=1 \
  --restart unless-stopped \
  memory-mcp:latest
```

### 管理コマンド

```bash
# ログ確認
docker logs -f memory-mcp

# コンテナ内でコマンド実行
docker exec -it memory-mcp bash

# 停止
docker stop memory-mcp

# 再起動
docker restart memory-mcp

# 削除
docker rm -f memory-mcp
```

## ボリュームマウント

### 推奨マウント構成

| ホストパス | コンテナパス | 説明 | 必須 |
|-----------|-------------|------|------|
| `./data` | `/data` | 全データ（memory/, logs/, cache/） | ✅ 必須 |
| `./config.json` | `/config/config.json` | サーバー設定（ホットリロード） | ⭐ 推奨 |

**シンプル化のポイント**:
- `./data` ディレクトリ1つだけマウントすれば、メモリ・ログ・キャッシュすべて永続化
- 個別のディレクトリをマウントする必要なし

### データディレクトリ構造

初回起動時、`./data` 配下に以下が自動作成されます：

```
data/
├── memory/              # Persona別データベース・ベクトルストア
│   ├── default/
│   │   ├── memory.sqlite
│   │   ├── persona_context.json
│   │   └── vector_store/
│   │       └── index.faiss
│   └── [persona_name]/
│       └── ...
├── logs/                # 操作ログ
│   └── memory_operations.log
└── cache/               # モデルキャッシュ
    ├── huggingface/
    ├── transformers/
    ├── sentence_transformers/
    └── torch/
```

### キャッシュボリューム

初回起動時、HuggingFaceから以下のモデルをダウンロードします：

- **埋め込みモデル**: `cl-nagoya/ruri-v3-30m` (~120MB)
- **Rerankerモデル**: `hotchpotch/japanese-reranker-xsmall-v2` (~50MB)

`./data/cache`ディレクトリに永続化されるため、コンテナ再作成時もダウンロードをスキップできます。

**重要**: `./data`ディレクトリを削除すると、すべての記憶とキャッシュが失われます。

## 環境変数

### データパス設定

| 環境変数 | デフォルト値 | 説明 |
|---------|-------------|------|
| `MEMORY_MCP_DATA_DIR` | `/data` | データディレクトリルート |
| `MEMORY_MCP_CONFIG_PATH` | `/config/config.json` | 設定ファイルパス |
| `MEMORY_MCP_STORAGE_BACKEND` | `sqlite` | ベクトルストアバックエンド（`sqlite`/`faiss` または `qdrant`） |
| `MEMORY_MCP_QDRANT_URL` | `http://localhost:6333` | Qdrantサーバー接続URL |
| `MEMORY_MCP_QDRANT_API_KEY` | `null` | Qdrant API Key（未設定なら認証なし） |
| `MEMORY_MCP_QDRANT_COLLECTION_PREFIX` | `memory_` | Qdrantコレクション名Prefix |

### キャッシュディレクトリ

すべてのキャッシュは `MEMORY_MCP_DATA_DIR` 配下の `cache/` に統一：

```bash
HF_HOME=/data/cache/huggingface
TRANSFORMERS_CACHE=/data/cache/transformers
SENTENCE_TRANSFORMERS_HOME=/data/cache/sentence_transformers
TORCH_HOME=/data/cache/torch
```

これにより、`./data` ディレクトリ1つをマウントするだけで、すべてのキャッシュが永続化されます。

### Python設定

```bash
PYTHONUNBUFFERED=1  # ログをリアルタイムで出力
```

### カスタム設定

`config.json`でサーバー設定をカスタマイズできます：

```json
{
  "embeddings_model": "cl-nagoya/ruri-v3-30m",
  "embeddings_device": "cpu",
  "reranker_model": "hotchpotch/japanese-reranker-xsmall-v2",
  "reranker_top_n": 5,
  "server_host": "0.0.0.0",
  "server_port": 8000,
  "storage_backend": "sqlite",
  "qdrant_url": "http://localhost:6333",
  "qdrant_api_key": null,
  "qdrant_collection_prefix": "memory_"
}
```

**注意**: `server_host`をDockerコンテナ内で`127.0.0.1`にすると、外部からアクセスできません。`0.0.0.0`を推奨します。

### Qdrantバックエンド使用時

Qdrantをベクトルストアバックエンドとして使用する場合、別途Qdrantサーバーを起動する必要があります。

**docker-compose.ymlにQdrantサービスを追加**:

```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - ./qdrant_storage:/qdrant/storage
    restart: unless-stopped

  memory-mcp:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: memory-mcp
    ports:
      - "26262:26262"
    volumes:
      - ./data:/data
      - ./config.json:/config/config.json:ro
    environment:
      - MEMORY_MCP_DATA_DIR=/data
      - MEMORY_MCP_SERVER_PORT=26262
      - MEMORY_MCP_STORAGE_BACKEND=qdrant
      - MEMORY_MCP_QDRANT_URL=http://qdrant:6333
      - PYTHONUNBUFFERED=1
    depends_on:
      - qdrant
    restart: unless-stopped
```

**移行ツール**:

MCPツール経由で、SQLite⇔Qdrant間でメモリデータを移行できます：

- `migrate_sqlite_to_qdrant_tool`: SQLiteからQdrantへベクトルデータをアップサート
- `migrate_qdrant_to_sqlite_tool`: QdrantからSQLiteへベクトルデータをインポート

これにより、既存のSQLite/FAISSデータをQdrantに移行したり、Qdrantデータをバックアップとしてローカルに保存することが可能です。

## ヘルスチェック

Docker Composeには自動ヘルスチェックが含まれています：

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### 手動ヘルスチェック

```bash
# Docker Compose
docker compose ps

# Dockerfile単独
docker ps --filter name=memory-mcp
```

`STATUS`列に`healthy`と表示されればOKです。

## イメージ配布

ビルドしたDockerイメージをコンテナレジストリに公開する方法です。

### GitHub Container Registry (推奨)

1. **Personal Access Tokenの作成**
   - GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
   - 権限: `write:packages`, `read:packages`, `delete:packages`

2. **ログイン**
   ```bash
   echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
   ```

3. **イメージのタグ付け**
   ```bash
   docker tag memory-mcp:latest ghcr.io/solidlime/memory-mcp:latest
   ```

4. **プッシュ**
   ```bash
   docker push ghcr.io/solidlime/memory-mcp:latest
   ```

5. **使用方法**
   ```bash
   docker run -d -p 8000:8000 --name memory-mcp \
     ghcr.io/solidlime/memory-mcp:latest
   ```

### Docker Hub

1. **ログイン**
   ```bash
   docker login
   ```

2. **イメージのタグ付け**
   ```bash
   docker tag memory-mcp:latest yourusername/memory-mcp:latest
   ```

3. **プッシュ**
   ```bash
   docker push yourusername/memory-mcp:latest
   ```

4. **使用方法**
   ```bash
   docker run -d -p 8000:8000 --name memory-mcp \
     yourusername/memory-mcp:latest
   ```

### バージョン管理

```bash
# バージョンタグ付きでビルド
docker build -t memory-mcp:v1.0.0 .

# 複数タグを付ける
docker tag memory-mcp:v1.0.0 ghcr.io/solidlime/memory-mcp:v1.0.0
docker tag memory-mcp:v1.0.0 ghcr.io/solidlime/memory-mcp:latest

# プッシュ
docker push ghcr.io/solidlime/memory-mcp:v1.0.0
docker push ghcr.io/solidlime/memory-mcp:latest
```

## トラブルシューティング

### コンテナが起動しない

```bash
# ログ確認
docker compose logs memory-mcp

# または
docker logs memory-mcp
```

**よくあるエラー**:

1. **ポート競合**: `Bind for 0.0.0.0:26262 failed: port is already allocated`
   - 原因: 別のコンテナやプロセスが同じポートを使用中
   - 解決: `docker-compose.yml`でホスト側ポートを変更（例: `9000:26262`）
   - または: `MEMORY_MCP_SERVER_PORT`環境変数で別のポートを指定

2. **パーミッションエラー**: `Permission denied`
   - 解決: ボリュームマウント先のディレクトリパーミッション確認
   ```bash
   sudo chown -R $USER:$USER .cache memory
   ```

3. **モジュールが見つからない**: `ModuleNotFoundError: No module named 'beartype'` など
   - 原因: 必要な依存パッケージがDockerイメージに含まれていない
   - 解決: Dockerfileで不要なpip uninstallを実行していないか確認
   - **重要な依存関係**:
     - `beartype`: fastmcp（MCPサーバー）に必須
     - `sympy`: torch（PyTorch）に必須
     - `scikit-learn`: sentence-transformers（埋め込みモデル）に必須
     - `pillow`: sentence-transformers、torchvision（画像処理）に必須
     - `jedi`: ipython（対話シェル）に必須
   - これらのパッケージは `requirements.txt` で自動的にインストールされますが、
     イメージサイズ削減のために削除すると本番環境でエラーになります
   - **推奨**: すべての依存パッケージを保持し、pip uninstallコマンドは使用しない

### モデルダウンロードエラー

```bash
# コンテナ内でモデルを手動ダウンロード
docker exec -it memory-mcp python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('cl-nagoya/ruri-v3-30m')"
```

### メモリ不足

```bash
# Dockerのメモリ制限を確認
docker stats memory-mcp
```

メモリ不足の場合、Docker Desktopの設定でメモリを増やします（推奨: 4GB以上）。

### データベースマイグレーションエラー

```bash
# コンテナを再起動してマイグレーション再実行
docker compose restart memory-mcp

# または
docker restart memory-mcp
```

### ログが表示されない

`PYTHONUNBUFFERED=1`環境変数が設定されているか確認：

```bash
docker exec memory-mcp env | grep PYTHONUNBUFFERED
```

### コンテナ内でデバッグ

```bash
# コンテナ内でbashを起動
docker exec -it memory-mcp bash

# Pythonスクリプトを手動実行
python3 memory_mcp.py

# ディレクトリ構造確認
ls -la /app
ls -la /app/memory
```

## パフォーマンス最適化

### GPUサポート（NVIDIA）

NVIDIA GPUを使用する場合：

**docker-compose.yml**:

```yaml
services:
  memory-mcp:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - EMBEDDINGS_DEVICE=cuda
```

**config.json**:

```json
{
  "embeddings_device": "cuda"
}
```

### メモリ制限

```yaml
services:
  memory-mcp:
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G
```

## プロダクション環境

### リバースプロキシ（Nginx）

```nginx
upstream memory_mcp {
    server localhost:8000;
}

server {
    listen 80;
    server_name memory-mcp.example.com;

    location /mcp {
        proxy_pass http://memory_mcp;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Persona "default";
    }
}
```

### HTTPS（Let's Encrypt）

```bash
# Certbotインストール
sudo apt install certbot python3-certbot-nginx

# SSL証明書取得
sudo certbot --nginx -d memory-mcp.example.com
```

## バックアップ

### データベースバックアップ

```bash
# memory/ディレクトリ全体をバックアップ
tar -czf memory-backup-$(date +%Y%m%d).tar.gz memory/

# 特定Personaのみ
tar -czf memory-default-backup.tar.gz memory/default/
```

### 自動バックアップ（cron）

```bash
# crontab -e
0 2 * * * cd /path/to/MemoryMCP && tar -czf /backup/memory-$(date +\%Y\%m\%d).tar.gz memory/
```

## Dockerfileビルド最適化

### Multi-stage Build

このプロジェクトのDockerfileは、Multi-stage buildパターンを採用しています：

```dockerfile
# Stage 1: Builder - PyTorchとPython依存関係をインストール
FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime - 最小限のファイルだけをコピー
FROM python:3.12-slim
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY . /app
```

**メリット**:
- 最終イメージサイズの削減（ビルドツール不要）
- レイヤーキャッシュの効率化
- セキュリティ向上（不要なツールを含まない）

### 依存関係管理のベストプラクティス

**重要**: Dockerイメージサイズを削減するために不要なパッケージを削除したくなりますが、
**依存関係を正しく理解せずに削除すると本番環境でエラーが発生します**。

#### 削除してはいけないパッケージ

以下のパッケージは一見不要に見えますが、**実際には必須依存関係**です：

| パッケージ | 依存元 | 理由 |
|-----------|--------|------|
| `beartype` | fastmcp → key_value.aio | MCPサーバー起動に必須 |
| `sympy` | torch | PyTorch内部で使用 |
| `scikit-learn` | sentence-transformers | 埋め込みモデルの内部処理 |
| `pillow` | sentence-transformers, torchvision | 画像処理機能（間接的に必要） |
| `jedi` | ipython | コード補完・対話シェル |

#### 依存関係チェック方法

パッケージを削除する前に、以下のスクリプトで依存関係を確認してください：

```python
import pkg_resources

def check_dependency(package_name):
    """指定パッケージを使用している依存関係を検出"""
    dependencies = []
    for dist in pkg_resources.working_set:
        if dist.has_metadata('METADATA'):
            metadata = dist.get_metadata('METADATA')
            if package_name in metadata:
                dependencies.append(dist.project_name)
    return dependencies

# 例: sympyの依存関係チェック
used_by = check_dependency('sympy')
if used_by:
    print(f"❌ sympy: USED BY {used_by} - DO NOT REMOVE")
else:
    print(f"✅ sympy: Not used - Safe to remove")
```

#### 推奨アプローチ

1. **すべての依存パッケージを保持**: `requirements.txt` で管理されているパッケージはすべて必要
2. **pip uninstallコマンドは使用しない**: 予期しない依存関係の破壊を防ぐ
3. **イメージサイズ削減は別の方法で**: Multi-stage build、`--no-cache-dir`、Alpine base imageなどを活用

#### 過去の失敗例

```dockerfile
# ❌ 悪い例: イメージサイズ削減のために依存パッケージを削除
RUN pip install -r requirements.txt && \
    pip uninstall -y sympy scikit-learn jedi pillow beartype

# 結果: 本番環境で ModuleNotFoundError が発生
# - beartype: fastmcpが起動しない
# - sympy: torchの一部機能が動かない
# - scikit-learn, pillow: sentence-transformersがクラッシュ
```

```dockerfile
# ✅ 良い例: 必要な依存関係をすべて保持
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# イメージサイズ削減はMulti-stage buildとキャッシュ無効化で対応
```

### イメージサイズの現状

- **最終イメージサイズ**: ~2.65GB
- **内訳**:
  - Base image (python:3.12-slim): ~180MB
  - PyTorch (CPU版): ~800MB
  - その他Python依存関係: ~1.2GB
  - アプリケーションコード: ~50MB
  - モデルキャッシュ: ボリュームマウントで永続化（含まない）

### さらなる最適化案

必要に応じて以下の最適化も検討できます：

1. **Alpine Linuxベース**: `python:3.12-alpine` (~50MB削減、ただしビルド時間増加)
2. **GPU版の分離**: CPU版とGPU版で別イメージを用意
3. **依存関係の見直し**: 本当に不要なパッケージがないか定期的にレビュー

## まとめ

- **推奨**: Docker Composeを使用
- **必須マウント**: `./memory`（データ永続化）
- **推奨マウント**: `./.cache`（モデルキャッシュ）、`./config.json`（設定）
- **ヘルスチェック**: 自動で正常性確認
- **ログ**: `docker compose logs -f`でリアルタイム確認

質問や問題があれば、GitHubのIssuesで報告してください！
