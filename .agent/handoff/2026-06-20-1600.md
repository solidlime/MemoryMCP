# HANDOFF - 2026-06-17

## 使用ツール
OpenCode（Orchestrator + Fixer + Oracle + Explorer + Librarian）

## 現在のタスクとプロジェクト状態

### 完了したタスク一覧（全12タスク）
- [x] **E1**: EventBus pub/sub基盤（10イベント定義、非同期発行、エラー分離）
- [x] **E2**: SSEエンドポイント GET /api/events/{persona}?topics=memory,context
- [x] **E2+**: tool.calledイベントを全20 MCPツールに追加（success/error両パス）
- [x] **SE1**: SessionEventエンティティ + SessionEventRepository + マイグレーションv024
- [x] **SE2**: SessionEventRecorder（EventBus購読→永続化）
- [x] **SE3**: チャットイベント（chat.message/llm_response/compact）発行（chat_service.py）
- [x] **CHAT-UNDO**: rollback/edit/regenerateボタン（SessionWindow.truncate_to + POST rollback）
- [x] **E3**: POST /api/events/ingest（Plugin用HTTP取り込み + APIキー認証）
- [x] **SE4**: Activityタブ（WebUIセッション履歴タイムライン表示）— カスタム縦型タイムライン
- [x] ruff lint 14→0修正 + CI緑 + テスト162 pass
- [x] ブラウザ実動作テスト（全13タブ正常）

### 品質状態
- ruff: 0 errors（新規コードのみ。既存19件は別PRで）
- テスト: 416 pass, 7 skip, 1 pre-existing fail
- 全13タブ: Overview/Memories/Chat/Activity/Settings/Analytics/Timeline/Graph/Import-Export/Personas/Admin いずれも正常

## 試したこと・結果
- ✅ 3レイヤー構造設計（L1:MCP拡張, L2:EventBus基盤, L3:OpenCode Plugin）→ 実装はL1+L2完了、L3未着手
- ✅ SSE E2E: MCP→EventBus→SSE→WebUIトーストの全パイプライン確認
- ✅ agent-browserでブラウザ自動テスト（ActivityタブのshowSkeletonバグ発見→修正）
- ❌ SSHキー未設定でgit pull/push不可 → HTTPSリモートに切り替えで解決
- ✅ WSL node v22.12.0 ~/.local/nodejs/bin にインストール・PATH永続化

## 未着手タスク（次のセッション候補）

### 高優先度
1. **L3: OpenCode Plugin（TypeScript）**: PreToolUse/PostToolUse/SessionStart/Stop/PreCompactフック→HTTP POST /api/events/ingest。~80-100行想定。
2. **L1: MCP拡張（context-modeからの移植）**:
   - M1: FTS5全文検索（bm25, unicode61 tokenizer）
   - M2: ingestツール（URL/markdown→チャンク→memory_create）
   - M3: batchツール
   - M4: 近接性リランキング
3. **Chromeライブラリ不足**: WSLでライブラリインストールすればブラウザ自動テスト可能

### 中優先度
4. **ruff既存19件の修正**
5. **APIの500エラー修正**: 存在しないアイテム削除、エクスポート
6. **データベース肥大**: 42 unique tagsでタグの重複整理

## 注意点・ブロッカー
- HTTP remoteに切り替え済み: `https://github.com/solidlime/MemoryMCP.git`
- サーバー起動: `python -m memory_mcp`（ポート26262）
- サーバー停止: `fuser -k 26262/tcp`
- WSL内agent-browser: `wsl bash -lic "cd /home/rausraus/Code/MemoryMCP && agent-browser ..."`
- テスト: `python -m pytest tests/ -x -q`
- `.venv/` と `_api_test.py` 等はgitignoreされてない（意図的に除外）
