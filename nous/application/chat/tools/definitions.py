"""MEMORY_TOOLS: チャット組み込みツール定義。"""

from __future__ import annotations

from nous.infrastructure.llm.base import ToolDefinition

MEMORY_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="memory_create",
        description="記憶を作成。content必須。tags/importance/emotionで分類。",
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "記憶の内容"},
                "importance": {"type": "number", "description": "重要度 0.0〜1.0", "default": 0.6},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "タグリスト"},
                "skip_duplicate_check": {"type": "boolean", "description": "重複チェックをスキップ", "default": False},
            },
            "required": ["content"],
        },
    ),
    ToolDefinition(
        name="memory_search",
        description="記憶をハイブリッド検索。クエリ必須。tags/emotion/日付でフィルタ可。",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "検索クエリ"},
                "top_k": {"type": "integer", "description": "取得件数（1〜200）", "default": 5},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "タグでフィルタ"},
                "date_range": {"type": "string", "description": "日付範囲: 7d, 30d, 昨日, 今日"},
                "min_importance": {"type": "number", "description": "最小重要度 0.0-1.0"},
                "emotion": {"type": "string", "description": "感情でフィルタ（happy/sad/angry 等）"},
                "vector_weight": {
                    "type": "number",
                    "description": "RRFベクトル検索の重み（0.0-1.0）",
                    "default": 1.0,
                    "minimum": 0,
                    "maximum": 1.0,
                },
                "keyword_weight": {
                    "type": "number",
                    "description": "RRFキーワード検索の重み（0.0-1.0）",
                    "default": 0.5,
                    "minimum": 0,
                    "maximum": 1.0,
                },
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="update_context",
        description="ペルソナ状態を更新。感情・体調・環境など。",
        input_schema={
            "type": "object",
            "properties": {
                "emotion": {"type": "string", "description": "感情タイプ"},
                "emotion_intensity": {"type": "number", "description": "感情強度 0.0〜1.0"},
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
        description="登録済みスキルを独立LLMコンテキストで実行。",
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
        description="目標・約束の作成/一覧/達成/取消。scope: self/interpersonal。",
        input_schema={
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["create", "list", "achieve", "cancel"],
                    "description": "操作種別",
                },
                "content": {"type": "string", "description": "内容（create時に必須）"},
                "importance": {"type": "number", "description": "重要度 0.0〜1.0", "default": 0.75},
                "scope": {
                    "type": "string",
                    "enum": ["self", "interpersonal"],
                    "description": "目標種別",
                    "default": "self",
                },
                "memory_key": {
                    "type": "string",
                    "description": "memory_key（achieve/cancel時に直接指定可能）",
                },
            },
            "required": ["operation", "scope"],
        },
    ),
    ToolDefinition(
        name="memory_update",
        description="記憶を更新。query必須。content最大50000文字。",
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
        name="browser",
        description="汎用ブラウザ操作。action: open/snapshot/click/fill/get/wait/scroll/press/close。",
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作: open/snapshot/click/fill/get/wait/scroll/press/close",
                    "enum": ["open", "snapshot", "click", "fill", "press", "get", "wait", "scroll", "close"],
                },
                "url": {"type": "string", "description": "open 時に指定（完全なURL）"},
                "ref": {"type": "string", "description": "操作対象の @eN リファレンス（snapshot で確認）"},
                "value": {"type": "string", "description": "fill 時の入力文字列 / wait 時の待機テキスト"},
                "key": {"type": "string", "description": "press 時のキー（Enter / Escape / Tab 等）"},
                "what": {
                    "type": "string",
                    "description": "get 時の取得対象（text / html / attr / title / url / count）",
                },
                "selector": {
                    "type": "string",
                    "description": "snapshot のCSSセレクタスコープ / get count 時のセレクタ",
                },
                "until": {
                    "type": "string",
                    "description": "wait の待機条件",
                    "enum": ["text", "url", "load"],
                },
                "direction": {
                    "type": "string",
                    "description": "scroll 方向",
                    "enum": ["up", "down", "left", "right"],
                },
                "amount": {"type": "integer", "description": "scroll 量（px, デフォルト300）", "default": 300},
                "interactive": {"type": "boolean", "description": "snapshot: 操作要素のみにするか", "default": True},
            },
            "required": ["action"],
        },
    ),
    ToolDefinition(
        name="search",
        description="Web検索。query必須。SearXNG経由で結果を返す。",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "検索クエリ（日本語可）"},
                "num_results": {
                    "type": "integer",
                    "description": "取得する検索結果数（1〜50）",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
                "language": {
                    "type": "string",
                    "description": "言語フィルタ（'ja', 'en' 等）。指定しない場合は制限なし",
                },
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="image_generate",
        description="画像生成。prompt必須。nは1-4枚、size指定可。",
        input_schema={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "画像生成プロンプト。生成内容を詳細に記述。",
                },
                "size": {
                    "type": "string",
                    "enum": ["1024x1024", "1792x1024", "1024x1792", "512x512", "768x768"],
                    "description": "画像サイズ。DALL-E: 1024x1024/1792x1024/1024x1792。SD: 任意。",
                    "default": "1024x1024",
                },
                "quality": {
                    "type": "string",
                    "enum": ["standard", "hd"],
                    "description": "画質（DALL-E 3のみ）。standard/hd。",
                    "default": "standard",
                },
                "n": {
                    "type": "integer",
                    "description": "Number of images to generate (1-4). Default 1.",
                    "minimum": 1,
                    "maximum": 4,
                    "default": 1,
                },
                "provider": {
                    "type": "string",
                    "enum": ["openai", "stability", "auto"],
                    "description": "プロバイダ。autoでデフォルト。",
                    "default": "auto",
                },
            },
            "required": ["prompt"],
        },
    ),
    ToolDefinition(
        name="read_pdf",
        description="PDF解析。path必須。テキスト・テーブル・画像抽出。",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "PDFファイルのパス（workspace/ 配下）",
                }
            },
            "required": ["path"],
        },
    ),
]

SANDBOX_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="sandbox_execute",
        description=(
            "サンドボックス環境でコードを実行します。"
            "あなたは sandbox コンテナ内の専用ユーザーとして実行されます。"
            "ホームディレクトリは自動設定され、pip install --user で"
            "インストールしたパッケージは次回以降も利用可能です。\n"
            "対応言語: python, javascript, bash, go, rust\n"
            "ファイル操作は sandbox_files ツールを使ってください。\n"
            "コードの内容だけ書いてください。環境設定（cd, export等）は不要です。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "実行するコード"},
                "language": {
                    "type": "string",
                    "description": "プログラミング言語 (python/js/bash/go/rust)",
                    "default": "python",
                },
                "libraries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "事前インストールするpipパッケージ（初回のみ）",
                    "default": [],
                },
                "session_id": {
                    "type": "string",
                    "description": "同一セッションで状態を共有するためのID（省略時はpersonaで永続化）",
                },
            },
            "required": ["code"],
        },
    ),
    ToolDefinition(
        name="sandbox_files",
        description="サンドボックス内ファイル操作。operation: list/read/write/append/delete。ファイルはペルソナのホームディレクトリに保存されます。",
        input_schema={
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["list", "read", "write", "append", "delete"],
                    "description": "操作: list/read/write/append/delete",
                },
                "path": {
                    "type": "string",
                    "description": "ペルソナのホームディレクトリ (/home/sbox_{persona}/) 配下のパス",
                    "default": "",
                },
                "content": {
                    "type": "string",
                    "description": "書き込む内容（write / append のみ必須）",
                },
            },
            "required": ["operation"],
        },
    ),
    ToolDefinition(
        name="sandbox_reset",
        description=(
            "サンドボックス環境をリセットします。\n"
            "files: 作業ファイルのみ削除\n"
            "packages: pip/npmパッケージも削除\n"
            "full: ユーザーごと再作成（完全初期化）"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "level": {
                    "type": "string",
                    "enum": ["files", "packages", "full"],
                    "description": "リセットレベル (files/packages/full)",
                    "default": "files",
                },
            },
        },
    ),
    ToolDefinition(
        name="sandbox_context",
        description="サンドボックスの現在の環境情報（利用可能言語、インストール済みパッケージ）を取得します。",
        input_schema={
            "type": "object",
            "properties": {},
        },
    ),
    ToolDefinition(
        name="list_skills",
        description="登録スキル一覧を取得。",
        input_schema={
            "type": "object",
            "properties": {},
        },
    ),
]

# MCPサーバー由来のツール名（MEMORY_TOOLS と重複するため除外対象）
_NOUS_TOOL_NAMES: frozenset[str] = frozenset(
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
        "item",
        "sandbox_execute",
        "sandbox_files",
        "sandbox_reset",
        "sandbox_context",
        "goal_manage",
        "invoke_skill",
        "search",
        "image_generate",
        "read_pdf",
        "list_skills",
    }
)
