# MEMORY

## プロジェクト概要
MemoryMCP: 日本語特化の永続記憶 MCP サーバー。SQLite + Qdrant + Ebbinghaus 忘却曲線。WebUIダッシュボード付き。

## 学習した知識・教訓

### WSL2 + Docker バインドマウント権限問題（2026-06-07）
- WSL2環境でDockerコンテナがホストのバインドマウントファイルを読めない場合、コンテナのユーザーIDをホストのUID(1000)に合わせる
- Dockerコンテナ設定に `"user": "1000:1000"` を追加すれば解決
- バインドマウントのパスは必ず絶対パス（`Path.resolve()`）で指定する

### Sandbox Dockerイメージのカスタムビルド（2026-06-07）
- ghcr.io/vndee/sandbox-python-311-bullseye が401になる場合、自前Dockerイメージをビルド
- Dockerfile.sandbox: `FROM python:3.11-slim-bullseye` + `python3-venv`

### Lucideアイコンのraw HTMLバグ修正（2026-06-08）
- `el.textContent` はHTMLタグをエスケープする → アイコンには `el.innerHTML` を使う
- `.pyc` キャッシュクリアしないとPython Webアプリの変更が反映されない

### 画像E2Eパイプライン（2026-06-08）
- LLMマルチモーダル: OpenAI互換APIでは `content: [{type: "text", text: "..."}, {type: "image_url", image_url: {url: "data:..."}}]` 形式
- 既存の content_parts 変換ロジック（inference.py L136-186）を流用し、ユーザー画像も同形式で注入
- OpenRouter: 画像対応はモデル依存。gpt-4oは動作、Claude Sonnet 4は非対応、kimi-k2.6も未確認
- DOMPurify: デフォルトでimgタグ除去。ALLOWED_TAGSに'img'、ALLOWED_ATTRに'src','alt'が必要
- フロントエンド画像送信: FileReader + readAsDataURLでbase64変換 → POST bodyのimages配列に格納
- PDFプレビュー: `<iframe>` でブラウザネイティブ表示
- 音声プレビュー: `<audio controls>` で再生

### サーバー再起動の注意点（2026-06-08）
- tmux kill-session -t mcpdev → sleep 2 → tmux new-session -d -s mcpdev
- 変更反映には `.pyc` キャッシュクリアが必須
