# MEMORY

## プロジェクト概要
MemoryMCP: 日本語特化の永続記憶 MCP サーバー。SQLite + Qdrant + Ebbinghaus 忘却曲線。WebUIダッシュボード付き。

## 学習した知識・教訓

### herta-memory ツール改修（2026-05-16）
- goal_manage/promise_manage は `memory_key` で直接参照可能に。`_tool_goal_manage()`/`_tool_promise_manage()` のachieve/fulfill/cancel分岐で、memory_key指定時はcontent文字列一致をスキップして直接キー参照
- memory_read は limit/offset でページネーション可能に。find_recent/get_recent チェーンに offset 追加、SQLite も LIMIT/OFFSET 対応
- MCPツールラッパー変更時は definitions.py のLLMスキーマも忘れず更新

### フロントエンド大幅改良（2026-05-15）
- chat.py は Python 文字列リテラル内に HTML/CSS/JS を内包する特殊構造。編集時は構文チェック必須
- 設定パネルHTMLは `<details><summary>` アコーディオン化で9セクションに整理。CSSは `.details-body` で内側余白制御
- Sandbox panel 削除時、`sandboxLog`/`sandboxRunBlock`/`sandboxAddArtifact`/`renderCodeBlock` はコードブロックRunボタンで現役のため保持必須
- `MEMORY_TOOL_NAMES` はMCPツール名5個 → builtinツール12個追加で17個に。メモリパネルへのツール結果反映に必須
- `/api/chat/{persona}/tool` エンドポイント新設。builtinツールのHTTP直接実行に使用
- `promise_cancel` は `builtin.py` + `definitions.py` に `goal_cancel` 同パターンで追加

### テスト更新パターン
- 削除した関数をテストしている場合は、同機能の残存関数にテスト対象を変更
- 削除したパラメータをテストしている場合は、新しいデフォルト値に期待値を変更
- インターフェースにパラメータ追加時は全モックのシグネチャも更新

### WebUI 構造
- ダッシュボード: dashboard.py が各セクションの render 関数を呼び出し
- 新規タブ追加手順: (1) sections/新規ファイル作成 (2) __init__.py エクスポート (3) dashboard.py 登録 (4) base.py ショートカット+skeleton追加
- showSkeleton: 自前ローディング状態を持つタブ（graph, import-export, personas, chat, timeline）はスキップ必須
