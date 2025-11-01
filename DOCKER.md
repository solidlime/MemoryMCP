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
  "server_port": 8000
}
```

**注意**: `server_host`をDockerコンテナ内で`127.0.0.1`にすると、外部からアクセスできません。`0.0.0.0`を推奨します。

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

## まとめ

- **推奨**: Docker Composeを使用
- **必須マウント**: `./memory`（データ永続化）
- **推奨マウント**: `./.cache`（モデルキャッシュ）、`./config.json`（設定）
- **ヘルスチェック**: 自動で正常性確認
- **ログ**: `docker compose logs -f`でリアルタイム確認

質問や問題があれば、GitHubのIssuesで報告してください！
