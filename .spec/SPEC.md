# SPEC: ツール改善 2026-06-27

## フェーズA: 低リスク・高効果

### A1. description 短文化

#### 現状の課題
全14ツールの description が3〜5行の長文。LLM がツール選択時に全文を読む必要があり、
認知負荷が高い。Claude Code のツールはすべて1行説明。

#### 修正対象ファイル
`memory_mcp/application/chat/tools/definitions.py` の全 `ToolDef` の `description` フィールド。

#### 修正基準
- **1行目**: いつ・なぜこのツールを使うか（必須）
- **2行目**: 必須パラメータの簡単な説明（任意、長くなる場合のみ）
- **削除するもの**: 実装詳細（「内部で〜する」）、注意書き（「〜の前に〜を呼べ」）、デフォルト値の説明（スキーマに書いてある）

#### 変更内容

| ツール | Before (行数) | After (行数) | 新description |
|--------|-------------|-------------|---------------|
| memory_create | 6行 | 2行 | `"新しい記憶を作成する。ユーザーの重要な事実・好み・出来事を記録したい時に使う。importance は 0.0〜1.0（高いほど重要）。"` |
| memory_search | 3行 | 2行 | `"記憶をハイブリッド検索（意味＋キーワード）する。思い出したいことや関連情報を探す時に使う。"` |
| context_update | 3行 | 2行 | `"ペルソナの感情・状態を更新する。気分や体調が変わった時に使う。emotion には happy/sad/angry 等を指定。"` |
| invoke_skill | 3行 | 1行 | `"登録済みスキルを独立したLLMコンテキストで実行する。"` |
| goal_manage | 3行 | 2行 | `"目標の作成・達成・キャンセル。operation で create/achieve/cancel を指定。達成したら achieve で完了にする。"` |
| promise_manage | 3行 | 2行 | `"約束の作成・履行・キャンセル。operation で create/fulfill/cancel を指定。相手との約束事に使う。"` |
| memory_update | 3行 | 2行 | `"既存の記憶を検索して内容を更新する。query で検索し、最初にヒットした記憶を new_content で置き換える。"` |
| context_recall | 3行 | — | **削除（A2）** |
| browser | 16行 | 5行 | `"Webブラウザを操作する。action で open/snapshot/click/fill/press/get/wait/scroll/close を指定。\nopen→snapshot→click のループで使う。open時は url 必須、click時は ref 必須。"` |
| search | 2行 | 2行 | `"SearXNGメタサーチエンジンでWeb検索する。リアルタイム情報や最新のドキュメントを調べたい時に使う。"` |
| image_generate | 8行 | 3行 | `"画像を生成する。prompt で生成内容を英語で指定。provider で openai/stability/auto を選べる。"` |
| read_pdf | 7行 | 2行 | `"PDFファイルを解析してテキスト・テーブル・画像を抽出する。path にPDFの絶対パスを指定。"` |
| execute_code | 4行 | 2行 | `"サンドボックスコンテナ内でコードを実行する。language で python/bash を指定。計算やデータ処理に使う。"` |
| sandbox_files | 4行 | 2行 | `"サンドボックス内のファイルを操作する。operation で list/read/write/delete を指定。write時は content 必須。"` |

#### 制約
- ツールの機能的振る舞いは一切変えない（description 変更のみ）
- 既存テストは description を検証していないため影響なし

---

### A2. context_recall 削除

#### 根拠
`context_recall` は `tags` による AND 検索のみ。`memory_search` にも `tags` パラメータがあり、
`memory_search` の上位互換。独立ツールとしての存在価値がない。
ツール数を減らすことで LLM の選択肢が減り、選択精度が上がる。

#### 修正内容

**削除対象**:
1. `definitions.py` → `context_recall` の `ToolDef` 定義を削除、`MEMORY_TOOLS` リストから削除
2. `builtin.py` → `_handle_context_recall()` 関数を削除
3. `builtin.py` → `_BUILTIN_DISPATCH` 辞書から `"context_recall"` エントリを削除

**注意**: `context_recall` のハンドラが他の場所から参照されていないか事前確認が必要。

#### 制約
- `memory_search` の tags パラメータが正しく AND 検索として機能していることの確認
- 全テストパスすること

---

### A3. search パラメータ追加

#### 修正対象
`definitions.py` の `search` ツール定義。

#### 追加パラメータ

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|-----------|-----|------|-----------|------|
| `query` | str | ✅ | — | 検索クエリ（変更なし） |
| `num_results` | int | ❌ | 10 | 取得する検索結果数（1〜50） |
| `language` | str | ❌ | None | 言語フィルタ（"ja", "en" 等）。指定しない場合は制限なし |

#### 修正内容
1. `definitions.py`: search の `parameters` に `num_results` と `language` を追加
2. `builtin.py` `_handle_search()`: `num_results` を SearXNG API の `limit` にマッピング、`language` を `language` パラメータにマッピング

---

### A4. goal/promise description 差別化

#### 現状
両ツールともほぼ同じ description:
- goal_manage: "Manage goals. operation: create (new goal), achieve (mark done)..."
- promise_manage: "Manage promises. operation: create (new promise), fulfill (mark done)..."

LLM が「これって目標？約束？」と迷う原因。

#### 修正内容
A1 の変更で既に対応。以下を明確に:
- goal_manage: 「目標の作成・達成・キャンセル」→ 自分のやるべきこと
- promise_manage: 「約束の作成・履行・キャンセル」→ 相手とのやりとり

---

## フェーズB: 中リスク・高効果

### B1. context_update 自動化

#### 現状の問題
`memory_create` の description に `"**Important**: Call context_update *before* memory_create if your emotional or physical state has changed."` 
という順序制約がある。LLM に「Aの前にBを呼べ」と強制するのは悪いツール設計。
LangGraph なら ToolNode 内で `InjectedState` として自動注入するパターン。

#### 修正方針
1. `_handle_memory_create_builtin()` 内で、明示的な `context_update` が事前に呼ばれていなくても、
   現在のペルソナ状態を自動スナップショットする
2. `context_update` ツールは削除せず、明示的な状態変更用に残す（感情変化を伴わない記憶作成では呼ばなくてよい）

#### 修正対象
- `builtin.py` `_handle_memory_create_builtin()`: persona 状態の自動取得ロジック追加
- `definitions.py` `memory_create` の description から「context_update を先に呼べ」の文言を削除（A1で対応済み）

#### 実装詳細
```python
# memory_create ハンドラ内
async def _handle_memory_create_builtin(...):
    # 自動コンテキストスナップショット
    persona = await persona_service.get(persona_name)
    context_snapshot = {
        "emotion": persona.emotion,
        "emotion_intensity": persona.emotion_intensity,
        "body_state": persona.body_state,
        "mental_state": persona.mental_state,
        "context_note": persona.context_note,
    }
    # ... 既存の memory_create 処理、context_snapshot を含める
```

#### 制約
- `persona_service` がハンドラ内で利用可能であること
- 既存の `context_update` → `memory_create` のテストケースが壊れないこと

---

### B2. sandbox_files の append/Edit 操作追加

#### 現状の問題
- `write` はファイル全体置換のみ。追記ができない
- Claude Code は `Write`（全体）と `Edit`（部分置換）を分離

#### 追加操作

**`append`**:
```
operation: "append"
path: ファイルパス（必須）
content: 追記する内容（必須）
```
→ ファイル末尾に content を追記。ファイルがなければ新規作成。

**`edit`**:
```
operation: "edit"
path: ファイルパス（必須）
start_line: 置換開始行（1-indexed, 必須）
end_line: 置換終了行（1-indexed, 任意, 省略時は start_line のみ）
new_content: 新しい内容（必須）
```
→ 指定行を new_content で置換。end_line 指定時は複数行を一括置換。

#### 修正対象
1. `definitions.py` `SANDBOX_TOOLS` の `sandbox_files` 定義: `operation` enum に `append` と `edit` を追加
2. `definitions.py`: `edit` 用の `start_line`, `end_line`, `new_content` パラメータ追加
3. `api/mcp/_tools_sandbox.py` `_tool_sandbox_files()`: append/edit の実装追加
4. `application/sandbox/service.py`: 必要に応じてサンドボックス内のファイル追記/行編集API追加

---

## フェーズC: 高リスク・高効果

### C1. memory_create の重複検出

#### 現状の問題
同じ内容の `memory_create` を複数回呼ぶと、重複した記憶が作成される。
例: 「今日の天気は晴れ」を3回呼ぶ → 3つのほぼ同一の記憶。

Mem0 は `add` 時に既存記憶とのセマンティック類似度を計算し、重複時は統合する。

#### 修正方針
1. `_handle_memory_create_builtin()` 内で、作成前に以下の処理を追加:
   a. 同一 persona の既存記憶を内部で `memory_search`（top_k=5）
   b. 各結果の content と新規 content の類似度を計算
   c. 類似度 > 0.85 の記憶があれば、既存記憶を更新（`memory_update` 内部呼び出し）
   d. 類似度 < 0.85 なら通常の作成処理
2. 戻り値に `{"status": "merged", "merged_into": "key", "similarity": 0.92}` のような情報を含める

#### 考慮点
- 類似度計算のオーバーヘッド（埋め込みベクトル比較は軽量）
- 閾値 0.85 は要チューニング。環境変数で調整可能に
- 「重複だが少し違う」場合の挙動（上書き vs 別途保存）の明示

#### 修正対象
- `builtin.py` `_handle_memory_create_builtin()`
- `definitions.py` `memory_create` の description に重複検出の説明追加

---

### C2. execute_code の session_id 対応

#### 現状の問題
`execute_code` は毎回新しいサンドボックスを作成する。
`x = 1` → `print(x)` のように複数回に分けて実行できない。
OpenAI Code Interpreter は20分間のセッション状態を維持する。

#### 修正方針
1. `execute_code` に `session_id` パラメータ追加（任意、指定時は既存セッションを再利用）
2. `execute_code` に `action` パラメータ追加（`run` / `session_end`）:
   - `run`（デフォルト）: コード実行
   - `session_end`: セッションを明示的に終了（リソース解放）
3. セッション管理:
   - メモリ内 dict で `session_id → sandbox_container` を管理
   - TTL 300秒（設定可能）でアイドルセッションを自動クリーンアップ
   - `session_end` で即時解放

#### 修正対象
1. `definitions.py`: `execute_code` に `session_id` と `action` パラメータ追加
2. `builtin.py` `_handle_execute_code()`: セッション管理ロジック追加
3. `application/sandbox/service.py`: `run_code(session_id, code, language)` のセッション対応
4. テスト: セッション状態維持のテスト追加

---

## フェーズD: 軽微・任意

### D1. invoke_skill の list_skills 追加

#### 現状
LLM は利用可能なスキル一覧を知らずに `invoke_skill` を呼ぶ必要がある。

#### 修正
- `invoke_skill` のツール定義の `name` パラメータの description に、
  利用可能なスキル名一覧を動的に埋め込む
- スキル一覧は起動時に読み込み、キャッシュする
- または新規 `list_skills` ツールを追加（ツール数が増えるので非推奨）

---

### D2. browser ツール引数整理

#### 現状
`browser` ツールは11個のパラメータを持つ。`action` 値によって必須/非必須が変わる複雑な依存関係。
ただし、agent-browser の `snapshot → ref → click` ループとの親和性が高く、
一度理解すれば使いやすい。即時の大規模リファクタリングは不要。

#### 対応
A1 の description 改善で対応。「open時は url 必須、click時は ref 必須」と明記する。
