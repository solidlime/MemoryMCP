# コード実行サンドボックス

MemoryMCP のチャットでは `llm-sandbox[docker]` を使った Python コード実行サンドボックスを利用できます。
コードはコンテナ内の IPython カーネルで実行され、結果がチャットに返ってきます。

---

## アーキテクチャ

```
MemoryMCP (サーバープロセス or Docker コンテナ)
    └── SandboxSession (llm-sandbox)
            └── Docker Python SDK
                    │  DOCKER_HOST = ローカルsocket or tcp://remote:2375
                    ↓
            Docker Daemon（ローカル or リモート）
                └── Python/IPython コンテナ
                        └── /workspace  ←→  data/sandbox/{persona}/workspace/  (bind mount)
```

- **ファイル永続化**: コンテナの `/workspace` は `data/sandbox/{persona}/workspace/` にバインドマウントされます。MemoryMCP を再起動してもファイルは残ります。
- **ペルソナ分離**: ペルソナごとに独立したワークスペースを持ちます。

---

## セットアップ

### 1. ローカル Docker（docker-compose を使う場合）

`docker-compose.yml` には `/var/run/docker.sock` マウントがすでに含まれています。  
サンドボックスを有効にするには `.env` ファイルに以下を追記します。

```env
MEMORY_MCP_SANDBOX__ENABLED=true
```

その後コンテナを再起動します。

```bash
docker-compose down && docker-compose up -d
```

> **注意**: `docker.sock` のマウントはホストの Docker デーモンをコンテナから利用する方式（sibling container）です。
> コンテナ内から新たにコンテナを起動するため、ホストに十分なリソースがある環境で使用してください。

### 2. ローカル Python（サーバーを直接起動する場合）

Docker Desktop（または Docker Engine）が起動している状態で次のコマンドを実行します。

```bash
MEMORY_MCP_SANDBOX__ENABLED=true python -m memory_mcp.main
```

### 3. リモート Docker ホスト

別のホストで Docker デーモンを TLS なしで公開している場合（開発・テスト用）:

```env
MEMORY_MCP_SANDBOX__ENABLED=true
MEMORY_MCP_SANDBOX__DOCKER_HOST=tcp://192.168.1.100:2375
```

TLS を有効にしたリモート Docker（本番推奨）:

```env
MEMORY_MCP_SANDBOX__DOCKER_HOST=tcp://192.168.1.100:2376
# Docker Python SDK は DOCKER_TLS_VERIFY / DOCKER_CERT_PATH 環境変数も参照します
DOCKER_TLS_VERIFY=1
DOCKER_CERT_PATH=/path/to/certs
```

---

## WebUI からの設定

チャット設定パネルの **🔬 コード実行サンドボックス** セクションで設定できます。

| フィールド | 説明 |
|-----------|------|
| コード実行を許可 | サンドボックスを ON/OFF する |
| Docker Host | 空 = グローバル設定（`MEMORY_MCP_SANDBOX__DOCKER_HOST`）に従う。`tcp://host:2375` を指定するとこのペルソナだけリモートに接続する |

ペルソナごとに異なる Docker Host を設定できます。

---

## ファイル永続化

サンドボックス内の `/workspace` は以下のホストパスにバインドマウントされます。

```
data/sandbox/{persona}/workspace/
```

- `docker-compose` 環境では `./data/sandbox/` として永続化されます。
- ファイルマネージャー（WebUI の 📁 タブ）からアップロード・ダウンロード・削除が可能です。

---

## セキュリティ上の注意

- **docker.sock マウント**はホストの Docker デーモンへのフルアクセスを許します。信頼できる環境のみで使用してください。
- **リモート Docker** を公開する場合は必ず TLS クライアント認証を設定してください。
- サンドボックスコンテナはデフォルトで `python:3.11` ベースです。インターネットアクセスが可能な点に注意してください。

---

## トラブルシューティング

### `Failed to start sandbox: ...`

- Docker が起動しているか確認: `docker info`
- docker-compose の場合: `docker-compose logs memory-mcp` でログ確認
- `/var/run/docker.sock` のマウントがあるか: `docker inspect memory-mcp | grep Binds`

### リモートホストに接続できない

- `DOCKER_HOST` の値が正しいか確認
- ファイアウォールでポート 2375/2376 が開放されているか確認
- TLS 設定を使っている場合は証明書パスが正しいか確認

### ファイルが `/workspace` に残らない

- サンドボックスが初回起動中はディレクトリ作成に少し時間がかかります
- `data/sandbox/{persona}/workspace/` がホスト側に存在するか確認してください
