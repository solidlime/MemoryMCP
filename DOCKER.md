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

### 最速起動

```bash
# リポジトリクローン
git clone https://github.com/solidlime/MemoryMCP.git
cd MemoryMCP

# Docker Composeで起動
docker compose up -d

# ログ確認
docker compose logs -f memory-mcp
```

サーバーが `http://localhost:8000` で起動します。

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
      - "8000:8000"
    volumes:
      - ./.cache:/app/.cache
      - ./memory:/app/memory
      - ./config.json:/app/config.json
      - ./memory_operations.log:/app/memory_operations.log
    environment:
      - HF_HOME=/app/.cache/huggingface
      - TRANSFORMERS_CACHE=/app/.cache/transformers
      - SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers
      - TORCH_HOME=/app/.cache/torch
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
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

ホスト側のポートを変更する場合：

```yaml
ports:
  - "9000:8000"  # ホスト:9000 -> コンテナ:8000
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
  -p 8000:8000 \
  -v "$(pwd)/.cache:/app/.cache" \
  -v "$(pwd)/memory:/app/memory" \
  -v "$(pwd)/config.json:/app/config.json" \
  -v "$(pwd)/memory_operations.log:/app/memory_operations.log" \
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
| `./.cache` | `/app/.cache` | HuggingFace/Torchモデルキャッシュ | ⭐ 推奨 |
| `./memory` | `/app/memory` | Persona別データベース・ベクトルストア | ✅ 必須 |
| `./config.json` | `/app/config.json` | サーバー設定（ホットリロード） | ⭐ 推奨 |
| `./memory_operations.log` | `/app/memory_operations.log` | 操作ログ | △ オプション |

### キャッシュボリューム

初回起動時、HuggingFaceから以下のモデルをダウンロードします：

- **埋め込みモデル**: `cl-nagoya/ruri-v3-30m` (~120MB)
- **Rerankerモデル**: `hotchpotch/japanese-reranker-xsmall-v2` (~50MB)

`.cache`ディレクトリをマウントすることで、コンテナ再作成時もダウンロードをスキップできます。

**Docker Composeの場合**:

```yaml
volumes:
  - ./.cache:/app/.cache  # ホストにキャッシュを永続化
```

**Dockerfileのみの場合**:

```bash
docker run -v "$(pwd)/.cache:/app/.cache" ...
```

### データ永続化

`./memory`ディレクトリには各Personaのデータが保存されます：

```
memory/
├── default/
│   ├── memory.sqlite          # SQLiteデータベース
│   ├── persona_context.json   # コンテキスト
│   └── vector_store/
│       └── index.faiss        # FAISSインデックス
└── [persona_name]/
    ├── memory.sqlite
    ├── persona_context.json
    └── vector_store/
```

**重要**: このディレクトリを削除すると、すべての記憶が失われます。

## 環境変数

### キャッシュディレクトリ

```bash
HF_HOME=/app/.cache/huggingface
TRANSFORMERS_CACHE=/app/.cache/transformers
SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers
TORCH_HOME=/app/.cache/torch
```

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

1. **ポート競合**: `Bind for 0.0.0.0:8000 failed: port is already allocated`
   - 解決: `docker-compose.yml`でポートを変更（例: `9000:8000`）

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
