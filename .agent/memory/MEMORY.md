# MEMORY

## プロジェクト概要
MemoryMCP: 日本語特化の永続記憶 MCP サーバー。SQLite + Qdrant + Ebbinghaus 忘却曲線。WebUIダッシュボード付き。

## 学習した知識・教訓

### コンテキスト圧縮システム（2026-06-09）
- CompressStep: 3段階圧縮。パイプラインは PrepareStep → PromptBuildStep → CompressStep → InferenceStep → PostProcessStep
- TokenCounter: tiktoken優先 + CJKヒューリスティック。ひらがなはCJK範囲外(U+3040-U+30FF)、漢字はU+4E00-U+9FFF
- ChatConfig新規9フィールド: max_stored_messages, context_max_tokens, context_compression_threshold他
- 並列ツール実行: asyncio.gatherで独立ツールを同時実行。enable_parallel_toolsフラグで制御
- 記憶プリロード最適化: memory_preload_count=3。上位のみプリロード、残りはツール経由検索

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
