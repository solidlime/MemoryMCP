# Troubleshooting Guide - Memory MCP

## NAS本番環境でのMCP接続問題

### 症状
- VS Code: "Waiting for server to respond to `initialize` request..."
- エラー: "Error sending message to http://nas:26262/mcp: TypeError: fetch failed"

### 原因の可能性

#### 1. ネットワーク・ポート問題 🌐

**確認方法**:
```bash
# NAS上でサーバーが起動しているか
ps aux | grep memory_mcp.py

# ポートがリッスンしているか
ss -tlnp | grep 26262
# または
netstat -tlnp | grep 26262

# ローカルホストからアクセスできるか
curl http://localhost:26262/health

# 外部からアクセスできるか（クライアントマシンから）
curl http://nas:26262/health
```

**修正方法**:
- ファイアウォール設定を確認：`sudo ufw status`
- ポート26262を開放：`sudo ufw allow 26262/tcp`
- NASのネットワーク設定でポート転送を確認

#### 2. サーバー起動失敗 ❌

**確認方法**:
```bash
# サーバーログを確認
tail -f /path/to/memory-mcp/logs/memory_mcp.log

# Docker環境の場合
docker logs memory-mcp

# サーバーを手動起動してエラー確認
cd /path/to/memory-mcp
source venv-rag/bin/activate
python memory_mcp.py
```

**よくある原因**:
- PyTorch CUDA依存（GPU環境で`MEMORY_MCP_EMBEDDINGS_DEVICE=cpu`に設定）
- Qdrantが起動していない
- メモリ不足
- 権限問題（ディレクトリ書き込み権限など）

#### 3. VS Code MCP Client設定 ⚙️

**正しい設定例**:
```json
{
  "mcp": {
    "servers": {
      "memory-mcp": {
        "type": "streamable-http",
        "url": "http://nas:26262/mcp",
        "headers": {
          "X-Persona": "default"
        }
      }
    }
  }
}
```

**確認ポイント**:
- ✅ URL末尾は `/mcp` （`/sse` ではない）
- ✅ ポート番号は `26262` （デフォルト）またはカスタム設定と一致
- ✅ ホスト名 `nas` が解決できる（`ping nas` で確認）
- ✅ `type` は `streamable-http`

#### 4. タイムアウト設定 ⏱️

VS Code MCP Clientのタイムアウトが短い可能性があります。

**確認方法**:
- VS Code設定で "mcp timeout" を検索
- 必要に応じてタイムアウトを延長（例: 30秒 → 60秒）

#### 5. FastMCPバージョン不一致 📦

**確認方法**:
```bash
# ローカル
pip show fastmcp | grep Version

# NAS
ssh nas "cd /path/to/memory-mcp && source venv-rag/bin/activate && pip show fastmcp | grep Version"
```

**修正方法**:
```bash
# 最新版にアップデート
pip install --upgrade fastmcp
```

---

## セッションID問題

### FastMCP streamable-httpトランスポートの仕様

FastMCPの`streamable-http`トランスポートは：
1. **initializeリクエスト**時にレスポンスヘッダー`mcp-session-id`でセッションIDを返す
2. **以降のリクエスト**では`mcp-session-id`ヘッダーにセッションIDを含める必要がある

### セッションIDなしでエラーになる場合

**症状**:
```
{"jsonrpc":"2.0","id":"server-error","error":{"code":-32600,"message":"Bad Request: Missing session ID"}}
```

**原因**:
- MCPクライアントがセッションIDをキャッシュしていない
- リクエスト間でHTTP接続が切断されている

**解決策**:
1. **MCPクライアント側**でセッションIDを保存する
   - initializeレスポンスヘッダーから`mcp-session-id`を抽出
   - 以降のリクエストヘッダーに追加

2. **テストスクリプトの例**: `test_mcp_http.py`参照
   ```python
   # initializeレスポンスからセッションIDを取得
   if "mcp-session-id" in response.headers:
       self.session_id = response.headers["mcp-session-id"]
   
   # 以降のリクエストで使用
   headers["mcp-session-id"] = self.session_id
   ```

---

## デバッグ用設定

### サーバー側のデバッグモード有効化

`memory_mcp.py`を編集：
```python
mcp = FastMCP(
    "Memory Service",
    host=_early_config.get("server_host", "127.0.0.1"),
    port=_early_config.get("server_port", 26262),
    debug=True,  # デバッグモード有効
    log_level="DEBUG"  # 詳細ログ
)
```

### 詳細ログ出力

環境変数で制御：
```bash
export MEMORY_MCP_LOG_LEVEL=DEBUG
python memory_mcp.py
```

---

## ローカルテスト環境での検証

NAS本番環境に適用する前に、必ずローカルで検証してください。

### 完全テスト手順

```bash
# 1. Qdrant + MCPサーバー起動
./test_local_environment.sh

# 別ターミナルで：

# 2. HTTP MCPエンドポイントテスト
source venv-rag/bin/activate
python test_mcp_http.py

# 期待結果: Total: 8/8 passed (100.0%)
```

### 手動検証

```bash
# 1. Health check
curl http://localhost:26262/health

# 2. Initialize（セッションID取得）
curl -v -X POST http://localhost:26262/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-Persona: default" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "test", "version": "1.0"}
    }
  }'

# レスポンスヘッダーから mcp-session-id を抽出

# 3. Tools list（セッションID使用）
curl -X POST http://localhost:26262/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-Persona: default" \
  -H "mcp-session-id: <YOUR_SESSION_ID>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
  }'
```

---

## NAS本番環境チェックリスト

デプロイ前に以下を確認：

- [ ] サーバーが起動している（`ps aux | grep memory_mcp`）
- [ ] ポート26262がリッスンしている（`ss -tlnp | grep 26262`）
- [ ] Health endpointが応答する（`curl http://localhost:26262/health`）
- [ ] Initializeが成功する（セッションIDが返る）
- [ ] ファイアウォール設定でポート開放済み
- [ ] VS Code設定のURLとポートが正しい
- [ ] `MEMORY_MCP_EMBEDDINGS_DEVICE=cpu`設定（GPU環境の場合）
- [ ] Qdrantが起動している
- [ ] ログディレクトリ・データディレクトリの書き込み権限

---

## よくある質問

### Q: ローカルでは動くのにNASでは動かない

**A**: 以下を確認してください：
1. NASのファイアウォール設定
2. ネットワーク経路（VPN、プロキシなど）
3. NASのリソース（CPU、メモリ、ディスク）
4. 環境変数の違い（特に`MEMORY_MCP_EMBEDDINGS_DEVICE`）

### Q: セッションIDエラーが出る

**A**: これは正常な動作です。FastMCPの`streamable-http`トランスポートはセッションID必須です。
- MCPクライアント（VS Code）が自動的にセッションIDを管理します
- 手動テストの場合は`mcp-session-id`ヘッダーを含めてください

### Q: initializeがタイムアウトする

**A**: 考えられる原因：
1. サーバー起動に時間がかかっている（RAGモデル初期化中）
2. ネットワーク遅延
3. VS Codeのタイムアウト設定が短い

**対策**:
- サーバーログで初期化完了を確認してからVS Codeを接続
- VS Codeのタイムアウト設定を延長
- サーバーを事前に起動しておく（自動起動設定）
