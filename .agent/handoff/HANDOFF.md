# HANDOFF - 2026-06-07 22:30

## 使用ツール
OpenCode (CLI)

## セッションで完了したこと

### 開発環境セットアップ
- .venv作成、全依存パッケージインストール (sentence-transformers/PyTorch/transformers含む)
- .env 開発設定 (MEMORY_MCP_DEVELOPMENT=true, PORT=26263)
- data/memory/{herta,rausraus} ディレクトリ作成
- Qdrant起動確認 (Docker, port 6333/26262)

### テストデータ注入
- ペルソナ作成: herta, rausraus (POST /api/personas)
- メモリ19件注入 (POST /api/memories/herta)
- プロフィール設定 (PUT /api/personas/herta/profile)

### Sandbox修正 (WSL2+Docker権限問題)
- **Dockerfile.sandbox**: python3-venv追加でSandbox環境構築完了
- **settings.py**: sandbox.image='memorymcp-sandbox:latest'
- **service.py**:
  - sandbox_internal.resolve() → 絶対パス化
  - container_configsに `"user": "1000:1000"` → WSL2権限問題解決
  - sandbox_imageでカスタムイメージ使用
- **動作確認**: print(1+1)→2, NumPy, Fibonacci, Bash 全成功

### フロントエンド修正
- base.py/chat.py/coding_agent.py: font-familyに日本語フォント追加

### チャットE2Eテスト
- agent-browserでChatタブ操作、SSEストリーミング確認
- OpenRouter + Gemini 3 Flash で日本語応答正常
- Sandbox直接API動作確認済み

## 現在の状態
- **サーバー**: tmux `mcpdev` セッションで起動中 (http://localhost:26263, 200 OK)
- **Qdrant**: Docker起動中。collection未作成（初回メモリ作成時に自動作成）
- **Sandbox**: Docker image `memorymcp-sandbox:latest` ビルド済み、ユーザー権限で正常動作

## 変更ファイル
| ファイル | 変更内容 |
|----------|----------|
| memory_mcp/api/http/sections/base.py | font-family 日本語追加 |
| memory_mcp/api/http/sections/chat.py | font-family 日本語追加 |
| memory_mcp/api/http/sections/coding_agent.py | font-family 日本語追加 |
| memory_mcp/application/sandbox/service.py | user 1000:1000, 絶対パス, custom image |
| memory_mcp/config/settings.py | sandbox.image 設定追加 |
| Dockerfile.sandbox (新規) | python3-venv追加の自前イメージ |

## 次のセッションで最初にやること
1. git commit & push
2. チャットでツール呼出し (execute_code) が発動しない問題の調査（モデル側 or システム側？）
3. sin波グラフ描画の画像レンダリング確認

## 注意点・ブロッカー
- Qdrant: collection未作成でもSQLiteフォールバックがあるので動作はする（エラーログは出る）
- Matplotlib警告（/.config/matplotlib）は無害だがMPLCONFIGDIRで解決可能
- seed.py はテストデータ注入用に作成。コミットしてなければ追加検討
- agent-browser の `@eN` ref はPowerShellで `@` が解釈されるため引用符 `"@eN"` が必要
