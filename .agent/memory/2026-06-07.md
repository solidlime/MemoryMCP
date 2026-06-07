# MEMORY

## プロジェクト概要
MemoryMCP: 日本語特化の永続記憶 MCP サーバー。SQLite + Qdrant + Ebbinghaus 忘却曲線。WebUIダッシュボード付き。

## 学習した知識・教訓

### get_context 軽量化（2026-05-16）
- fullモードの返り値が膨大すぎて実用に耐えない。modeパラメータごと削除し軽量モード一本化
- `get_top_by_importance(15→8)` で ESSENTIAL STORY も半分に
- char_budget 2000→1500, snippet 120→100
- 削除した関数をテストしている場合は、残存関数にテスト対象を変更（test_goals_promises.py → _format_lightweight_response）

### goal/promise_manage memory_key 参照（2026-05-16）
- achieve/fulfill/cancel 時に memory_key があれば content 文字列一致をスキップし直接キー参照
- MCPツールラッパーで content を `str = ""`（オプショナル）にすることで、memory_key 指定時の Pydantic 必須エラー解消
- definitions.py の LLM スキーマも必ず同期更新

### sandbox 一時ファイルクリーンアップ（2026-05-16）
- `llm_sandbox` ライブラリは `/sandbox` ではなく `/tmp` に一時ファイルを作成する
- クリーンアップは `/sandbox` と `tempfile.gettempdir()` の両方を検索すべき

### MCPツール設計パターン
- flat 名単一目的ツールの方が LLM の選択精度が高い（god-tool より有利）
- コードは DRY、インターフェースは flat
- MCPツール変更時は tools.py + definitions.py + builtin.py の3点セット確認必須

### フロントエンド構造
- WebUI は 14 セクションファイルを dashboard.py が合成
- 各セクションは `render_*_tab()`（HTML）と `render_*_js()`（JS）の2関数を提供
- base.py に共通CSS・JS関数（renderEmotionBars, renderBodyStateBars 等）が定義されている
- セクション間で JS 関数や CSS が重複しがち。base.py に集約すべき

### 感情・身体状態のデータフロー
- Memory エンティティ: `emotions: dict[str, float]`（多次元）+ `emotion: str`（旧単一・フォールバック用）
- body_state: `dict[str, float]`（fatigue/warmth/arousal/heart_rate/pain）
- state_snapped_at: auto-snapshot 機能で自動記録（v020 マイグレーションで追加）
- フロントエンド表示はモーダル・概要タブでは対応済みだが、チャットパネル・グラフ詳細・メモリー一覧では未対応

### テスト設計
- 肥大化: 59ファイル 988テスト ~13,000行。行数半減が目標
- parametrize を活用し同パターンのテストを統合
- AsyncMock を非同期関数に使用（MagicMock より正確）
- In-Memory Repository パターンでモックより実体テストを優先
