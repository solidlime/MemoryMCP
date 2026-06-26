# SPEC: ツール対策 2026-06-27 (v4 — テストギャップ反映)

## 前提
- MCP後方互換 **不要**。`promise_manage` は全層から完全削除
- chat.js の `/promise` スラッシュコマンド・`fulfillPromise()` 関数も削除
- **#13（goal list）を #1 に統合**。同一 _tools_goal.py の2回改修を回避
- **#0（memory_llm.py テスト）を #1 の前提条件に**。テスト0件での大規模改修は不可

## レイヤー構造（実装者向け参照）
```
definitions.py（チャットLLM用スキーマ）
    ├─ builtin.py（ビルトインハンドラ） ← 直接実装 or MCP委譲
    └─ api/mcp/tools.py（@mcp.tool() 登録）
           └─ api/mcp/_tools_*.py（共有実装） ← 両層共通
```
**注意**: `memory_create`/`memory_search`/`memory_update` は両層に別実装あり。片方だけの修正で不整合が生じる。

---

## 🔴 最優先

### #0. memory_llm.py テスト新規作成 🆕

#### 対象ファイル
`memory_mcp/application/chat/memory_llm.py`（571行）

#### テストファイル
新規作成: `tests/unit/test_memory_llm.py`

#### 0.1 `_parse_memory_llm_result()` テスト
LLMのJSON応答パーサ。以下のケースをカバー:
```python
# 正常系
parse_valid_full_json()          # facts, goals, context_update, inventory_update 全フィールド
parse_json_with_facts_only()     # facts のみ、他は空
parse_json_with_goals_only()     # goals のみ
parse_empty_dict()               # {}
parse_markdown_codeblock()       # ```json ... ``` でラップされたJSON
parse_list_format_compat()       # 後方互換: リスト形式の古い出力
parse_goals_with_fulfill_action() # action: "fulfill" (旧promise)
parse_goals_with_scope()         # scope: "self" | "interpersonal"

# 異常系
parse_invalid_json()             # 不正なJSON文字列 → 空結果 or エラー
parse_empty_string()             # "" → 空結果
parse_none_input()               # None → 空結果
parse_missing_required_fields()  # facts キー欠落 → デフォルト値
parse_extra_fields_ignored()     # 未知キー → 無視
parse_nested_text_markdown()     # 説明文中の ``` に釣られない
```

#### 0.2 `_build_memory_llm_context()` テスト
```python
# 引数: commitments (goal+promiseのリスト), equipment_summary (str)
context_empty()                  # 空のcommitments + 空のequipment
context_goals_only()             # goals のみ
context_promises_only()          # promises のみ (scope="interpersonal")
context_mixed()                  # goals + promises 混在
context_with_equipment()         # 装備品あり
context_with_long_commitments()  # 10件以上のgoal/promise
```

#### 0.3 `_MEMORY_LLM_PROMPT` フォーマットテスト
```python
prompt_format_all_placeholders() # persona_name, user_name, persona_gender, ... 全埋め込み
prompt_format_partial_info()     # 一部のユーザー情報が未設定
prompt_no_format_errors()        # 不正なプレースホルダがないことの確認
```

#### 0.4 `run_context_housekeeping()` パーステスト
```python
housekeeping_valid_result()      # 正常なhousekeeping結果のパース
housekeeping_invalid_json()      # 不正JSON → 空リスト返却
housekeeping_no_cancellations()  # キャンセル対象なし
```

---

### #1. promise_manage 完全削除 + goal_manage 統合 + operation "list" 追加

#### 修正内容（v3同様、以下略）

**A. definitions.py** — 変更:
```python
ToolDefinition(
    name="goal_manage",
    description="目標・約束の作成・一覧・達成・キャンセル。operation: create/list/achieve/cancel。scope: self/interpersonal。",
    input_schema={
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["create", "list", "achieve", "cancel"]},
            "content": {"type": "string", "description": "内容（create時に必須）"},
            "importance": {"type": "number", "description": "重要度 0.0〜1.0", "default": 0.75},
            "scope": {"type": "string", "enum": ["self", "interpersonal"], "description": "目標種別", "default": "self"},
            "memory_key": {"type": "string", "description": "memory_key（achieve/cancel時に直接指定可能）"},
        },
        "required": ["operation", "scope"],
    },
),
```
`promise_manage` ToolDefinition 削除。`_MEMORY_MCP_TOOL_NAMES` から `"promise_manage"` 削除。

**B〜R** — v3 SPEC と同一（v3 の #1-A 〜 #1-R をそのまま踏襲）

#### 削除・修正リスト（完全版）
v3 の完全リスト（25ファイル）から変更なし。

---

### #2. memory_update 安全化

（v3 と同一）

---

## 🟡 高優先

### #3. memory_search フィルタ追加
### #4. browser description 強化
### #5. sandbox_files required 関連改善
### #6. 制限値のツール定義可視化

（v3 と同一）

---

## 🟢 低優先

### #7. memory_create 重複検出
### #8. execute_code session_id 対応
### #9. description 短文化（全13ツール）
### #10. context_update 自動化
### #11. sandbox_files append/edit 追加
### #14. README context_recall 記述削除

（v3 と同一）

---

### #15. builtin.py ハンドラのパラメータ検証テスト 🆕

#### 対象
`memory_mcp/application/chat/tools/builtin.py`

#### テストファイル
新規作成: `tests/unit/test_builtin_handlers.py`

#### 15.1 `_handle_browser` パラメータ検証
```python
# 外部プロセス呼出し部（agent-browser CLI）は async subprocess を mock
test_browser_action_required()   # action未指定 → エラー
test_browser_unknown_action()    # 未知action → エラー
test_browser_open_no_url()       # open で url未指定 → エラー
test_browser_click_no_ref()      # click で ref未指定 → エラー
test_browser_fill_no_ref()       # fill で ref未指定 → エラー
test_browser_press_no_key()      # press で key未指定 → エラー
test_browser_valid_open()        # open + url → subprocess 呼出し確認
```

#### 15.2 `_handle_execute_code` パラメータ検証
```python
test_execute_empty_code()        # code未指定 → エラー
test_execute_sandbox_disabled()  # sandbox無効 → エラー
test_execute_valid_python()      # python実行 → sandbox session呼出し確認
test_execute_valid_bash()        # bash実行 → 同
```

#### 15.3 `_handle_image_generate` パラメータ検証
```python
test_image_empty_prompt()        # prompt未指定 → エラー
test_image_invalid_provider()    # 不明provider → デフォルト使用 or エラー
test_image_openai_call()         # openai provider → factory呼出し確認
test_image_stability_call()      # stability provider → 同
```

#### 15.4 `_handle_search` パラメータ検証
```python
test_search_empty_query()        # query未指定 → エラー
test_search_num_results_boundary() # num_results=0/@1/@10/@100 の境界
test_search_with_language()      # languageパラメータ伝搬確認
```

---

### #16. definitions.py スキーマ整合性テスト 🆕

#### 対象
`memory_mcp/application/chat/tools/definitions.py`（309行）

#### テストファイル
新規作成: `tests/unit/test_tool_definitions.py`

```python
def test_all_required_keys_exist_in_properties():
    """全 ToolDefinition で required 配列の全キーが properties に存在することを検証"""
    for td in MEMORY_TOOLS + SANDBOX_TOOLS:
        for req in td.input_schema.get("required", []):
            assert req in td.input_schema["properties"]

def test_all_enums_are_non_empty():
    """全 ToolDefinition で enum 制約が空でないことを検証"""
    for td in MEMORY_TOOLS + SANDBOX_TOOLS:
        for prop in td.input_schema.get("properties", {}).values():
            if "enum" in prop:
                assert len(prop["enum"]) > 0

def test_no_duplicate_tool_names():
    """ツール名の重複がないことを検証"""
    names = [td.name for td in MEMORY_TOOLS + SANDBOX_TOOLS]
    assert len(names) == len(set(names))

def test_scope_enum_values():
    """#1 変更後: goal_manage の scope enum が ["self", "interpersonal"] であること"""
    goal_td = next(td for td in MEMORY_TOOLS if td.name == "goal_manage")
    assert goal_td.input_schema["properties"]["scope"]["enum"] == ["self", "interpersonal"]

def test_promise_manage_removed():
    """#1 変更後: promise_manage が存在しないこと"""
    names = [td.name for td in MEMORY_TOOLS + SANDBOX_TOOLS]
    assert "promise_manage" not in names
```

---

### #17. テスト保守性改善 🆕

#### 17.1 mock_app_context フィクスチャの conftest.py 集約
- `test_mcp_memory.py`, `test_mcp_goals_promises.py`, `test_mcp_sandbox.py` の3重定義を `conftest.py` に統合
- `scope` パラメータで必要なサービス数を制御（例: `mock_app_context("full")`, `mock_app_context("minimal")`）

#### 17.2 patch ボイラープレートのヘルパー化
```python
# conftest.py に追加
from contextlib import asynccontextmanager

@asynccontextmanager
async def mcp_tool_context(mock_ctx, persona="test_persona"):
    with (
        patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg,
        patch("memory_mcp.api.mcp.tools.get_current_persona", return_value=persona),
    ):
        mock_reg.get_instance.return_value = mock_ctx
        yield mock_reg
```

#### 17.3 asyncio.run() → await 置換
- `test_session_event_recorder.py` の `asyncio.run(recorder._on_event(...))` を `@pytest.mark.asyncio` + `await` に

#### 17.4 アサーション具体化
- `test_mcp_memory.py` の `assert "Error" in result` → `assert "not found" in result` / `assert "invalid" in result` 等のエラー種別部分一致に

---

## スコープ外
- 新ツール追加
- 外部MCPクライアント統合改善
- _tools_sandbox.py リファクタリング
- CHANGELOG.md 履歴修正
- chat.js のテストフレームワーク導入
