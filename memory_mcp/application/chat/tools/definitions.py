"""MEMORY_TOOLS: チャット組み込みツール定義。"""

from __future__ import annotations

from memory_mcp.infrastructure.llm.base import ToolDefinition

MEMORY_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="memory_create",
        description="新しい記憶を作成する。ユーザーの重要な事実・好み・出来事を記録したい時に使う。importance は 0.0〜1.0（高いほど重要）。tags で分類。重複チェックをスキップする場合は skip_duplicate_check: true を指定。",
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
        description="記憶をハイブリッド検索（意味＋キーワード）する。思い出したいことや関連情報を探す時に使う。top_k で取得件数指定。",
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
        description="ペルソナの感情・状態を更新する。気分や体調が変わった時に使う。emotion には happy/sad/angry/neutral 等の感情を指定。",
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
        description="登録済みのスキルを独立したLLMコンテキストで実行する。複雑な専門タスクをメインの会話から分離したい時に使う。",
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
        description="目標（自分が達成したいこと）の作成・達成・キャンセル。operation は create（新しい目標）/ achieve（達成）/ cancel（キャンセル）。",
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
        description="約束（ユーザーや他人との約束事）の作成・履行・キャンセル。goal_manage と違い、対人関係の約束に使う。operation は create/fulfill/cancel。",
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
        description="既存の記憶を検索して内容を更新する。記憶の内容が古くなった・変わった場合に使う。query で検索、new_content で置き換え。",
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
        description="agent-browser CLI 経由でWebブラウザを操作。基本的な流れ: open → snapshot -i → click @eN / fill @eN → snapshot -i の繰り返し。action で操作種別を指定。",
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": (
                        "操作種別。open(URLを開く) / snapshot(ページ構造取得) / "
                        "click(要素クリック) / fill(テキスト入力) / press(キー押下) / "
                        "get(情報取得) / wait(待機) / scroll(スクロール) / close(終了)"
                    ),
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
        description="SearXNGメタサーチエンジンでWeb検索する。リアルタイム情報や最新ドキュメントを調べたい時に使う。Google/Bing/DuckDuckGo等の結果を集約。",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "検索クエリ（日本語可）"},
                "num_results": {"type": "integer", "description": "取得する検索結果数（1〜50）", "default": 10, "minimum": 1, "maximum": 50},
                "language": {"type": "string", "description": "言語フィルタ（'ja', 'en' 等）。指定しない場合は制限なし"},
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="image_generate",
        description="画像生成。DALL-E 3 または Stable Diffusion で画像を作成する。prompt で生成内容を指定。size/quality/provider で詳細調整可能。",
        input_schema={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Detailed image generation prompt. Describe what you want to create in detail. For Japanese prompts, describe visually what should appear.",
                },
                "size": {
                    "type": "string",
                    "enum": ["1024x1024", "1792x1024", "1024x1792", "512x512", "768x768"],
                    "description": "Image size. Default 1024x1024. For DALL-E: 1024x1024, 1792x1024 (landscape), 1024x1792 (portrait). For SD: any size supported by the server.",
                    "default": "1024x1024",
                },
                "quality": {
                    "type": "string",
                    "enum": ["standard", "hd"],
                    "description": "Image quality. Only used with DALL-E 3. 'hd' for higher detail.",
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
                    "description": "Image generation provider. 'auto' uses the default configured provider.",
                    "default": "auto",
                },
            },
            "required": ["prompt"],
        },
    ),
    ToolDefinition(
        name="read_pdf",
        description="PDFファイルを解析してテキスト・テーブル・画像を抽出する。path にPDFファイルの絶対パスを指定。50MB以内のファイル対応。",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the PDF file in the workspace (e.g. 'workspace/projects/document.pdf')",
                }
            },
            "required": ["path"],
        },
    ),
]

SANDBOX_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="execute_code",
        description="サンドボックスコンテナ内でコードを実行。Python / Bash 対応。session_id を指定すると同一コンテナで変数や状態を共有できる。",
        input_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "実行するコード"},
                "language": {
                    "type": "string",
                    "description": "言語 (python / bash)",
                    "default": "python",
                },
                "session_id": {
                    "type": "string",
                    "description": "同一セッションで状態を共有するためのID（省略時は毎回新規セッション）",
                },
            },
            "required": ["code"],
        },
    ),
    ToolDefinition(
        name="sandbox_files",
        description="サンドボックスの /sandbox 配下でファイル操作。operation で list/read/write/append/delete を指定。write/append 時は content 必須。画像ファイルも自動検出。",
        input_schema={
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["list", "read", "write", "append", "delete"],
                    "description": "操作種別",
                },
                "path": {
                    "type": "string",
                    "description": "/sandbox 配下のパス（list はディレクトリ、read/write/delete はファイル）",
                    "default": "/sandbox",
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
        name="list_skills",
        description="登録済みスキルの一覧を取得。invoke_skill を呼ぶ前に、利用可能なスキル名と説明を確認するために使う。",
        input_schema={
            "type": "object",
            "properties": {},
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
        "web_search",
    }
)
