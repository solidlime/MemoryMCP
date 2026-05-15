# PLAN - やりたいこと

## フロントエンド・ツール改善（2026-05-15）
チャットWebUI・MCPツールの包括的監査に基づく改善計画。4フェーズに分割。

### 🔴 Phase 1: バグ修正（即効・低工数）
- [ ] **旧サンドボックスパネルの死にコード削除** — `chat.py` の CSS 255-416行 + JS 1665-2100行。`#sandbox-panel`, `#sandbox-terminal` 等のDOM要素は既に存在しない
- [ ] **MEMORY_TOOL_NAMES にbuiltinツール追加** — `chat.py:1673` の Set がMCPツール5個だけで、`memory_create` 等12個不在。メモリパネルにツール結果が表示されない
- [ ] **caAppendOutput をグローバル公開** — `coding_agent.py:426` の `_appendOutput` を `window.caAppendOutput` に。sandbox結果がCoding Agentパネルに届かない
- [ ] **switchSandboxTab/sandboxExecuteCmd の二重定義削除** — `chat.py:1744` と `chat.py:2059` の重複
- [ ] **promise_cancel 追加** — `goal_create/achieve/cancel` に対し promise は create/fulfill のみ。非対称
- [ ] **sandbox_files list 空問題** — `service.py:list_files` の `entry.stat()` が単一ファイルのOSErrorでループ全体を殺す → エントリ毎try/except化（実装済み、要デプロイ）
- [ ] **bash実行時の `!` プレフィックス自動除去** — `language="bash"` 時に `!ls` がシェルで解釈不可 → 自動strip（実装済み、要デプロイ）

### 🟡 Phase 2: 設定UIの欠落（低工数）
- [ ] **enable_memory_tools トグル追加** — チャットLLMに組み込みツールを渡すか制御不可。設定パネルにチェックボックス追加
- [ ] **extract_max_tokens 入力欄追加** — 事実抽出のトークン制限が512固定。`auto_extract` の横に数値入力追加
- [ ] **設定の保存ボタンをsticky footer化** — 全スクロール必須の問題

### 🟠 Phase 3: UX改善（中工数）
- [ ] **設定パネルをアコーディオン化** — 10セクションが280pxサイドバーにフラットスクロール → `<details>` で折りたたみ
- [ ] **リトライ/編集ボタン** — 最後のアシスタント応答を再生成、ユーザー入力を編集して再送
- [ ] **スラッシュコマンド** — `/memory`, `/goal`, `/code` でクイック操作。`chat-input` のkeydown監視
- [ ] **デバッグモードトグル** — バックエンドにあるdebugモードをUIからON/OFF
- [ ] **Alt+1〜9ショートカットにChatタブ追加** — `base.py:866` に `'chat'` を追加
- [ ] **温度スライダー値の初期表示修正** — `applyChatConfig()` でスライダー値を明示更新
- [ ] **添付ファイル表示ラベル復活** — `chat.py:1462` で `CHAT.attachments` をクリアする前に数を保存
- [ ] **console.log → console.debug** — 本番にデバッグログが露出

### 🔵 Phase 4: 新機能（高工数）
- [ ] **メモリパネルにCRUD操作** — 記憶カードをクリック→編集/削除、goal完了操作を直接UIから
- [ ] **メモリタイムライン可視化** — 感情色付きの記憶履歴タイムライン（vis-network活用）
- [ ] **スキルベースのシステムプロンプトテンプレート** — ドロップダウンで切替
- [ ] **音声入力 🎤** — Web Speech API
- [ ] **会話エクスポート** — チャットをMarkdown/JSON出力
- [ ] **Web検索トグル** — チャット入力に「🌐 Web検索」追加

### 🟣 Phase 5: ツール不整合（低〜中工数）
- [ ] **MCP `memory` ツールの死にパラメータ削除** — `context_tags`, `description`, `status` 未使用
- [ ] **importance検証統一** — MCP createが黙ってclamp、updateがエラー返却 → 両方エラーに統一
- [ ] **builtin `memory_search` の結果上限を200に** — 現在10件キャップ（MCPは200）
- [ ] **builtinの感情検証追加** — MCPは `_VALID_EMOTIONS` 21種検証、builtinはスルー
- [ ] **`search_memory` の死に `mode` パラメータ削除**

### 🟢 sandbox 追加修正（2026-05-15）
- [x] **_cleanup_stale_sandbox_container をPython Docker SDKに** — subprocess `docker rm -f` がmemory-mcpコンテナにdocker CLI不在で無言失敗 → `docker.from_env()` に変更（実装済み、要デプロイ）
- [ ] **sandboxコンテナ手動掃除（1回限り）** — NAS上で `sudo docker exec sandbox-docker docker rm -f sandbox-herta`
- [ ] **NASで `docker-compose build --no-cache memory-mcp && docker-compose up -d`** — 全修正をデプロイ

## Hindsight 分析（2026-05-13）
vectorize-io/hindsight（13.2k stars）を分析し、MemoryMCP とのギャップを特定。

### 既に実装済み（Hindsight相当以上）
- Semantic 検索: Qdrant + ruri-v3 ローカル埋め込み
- Keyword 検索: SQLite LIKE
- Graph 検索: entity_graph / entity_search / entity_add_relation
- RRF 融合: RRFRanker（k=60）
- Cross-encoder リランキング: RerankerModel（japanese-reranker-xsmall-v2）
- Reflect（内省）: reflection.py（Generative Agents スタイル）
- 矛盾検出: check_contradictions
- セッション要約: LLMベース + 日次要約ワーカー
- エンティティ抽出: 正規表現ベース（人物・場所）
- 自動タイプ分類: 5タイプ（decision/preference/milestone/problem/emotional）
- LLM連携: Anthropic / OpenAI / OpenRouter

### 改善候補（優先度順）

#### 🔴 P1: date_range 検索フィルタ統合
- parse_date_range() は実装済みだが、実際の検索SQLに未統合
- search_keyword() と Qdrant search() に date_range フィルタを追加
- これだけで時系列検索が機能するようになる

#### 🟠 P2: 重要度の自動評価
- 現在 importance は手動設定のみ（デフォルト0.5）
- 案1: LLM で自動評価（openai/anthropic API使用）
- 案2: ヒューリスティック（単語数・感情強度・タイプなどから計算）
- type_classifier の結果を importance 計算に活用できるかも

#### 🟡 P3: 関係性の自動抽出
- エンティティ抽出はあるが、エンティティ間の関係性は手動 add_relation のみ
- 案1: LLM で「AはBの〜」パターンを抽出
- 案2: 日本語構文解析（係り受け）で抽出
- Hindsight の Retain 相当の完全自動構造化を目指す

#### 🟢 P4: メンタルモデル / 抽象化レイヤー
- 複数記憶からのパターン抽出・抽象化
- 例: 「ユーザーは朝コーヒーを飲む」×3回 → 「ユーザーは朝コーヒーを飲む習慣がある」
- 新規設計が必要。Hindsight の Mental Models を参考に
- Reflection の延長線上にある概念

#### その他（余裕があれば）
- BM25 キーワード検索（現在 LIKE）
- 感情自動分析（emotion_type 自動設定）
- Ollama 等ローカルLLM対応
- LongMemEval ベンチマーク参加検討

### MemoryMCP の独自強み（維持すべき）
- MCP ネイティブ（REST + MCP 両対応）
- ペルソナ管理（感情・装備・状態）
- SQLite 軽量運用
- LLM なしで動作可能
- Memory Blocks / 物理アイテム管理
