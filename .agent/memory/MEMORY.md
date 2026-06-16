# MEMORY

## プロジェクト概要
MemoryMCP: 日本語特化の永続記憶 MCP サーバー。SQLite + Qdrant + Ebbinghaus 忘却曲線。WebUIダッシュボード付き。
3レイヤー構造（L1:MCP拡張, L2:EventBus基盤, L3:OpenCode Plugin）。

## 学習した知識・教訓

### EventBus + SSE + SessionEvent リアルタイムイベント基盤（2026-06-17）
- EventBus: asyncio Queueベースのpub/sub。MCPツールのtool.called、チャットイベント、Plugin取り込みを統一的に購読可能
- SSE: GET /api/events/{persona}?topics=memory,context → EventSource接続でWebUIにトースト通知
- SessionEvent: domain/memory/session_event.py ドメインモデル + SQLite永続化 + マイグレーションv024
- SessionEventRecorder: EventBus購読→SessionEvent変換→Repository永続化の自動パイプライン
- POST /api/events/ingest: Plugin用HTTP取り込み。APIキー認証（空=開発モードでスキップ）
- **全20 MCPツールにsuccess/error両パスでtool.calledイベント追加済み**

### Activityタブ（セッション履歴タイムライン）（2026-06-17）
- カスタム縦型タイムライン採用（vis-timeline不適：離散イベントのグループ化にオーバースペック）
- offset-basedページネーション（SQLiteローカルDB、数千件規模で十分）
- タブ名 `activity`（`clock`既存Timelineタブとの混乱回避）
- metadata.platform 規約: webui / opencode / mcp / plugin → フロントでバッジ表示
- showSkeletonとの衝突: Activityタブのact-feedを破壊→除外リストに追加で解決

### ブラウザ自動テスト（2026-06-17）
- agent-browser + Chrome CDP でWebUI操作可能
- WSL環境: node v22.12.0、~/.local/nodejs/bin/ にインストール
- WSL PATH: ~/.bashrc に `export PATH=$HOME/.local/nodejs/bin:$PATH` が必要
- agent-browser: `npm i -g agent-browser` → `agent-browser install`（Chrome自動ダウンロード）
- WSL Chrome: ライブラリ不足時は `sudo apt install libnspr4 libnss3 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libasound2` 必要

### コミットワークフロー（2026-06-17）
- HTTPSリモートに切り替えるとWSL内から直接git push可能（SSH鍵不要）
- 操作: `git remote set-url origin https://github.com/solidlime/MemoryMCP.git`

### Chat ロールバック（2026-06-17）
- SessionWindow.truncate_to(index) で指定インデックス以降を削除 → SQLiteに_persist()
- POST /api/chat/{persona}/sessions/{session_id}/rollback {keep_until: N}
- 存在しないセッション: 500→404修正（try-exceptラップ）

### WSL2 + Docker バインドマウント権限問題（2026-06-07）
- WSL2環境でDockerコンテナがホストのファイルを読めない場合、UID合わせ
- バインドマウントのパスは絶対パス指定

### Sandbox Dockerイメージ（2026-06-07）
- 自前Dockerfile: `FROM python:3.11-slim-bullseye`

### Lucideアイコンのraw HTMLバグ（2026-06-08）
- `el.textContent` はHTMLエスケープ。アイコンには `el.innerHTML` 使用

### 画像E2Eパイプライン（2026-06-08）
- OpenAI互換: `content: [{type: text}, {type: image_url}]` 形式
- DOMPurify: imgタグ除去防止にALLOWED_TAGS+ALLOWED_ATTR追加

### サーバー再起動（2026-06-08）
- tmux kill-session → sleep 2 → tmux new-session
- .pycキャッシュクリア必須
