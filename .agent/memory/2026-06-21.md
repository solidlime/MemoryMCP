# MEMORY

## プロジェクト概要
MemoryMCP: 日本語特化の永続記憶 MCP サーバー。SQLite + Qdrant + Ebbinghaus 忘却曲線。WebUIダッシュボード付き。
3レイヤー構造（L1:MCP拡張, L2:EventBus基盤, L3:OpenCode Plugin）。

## 学習した知識・教訓

### CSS/JS 静的ファイル分離（2026-06-21）
- chat.py: 2714行のモノリスから `<style>` (586行) と JS (1710行) を抽出、417行に縮小
- 静的ファイルサーブ: `mcp.custom_route("/static/{filepath:path}")` で実装。FastMCPは `.mount()` 未対応
- Python文字列からの抽出はWSL Pythonスクリプトで。PowerShellのヒアドキュメントは `<` 記号でパースエラー → `write` ツールで.py保存→WSLで実行
- テスト更新: `render_chat_js()` → ファイル読込 `_read_chat_js()` に切替。E402に注意

### ブラウザ自動テスト（2026-06-21）
- `agent-browser` CLI: PowerShellでは `@` エスケープ必須 (`'@eN'`)。長時間 `wait` はデーモン破壊
- WSLコマンド: `wsl -d Ubuntu -- bash -c "..."` 形式。複雑JSONは一時ファイル経由
- MemoryMCPサーバー: `.venv/bin/python -m memory_mcp.main`。`pkill` で停止

### コードベース健全化リファクタリング（2026-06-20）
- tools.py 分割: TOOL_DISPATCH + @mcp.tool() ラッパーのみ残す（2107→431行）、7カテゴリファイルに分割
- `normalize_importance()` 統一: `max(0.0,min(1.0))` 5箇所→value_objects.pyに集約
- `_VALID_EMOTIONS`: API層→domain/value_objects.pyに移動
- E402修正: `logger = getLogger()` が import より前に来るとruffエラー→import群の後に移動
- SIM105: `try/except PermissionError: pass` → `contextlib.suppress(PermissionError)`

### emotion_type → emotion 全層統一（2026-06-20）
- Pydantic v2で `Field(alias="emotion_type")` + `populate_by_name=True` 必須
- 6層の修正箇所: DB schema→domain entity→API model→MCP param→LLM prompt→frontend JS

### EventBus + SSE 基盤（2026-06-17）
- EventBus: asyncio Queueベースのpub/sub。全20 MCPツールにtool.calledイベント追加済み

### Chat ロールバック（2026-06-17）
- POST /api/chat/{persona}/sessions/{session_id}/rollback {keep_until: N}。存在しないセッションは404

### WSL2 + Docker バインドマウント（2026-06-07）
- uid合わせ。絶対パス指定。自前Dockerfile: `FROM python:3.11-slim-bullseye`

### 画像E2Eパイプライン（2026-06-08）
- OpenAI互換: `content: [{type: text}, {type: image_url}]`。DOMPurify: img許可設定追加

### コミットワークフロー
- SSHリモート: `git remote set-url origin git@github.com:solidlime/MemoryMCP.git`
- HTTPSが認証失敗する場合のフォールバック
- `ruff check → 0 errors` を維持。pytest: 1085 pass / 1 fail (test_settings既存バグ)
