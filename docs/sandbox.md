# コード実行サンドボックス

MemoryMCP のチャットでは `llm-sandbox[docker]` を使った Python コード実行サンドボックスを利用できます。
コードはコンテナ内の IPython カーネルで実行され、結果がチャットに返ってきます。

---

## アーキテクチャ

```
ホストOS (例: Synology NAS)
│
├─ [sandbox-docker]  ← docker:dind (--privileged) ← 推奨
│   Docker デーモン (tcp://0.0.0.0:2375, TLS無効)
│   /data → ./data  ← memory-mcp と同パスで共有
│   /var/lib/docker → dind-storage (named volume)
│   └─ Python/IPython コンテナ（動的生成）
│       /workspace → /data/sandbox/{persona}/workspace/
│       cap_drop: ALL + no-new-privileges（ハードニング済み）
│
└─ [memory-mcp]
    DOCKER_HOST=tcp://sandbox-docker:2375
    /data → ./data
    ※ docker.sock マウントなし
```

- **ファイル永続化**: コンテナの `/workspace` は `data/sandbox/{persona}/workspace/` にバインドマウントされます。MemoryMCP を再起動してもファイルは残ります。
- **ペルソナ分離**: ペルソナごとに独立したワークスペースを持ちます。
- **セキュリティ**: IPython コンテナは `cap_drop: ALL` + `no-new-privileges` で動作し、`/workspace` 以外にアクセスできません。

---

## セットアップ

### 1. Docker Compose（推奨）

`docker-compose.yml` には `sandbox-docker`（DinD）サービスがデフォルトで有効になっています。

```bash
docker-compose up -d
```

起動後、WebUI のチャット設定で **コード実行を許可** をオンにするか、`.env` に以下を追記します。

```env
MEMORY_MCP_SANDBOX__ENABLED=true
MEMORY_MCP_SANDBOX__DOCKER_HOST=tcp://sandbox-docker:2375
```

その後コンテナを再起動します。

```bash
docker-compose restart memory-mcp
```

### 2. ローカル Python（サーバーを直接起動する場合）

Docker Desktop（または Docker Engine）が起動している状態で実行します。

```bash
MEMORY_MCP_SANDBOX__ENABLED=true python -m memory_mcp.main
```

この場合、ローカルの Docker ソケット（`/var/run/docker.sock` 等）が自動検出されます。

### 3. リモート Docker ホスト

別のホストで Docker デーモンを公開している場合（開発・テスト用）:

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

- **DinD**（`sandbox-docker` サービス）は `--privileged` で動作しますが、memory-mcp からは TCP 経由でのみアクセスします。`docker.sock` を memory-mcp にマウントしていないため、memory-mcp コンテナがホストの Docker デーモンを直接操作することはできません。
- **IPython コンテナ**（ユーザーコードが実行される場所）は `cap_drop: ALL` + `no-new-privileges` + `/workspace` のみのマウントで動作します。
- **リモート Docker** を公開する場合は必ず TLS クライアント認証を設定してください。
- サンドボックスコンテナはデフォルトでインターネットアクセスが可能です。必要に応じて Docker のネットワーク設定で制限してください。

---

## トラブルシューティング

### `Failed to start sandbox: ...` / Docker に接続できない

- sandbox-docker サービスが起動しているか確認: `docker-compose ps sandbox-docker`
- `MEMORY_MCP_SANDBOX__DOCKER_HOST=tcp://sandbox-docker:2375` が設定されているか確認
- ローカル Python 実行の場合は Docker Desktop が起動しているか確認: `docker info`
- docker-compose のログ: `docker-compose logs memory-mcp`

### sandbox-docker が起動しない

- `docker-compose logs sandbox-docker` でログを確認
- DinD は `--privileged` が必要です。ホストが privileged コンテナを許可しているか確認してください。

### リモートホストに接続できない

- `MEMORY_MCP_SANDBOX__DOCKER_HOST` の値が正しいか確認
- ファイアウォールでポート 2375/2376 が開放されているか確認
- TLS 設定を使っている場合は証明書パスが正しいか確認

### ファイルが `/workspace` に残らない

- サンドボックスが初回起動中はディレクトリ作成に少し時間がかかります
- `data/sandbox/{persona}/workspace/` がホスト側に存在するか確認してください

