# Claude Desktop セットアップ

## トランスポートモード自動検出

`memory_mcp.py` は起動方法を自動検出して適切なトランスポートを選択します：

| モード | 用途 | 判定条件 |
|--------|------|----------|
| `stdio` | Claude Desktop | stdin がパイプ接続（TTY でない）または `--stdio` フラグ |
| `streamable-http` | Open WebUI / LibreChat / ブラウザ | 手動起動（stdin が TTY） |

**フラグ不要**: Claude Desktop から起動すると stdin が自動的にパイプ接続となり、
stdio モードが自動選択されます。

---

## Claude Desktop 設定

`claude_desktop_config.json` に以下を追加してください：

### Linux / macOS

```json
{
  "mcpServers": {
    "memory-mcp": {
      "command": "python",
      "args": ["/path/to/memory-mcp/memory_mcp.py"],
      "env": {
        "PERSONA": "herta"
      }
    }
  }
}
```

### Windows (venv)

```json
{
  "mcpServers": {
    "memory-mcp": {
      "command": "C:/path/to/memory-mcp/venv-rag/Scripts/python.exe",
      "args": ["C:/path/to/memory-mcp/memory_mcp.py"],
      "env": {
        "PERSONA": "herta"
      }
    }
  }
}
```

### WSL

```json
{
  "mcpServers": {
    "memory-mcp": {
      "command": "wsl",
      "args": [
        "-e", "bash", "-c",
        "cd /home/rausraus/memory-mcp && source venv-rag/bin/activate && python memory_mcp.py"
      ],
      "env": {
        "PERSONA": "herta"
      }
    }
  }
}
```

---

## ペルソナ指定の優先順位

| 優先度 | 方法 | 用途 |
|--------|------|------|
| 1 (最高) | HTTP `Authorization: Bearer {persona}` | Open WebUI / LibreChat |
| 2 | HTTP `X-Persona: {persona}` | 後方互換 |
| 3 | `PERSONA` 環境変数 | **stdio / Claude Desktop 推奨** |
| 4 | `--persona herta` CLI フラグ | `PERSONA` 未設定時の fallback |
| 5 (最低) | `default` | 何も指定なし |

> **推奨**: Claude Desktop では `env.PERSONA` で指定するのが最もシンプルで確実です。

---

## 多クライアント・多ペルソナ同時アクセス

v2 以降、複数クライアントが異なるペルソナで同時アクセスしても安全です：

| 機能 | 対応状況 | 実装 |
|------|----------|------|
| HTTP 同時接続（異なるペルソナ） | ✅ 完全分離 | 別 DB / 別 Qdrant コレクション |
| HTTP 同時接続（同一ペルソナ） | ✅ 安全 | WAL モード + busy_timeout + atomic write |
| `persona_context.json` 書き込み | ✅ 競合なし | ペルソナ別 `threading.Lock` + `os.replace` |
| ベクトルストア idle rebuild | ✅ 正確 | `VectorStoreState._dirty_personas` (ペルソナ別辞書) |
| 自動サマリ / クリーンアップ | ✅ 全ペルソナ対応 | `_get_all_personas()` で全ディレクトリを走査 |

---

## 設定ファイルの場所

| OS | パス |
|----|------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/claude/claude_desktop_config.json` |

---

## ログ確認

stdio モードでのすべての出力はファイルに書き込まれます（stdout は JSON-RPC プロトコル専用）：

```bash
tail -f logs/memory_mcp.log
```

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| ツールが表示されない | ログファイルでエラーを確認 |
| ペルソナが切り替わらない | `env.PERSONA` の値を確認 |
| RAG エラー | Qdrant が起動しているか確認（`docker-compose up -d`） |
| `database is locked` エラー | DB の WAL 有効化のため一度接続して再起動 |
