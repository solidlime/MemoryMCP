# MEMORY

## プロジェクト概要
MemoryMCP: 日本語特化の永続記憶 MCP サーバー。SQLite + Qdrant + Ebbinghaus 忘却曲線。WebUIダッシュボード付き。
3レイヤー構造（L1:MCP拡張, L2:EventBus基盤, L3:OpenCode Plugin）。

## 学習した知識・教訓

### コードベース健全化リファクタリング（2026-06-20）
- tools.py 分割: TOOL_DISPATCH + @mcp.tool() ラッパーのみ残す（2107→431行）、7カテゴリファイルに分割。テストでは `event_bus = AsyncMock()` が必要
- `normalize_importance()` 統一: `max(0.0,min(1.0))` 5箇所→value_objects.pyに集約。Pydantic field_validator内でも使用可
- `_VALID_EMOTIONS`: API層のtools.py→domain/value_objects.pyに移動。テストのimportパスを修正忘れずに
- DEPRECATED endpoint削除: 3件削除。テストのアサーションを新レスポンス形式に合わせる（dashboardはstatsがネスト）
- E402修正: `logger = getLogger()` が import より前に来るとruffエラー→import群の後に移動
- SIM105: `try/except PermissionError: pass` → `contextlib.suppress(PermissionError)` でruffクリーン
- ruff --fix: W293（空白行スペース）は自動修正可能。E402（import位置）は手動修正または --unsafe-fixes が必要

### emotion_type → emotion 全層統一（2026-06-20）
- _VALID_EMOTIONS(22)とALLOWED_EMOTIONS(22)の不一致8感情を解消→_EMOTION_KEYWORD_MAPに吸収し25感情に統一
- Pydantic v2で `Field(alias="emotion_type")` + `populate_by_name=True` 必須（canonical名も受け付けるために）
- 6層の修正箇所: DB schema→domain entity→API model→MCP param→LLM prompt→frontend JS。全層漏れなく変更しないと不整合
- 変換ロジック削除: `_memory_to_dict()` の pop 変換や `updates["emotion_type"]→"emotion"` の手動変換を全削除

### EventBus + SSE + SessionEvent リアルタイムイベント基盤（2026-06-17）
- EventBus: asyncio Queueベースのpub/sub。全20 MCPツールにtool.calledイベント追加済み
- SSE: GET /api/events/{persona}?topics=memory,context
- SessionEventRecorder: EventBus→SessionEvent→Repository永続化の自動パイプライン

### Activityタブ（2026-06-17）
- カスタム縦型タイムライン。offset-basedページネーション。タブ名 `activity`
- metadata.platform 規約: webui / opencode / mcp / plugin → バッジ表示

### ブラウザ自動テスト（2026-06-17）
- agent-browser + Chrome CDP。WSLではライブラリ `sudo apt install libnspr4 libnss3 ...` が必要

### コミットワークフロー（2026-06-17）
- HTTPSリモート: `git remote set-url origin https://github.com/solidlime/MemoryMCP.git` でWSL内直接push可能

### Chat ロールバック（2026-06-17）
- POST /api/chat/{persona}/sessions/{session_id}/rollback {keep_until: N}
- 存在しないセッションは404を返す（500→404修正）

### WSL2 + Docker バインドマウント権限問題（2026-06-07）
- uid合わせ。絶対パス指定。自前Dockerfile: `FROM python:3.11-slim-bullseye`

### Lucideアイコンのraw HTMLバグ（2026-06-08）
- `el.innerHTML` 使用（`el.textContent` はHTMLエスケープ）

### 画像E2Eパイプライン（2026-06-08）
- OpenAI互換: `content: [{type: text}, {type: image_url}]`。DOMPurify: img許可設定追加

### サーバー再起動（2026-06-08）
- tmux kill-session → sleep 2 → tmux new-session。.pycキャッシュクリア必須
