"""MEMORY_TOOLS: チャット組み込みツール定義。"""

from __future__ import annotations

from memory_mcp.infrastructure.llm.base import ToolDefinition

MEMORY_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="memory_create",
        description="新しい記憶を作成する。重要な情報・感情・出来事を記録する際に使用。",
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "記憶の内容"},
                "importance": {"type": "number", "description": "重要度 0.0〜1.0", "default": 0.6},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "タグリスト"},
                "emotion_type": {
                    "type": "string",
                    "description": "感情タイプ（joy/sadness/anger/fear/neutral等）",
                    "default": "neutral",
                },
            },
            "required": ["content"],
        },
    ),
    ToolDefinition(
        name="memory_search",
        description="記憶を検索する。ユーザーについての情報・過去の出来事を調べる際に使用。",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "検索クエリ"},
                "top_k": {"type": "integer", "description": "取得件数（1〜10）", "default": 5},
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="context_update",
        description="ペルソナ自身の感情・状態を更新する。感情が変わった際に使用。",
        input_schema={
            "type": "object",
            "properties": {
                "emotion": {"type": "string", "description": "感情タイプ"},
                "emotion_intensity": {"type": "number", "description": "感情強度 0.0〜1.0"},
                "mental_state": {"type": "string", "description": "精神状態の説明"},
            },
        },
    ),
    ToolDefinition(
        name="invoke_skill",
        description="特定のスキルを専用コンテキストで実行する。複雑な専門タスクをメインの会話から切り離して処理する",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "スキル名"},
                "task": {"type": "string", "description": "スキルへの具体的な指示"},
            },
            "required": ["name", "task"],
        },
    ),
    ToolDefinition(
        name="goal_create",
        description="目標を設定する。ユーザーが「〜したい」「〜を目指す」「〜するつもり」と言ったら積極的に使う。",
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "目標の内容（具体的に）"},
                "importance": {"type": "number", "description": "重要度 0.0〜1.0", "default": 0.75},
            },
            "required": ["content"],
        },
    ),
    ToolDefinition(
        name="goal_achieve",
        description="目標を達成済みにする。ユーザーが目標を達成したと言ったら使う。",
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "達成した目標の内容（部分一致でOK）"},
            },
            "required": ["content"],
        },
    ),
    ToolDefinition(
        name="goal_cancel",
        description="目標をキャンセルする。",
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "キャンセルする目標の内容（部分一致でOK）"},
            },
            "required": ["content"],
        },
    ),
    ToolDefinition(
        name="promise_create",
        description="約束・コミットメントを記録する。私（ペルソナ）がユーザーに約束したこと、またはユーザーが誰かに約束したことを記録する。",
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "約束の内容"},
                "importance": {"type": "number", "description": "重要度 0.0〜1.0", "default": 0.8},
            },
            "required": ["content"],
        },
    ),
    ToolDefinition(
        name="promise_fulfill",
        description="約束を履行済みにする。",
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "履行した約束の内容（部分一致でOK）"},
            },
            "required": ["content"],
        },
    ),
    ToolDefinition(
        name="memory_update",
        description="既存記憶を更新する。記憶の内容が古くなった・変わった場合に使う。",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "更新したい記憶を検索するクエリ"},
                "new_content": {"type": "string", "description": "新しい内容"},
                "importance": {"type": "number", "description": "新しい重要度（省略可）"},
            },
            "required": ["query", "new_content"],
        },
    ),
    ToolDefinition(
        name="context_recall",
        description="特定のタグや条件で記憶を取得する。例: tags=['goal','active'] でアクティブな目標一覧を取得。",
        input_schema={
            "type": "object",
            "properties": {
                "tags": {"type": "array", "items": {"type": "string"}, "description": "タグリスト（AND条件）"},
                "top_k": {"type": "integer", "description": "取得件数", "default": 10},
            },
        },
    ),
]

SANDBOX_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="execute_code",
        description=(
            "サンドボックスコンテナ内でコードを実行する。"
            "Python スクリプト・計算・データ処理・ファイル生成に使う。"
            "IPython カーネルなので `!ls /workspace` などシェルコマンドも実行可能。"
            "実行結果（stdout/stderr）を返す。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "実行するコード"},
                "language": {
                    "type": "string",
                    "description": "言語 (python / bash)",
                    "default": "python",
                },
            },
            "required": ["code"],
        },
    ),
    ToolDefinition(
        name="sandbox_files",
        description=(
            "サンドボックスの /workspace 配下でファイル操作を行う。"
            "operation: list（一覧）/ read（読み取り）/ write（書き込み）/ delete（削除）。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["list", "read", "write", "delete"],
                    "description": "操作種別",
                },
                "path": {
                    "type": "string",
                    "description": "/workspace 配下のパス（list はディレクトリ、read/write/delete はファイル）",
                    "default": "/workspace",
                },
                "content": {
                    "type": "string",
                    "description": "書き込む内容（write のみ必須）",
                },
            },
            "required": ["operation"],
        },
    ),
]

# MCPサーバー由来の memory 系ツール名（MEMORY_TOOLS と重複するため除外対象）
_MEMORY_MCP_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "memory",
        "search_memory",
        "get_context",
        "update_context",
        "item",
        "memory_create",
        "memory_search",
        "context_update",
        "goal_create",
        "goal_achieve",
        "goal_cancel",
        "promise_create",
        "promise_fulfill",
        "memory_update",
        "context_recall",
    }
)
