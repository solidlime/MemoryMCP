# MEMORY

## プロジェクト概要
MemoryMCP: 日本語特化の永続記憶 MCP サーバー。SQLite + Qdrant + Ebbinghaus 忘却曲線。WebUIダッシュボード付き。

## 学習した知識・教訓

### WSL2 + Docker バインドマウント権限問題（2026-06-07）
- WSL2環境でDockerコンテナがホストのバインドマウントファイルを読めない場合、コンテナのユーザーIDをホストのUID(1000)に合わせる
- Dockerコンテナ設定に `"user": "1000:1000"` を追加すれば解決
- chmod 777 だけでは不十分（既存ファイルには効くが新規作成ファイルはumask制限を受ける）
- バインドマウントのパスは必ず絶対パス（`Path.resolve()`）で指定する

### Sandbox Dockerイメージのカスタムビルド（2026-06-07）
- ghcr.io/vndee/sandbox-python-311-bullseye が401になる場合、自前Dockerイメージをビルド
- Dockerfile.sandbox: `FROM python:3.11-slim-bullseye` + `python3-venv`（sandbox環境構築に必要）
- settings.py に `sandbox.image` 設定を追加して参照

### フロントエンド日本語フォント（2026-06-07）
- base.py/chat.py/coding_agent.py の font-family に `'Yu Gothic', 'Noto Sans JP'` 等の日本語フォントを明示追加
- システムフォントのみに依存すると環境によって表示品質が低下する

### Qdrant 稼働確認（2026-06-07）
- Qdrantは本番ポート26262、開発ポート6333でDocker稼働。6333で疎通確認可能

### MemoryMCP v2.0.0 起動構成（2026-06-07）
- main.py: FastMCP streamable-httpサーバー、ポート26263
- tmuxセッション `mcpdev` で永続化：`tmux new-session -d -s mcpdev 'cd ... && .venv/bin/python -m memory_mcp.main'`
- .envに DEVELOPMENT=true でデバッグログ・sandbox/etcオフ設定
