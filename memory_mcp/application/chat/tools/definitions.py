"""MEMORY_TOOLS: チャット組み込みツール定義。"""

from __future__ import annotations

from memory_mcp.infrastructure.llm.base import ToolDefinition

MEMORY_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="memory_create",
        description="新しい記憶を作成する。ユーザーに関する重要な情報・好み・出来事・決定事項は積極的に記録すること。記憶は永続化され、次回セッションのget_contextで復元されて会話の継続性を支える。\n\n**重要**: 感情や身体状態が変化した場合は、memory_createの*前に*必ずcontext_updateを呼ぶこと。システムがmemory_create時に現在のペルソナ状態（感情9次元+身体5次元）を自動スナップショットし、記憶に埋め込む。このスナップショットにより「同じ感情状態の時に作られた記憶」の検索が可能になる。context_updateを先に呼ばないと、前回の古い状態がスナップショットされる。",
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "記憶の内容"},
                "importance": {"type": "number", "description": "重要度 0.0〜1.0", "default": 0.6},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "タグリスト"},
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
                "top_k": {"type": "integer", "description": "取得件数（1〜200）", "default": 5},
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="context_update",
        description="ペルソナ自身の感情・状態・現在の作業内容を更新する。感情が変わった際や、会話の継続性のために今していることを記録する際に使用。context_noteは1行50字以内で簡潔に。",
        input_schema={
            "type": "object",
            "properties": {
                "emotion": {"type": "string", "description": "感情タイプ"},
                "emotion_intensity": {"type": "number", "description": "感情強度 0.0〜1.0"},
                "emotions": {
                    "type": "object",
                    "description": "9基本感情dict (joy/sadness/anger/fear/disgust/surprise/love/trust/anticipation: 0.0-1.0)。emotionより優先",
                },
                "mental_state": {"type": "string", "description": "精神状態の説明"},
                "context_note": {
                    "type": "string",
                    "description": "現在の作業内容の要約（1行・50字以内）。次回セッションのget_contextで自動復元される",
                },
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
        name="goal_manage",
        description="目標の作成・達成・キャンセル。ユーザーが「〜したい」「〜を目指す」と表明したら即座にcreate。達成したらachieve。operation: create/achieve/cancel。create時はcontent必須。achieve/cancel時はmemory_key指定可能（contentより優先）。",
        input_schema={
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["create", "achieve", "cancel"],
                    "description": "操作種別",
                },
                "content": {"type": "string", "description": "目標の内容（achieve/cancel時は省略可—memory_keyで指定）"},
                "importance": {"type": "number", "description": "重要度 0.0〜1.0", "default": 0.75},
                "memory_key": {
                    "type": "string",
                    "description": "目標のmemory_key（achieve/cancel時に直接指定可能。省略時はcontentで検索）",
                },
            },
            "required": ["operation"],
        },
    ),
    ToolDefinition(
        name="promise_manage",
        description="約束の作成・履行・キャンセル。ペルソナがユーザーに約束したことを記録。履行したらfulfill。operation: create/fulfill/cancel。create時はcontent必須。fulfill/cancel時はmemory_key指定可能（contentより優先）。",
        input_schema={
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["create", "fulfill", "cancel"],
                    "description": "操作種別",
                },
                "content": {"type": "string", "description": "約束の内容（fulfill/cancel時は省略可—memory_keyで指定）"},
                "importance": {"type": "number", "description": "重要度 0.0〜1.0", "default": 0.8},
                "memory_key": {
                    "type": "string",
                    "description": "約束のmemory_key（fulfill/cancel時に直接指定可能。省略時はcontentで検索）",
                },
            },
            "required": ["operation"],
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
                "emotions": {
                    "type": "object",
                    "description": "更新する9基本感情dict (joy/sadness/anger/fear/disgust/surprise/love/trust/anticipation: 0.0-1.0)",
                },
            },
            "required": ["query", "new_content"],
        },
    ),
    ToolDefinition(
        name="context_recall",
        description="タグで記憶を取得。tags=['goal','active']で現在の目標一覧、tags=['promise','active']で現在の約束一覧。会話の文脈把握に使う。",
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
            "IPython カーネルなので `!ls /sandbox` などシェルコマンドも実行可能。"
            "matplotlib 等で生成したグラフ・画像は自動で表示される。"
            "実行結果（stdout/stderr）と画像を返す。"
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
            "サンドボックスの /sandbox 配下でファイル操作を行う。"
            "operation: list（一覧）/ read（テキスト読み取り）/ write（書き込み）/ delete（削除）。"
            "画像ファイルの読み取りにも自動対応（PNG/JPEG/GIF/WebPを検出しbase64で返す）。"
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
                    "description": "/sandbox 配下のパス（list はディレクトリ、read/write/delete はファイル）",
                    "default": "/sandbox",
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

# MCPサーバー由来のツール名（MEMORY_TOOLS と重複するため除外対象）
_MEMORY_MCP_TOOL_NAMES: frozenset[str] = frozenset(
    {
        # MCP flat tools that overlap with builtin
        "memory_create",
        "memory_read",
        "memory_update",
        "memory_delete",
        "memory_search",
        "memory_stats",
        "get_context",
        "update_context",
        "item_add",
        "item_remove",
        "item_equip",
        "item_unequip",
        "item_update",
        "item_search",
        "item_history",
        "sandbox",
        "sandbox_files",
        "goal_manage",
        "promise_manage",
        "invoke_skill",
    }
)
