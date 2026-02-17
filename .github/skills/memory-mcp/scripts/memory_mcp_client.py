#!/usr/bin/env python3
"""
Memory MCP Client - Unified CLI for all MCP tools

このスクリプトはMemory MCPサーバーの全ツールに対応したCLIクライアントです。

ツール:
  1. get_context  - ペルソナの状態、時刻、メモリ統計を取得
  2. memory       - メモリ操作（create, update, delete, search, stats, check_routines, anniversary）
  3. item         - アイテム操作（add, remove, equip, unequip, update, search, history, memories, stats）

使用方法:
  python memory_mcp_client.py <tool> [options]

例:
  # コンテキスト取得
  python memory_mcp_client.py get_context

  # メモリ作成
  python memory_mcp_client.py memory create --content "好きな食べ物はイチゴ" --importance 0.8

  # メモリ検索
  python memory_mcp_client.py memory search --query "イチゴ" --mode semantic

  # アイテム追加
  python memory_mcp_client.py item add --name "赤いドレス" --category clothing

  # アイテム装備（スロット指定）
  python memory_mcp_client.py item equip --slot top --name "赤いドレス"

  # 複数アイテム同時装備
  python memory_mcp_client.py item equip --equipment '{"top": "赤いドレス", "foot": "サンダル"}'

  # アイテム装備解除
  python memory_mcp_client.py item unequip --slot top

共通オプション:
  --persona     ペルソナ名（デフォルト: config.jsonから読み込み）
  --url         MCPサーバーURL（デフォルト: config.jsonから読み込み）
  --format      出力形式（json|text）（デフォルト: text）
"""

import argparse
import json
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional
import requests

# 環境変数でPythonのI/OエンコーディングをUTF-8に強制
os.environ['PYTHONIOENCODING'] = 'utf-8'

# コンソール出力のエンコーディングをUTF-8に設定（Windows対応）
if sys.platform == "win32":
    import io
    import ctypes

    # Windows APIでコンソールをUTF-8モードに設定
    try:
        # コンソールの出力コードページをUTF-8 (65001) に設定
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception:
        pass  # 失敗しても続行（管理者権限不要の環境用）

    # stdout/stderrをUTF-8でラップ
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
else:
    # Linux/Macでもエンコーディングを明示
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)


def load_config() -> Dict[str, Any]:
    """Load configuration file"""
    config_path = Path(__file__).parent.parent / "references" / "config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def call_mcp_tool(
    tool_name: str,
    params: Dict[str, Any],
    persona: str,
    server_url: str
) -> Dict[str, Any]:
    """
    MCPツールを呼び出す

    Args:
        tool_name: ツール名（get_context, memory, item）
        params: ツールパラメータ
        persona: ペルソナ名
        server_url: MCPサーバーURL

    Returns:
        dict: レスポンスデータ
    """
    url = f"{server_url}/mcp/v1/tools/{tool_name}"
    headers = {
        "Authorization": f"Bearer {persona}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json=params, timeout=30)
        response.raise_for_status()
        # 明示的にUTF-8でデコードしてからJSONパース
        text = response.content.decode('utf-8')
        return json.loads(text)
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def format_output(data: Dict[str, Any], output_format: str = "text") -> str:
    """
    レスポンスデータを整形

    Args:
        data: レスポンスデータ
        output_format: 出力形式（json or text）

    Returns:
        str: 整形された文字列
    """
    if output_format == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)

    if "error" in data:
        return f"❌ エラー: {data['error']}"

    # テキスト形式で整形
    output = []
    output.append("=" * 60)

    if "content" in data:
        content = data["content"]
        if isinstance(content, list) and len(content) > 0:
            text_content = content[0].get("text", "")
            output.append(text_content)
        else:
            output.append(str(content))
    else:
        output.append(json.dumps(data, ensure_ascii=False, indent=2))

    output.append("=" * 60)
    return "\n".join(output)


def cmd_get_context(args: argparse.Namespace, config: Dict[str, Any]) -> int:
    """Execute get_context command"""
    persona = args.persona or config.get("persona", {}).get("default", "default")
    server_url = args.url or config.get("mcp_server", {}).get("url", "http://localhost:26262")

    result = call_mcp_tool("get_context", {}, persona, server_url)
    print(format_output(result, args.format))

    return 0 if "error" not in result else 1


def cmd_memory(args: argparse.Namespace, config: Dict[str, Any]) -> int:
    """Execute memory command"""
    persona = args.persona or config.get("persona", {}).get("default", "default")
    server_url = args.url or config.get("mcp_server", {}).get("url", "http://localhost:26262")

    # パラメータを構築
    params = {"operation": args.operation}

    # 操作別のパラメータ
    if args.operation == "create":
        if not args.content:
            print("❌ エラー: --content は必須です", file=sys.stderr)
            return 1
        params["content"] = args.content
        if args.importance is not None:
            params["importance"] = args.importance
        if args.emotion_type:
            params["emotion_type"] = args.emotion_type
        if args.emotion_intensity is not None:
            params["emotion_intensity"] = args.emotion_intensity
        if args.tags:
            params["context_tags"] = args.tags.split(",")
        if args.context_tags:
            params["context_tags"] = args.context_tags.split(",")
        if args.action_tag:
            params["action_tag"] = args.action_tag

    elif args.operation == "update":
        if not args.key:
            print("❌ エラー: --key は必須です", file=sys.stderr)
            return 1
        params["key"] = args.key
        if args.content:
            params["content"] = args.content
        if args.importance is not None:
            params["importance"] = args.importance
        if args.emotion_type:
            params["emotion_type"] = args.emotion_type
        if args.tags:
            params["context_tags"] = args.tags.split(",")

    elif args.operation == "delete":
        if not args.key:
            print("❌ エラー: --key は必須です", file=sys.stderr)
            return 1
        params["key"] = args.key

    elif args.operation == "search":
        if not args.query:
            print("❌ エラー: --query は必須です", file=sys.stderr)
            return 1
        params["query"] = args.query
        if args.mode:
            params["mode"] = args.mode
        if args.top_k:
            params["top_k"] = args.top_k
        if args.date_range:
            params["date_range"] = args.date_range
        if args.tags:
            params["search_tags"] = args.tags.split(",")

    elif args.operation == "anniversary":
        if args.content:
            params["content"] = args.content
        if args.delete_key:
            params["delete_key"] = args.delete_key

    # ツール呼び出し
    result = call_mcp_tool("memory", params, persona, server_url)
    print(format_output(result, args.format))

    return 0 if "error" not in result else 1


def cmd_item(args: argparse.Namespace, config: Dict[str, Any]) -> int:
    """Execute item command"""
    persona = args.persona or config.get("persona", {}).get("default", "default")
    server_url = args.url or config.get("mcp_server", {}).get("url", "http://localhost:26262")

    # パラメータを構築
    params = {"operation": args.operation}

    # 操作別のパラメータ
    if args.operation == "add":
        if not args.name:
            print("❌ エラー: --name は必須です", file=sys.stderr)
            return 1
        params["name"] = args.name
        if args.category:
            params["category"] = args.category
        if args.description:
            params["description"] = args.description
        if args.tags:
            params["tags"] = args.tags.split(",")

    elif args.operation == "remove":
        if not args.name:
            print("❌ エラー: --name は必須です", file=sys.stderr)
            return 1
        params["name"] = args.name

    elif args.operation == "equip":
        # equipmentパラメータを構築（スロット→アイテム名の辞書）
        if args.equipment:
            # JSON形式の装備辞書が指定された場合
            try:
                params["equipment"] = json.loads(args.equipment)
            except json.JSONDecodeError:
                print("❌ エラー: --equipment は有効なJSON形式である必要があります", file=sys.stderr)
                print('例: --equipment \'{"top": "白いドレス", "foot": "サンダル"}\'', file=sys.stderr)
                return 1
        elif args.slot and args.name:
            # スロットとアイテム名の組み合わせが指定された場合
            params["equipment"] = {args.slot: args.name}
        else:
            print("❌ エラー: --slot と --name、または --equipment が必要です", file=sys.stderr)
            print("例1: --slot top --name '白いドレス'", file=sys.stderr)
            print('例2: --equipment \'{"top": "白いドレス", "foot": "サンダル"}\'', file=sys.stderr)
            return 1

    elif args.operation == "unequip":
        # slotsパラメータを構築（スロット名のリスト）
        if args.slots:
            # カンマ区切りのスロット名リスト
            params["slots"] = args.slots.split(",")
        elif args.slot:
            # 単一スロット名
            params["slots"] = args.slot
        else:
            print("❌ エラー: --slot または --slots が必要です", file=sys.stderr)
            print("例1: --slot top", file=sys.stderr)
            print("例2: --slots top,foot,hand", file=sys.stderr)
            return 1

    elif args.operation == "update":
        if not args.name:
            print("❌ エラー: --name は必須です", file=sys.stderr)
            return 1
        params["name"] = args.name
        if args.description:
            params["description"] = args.description
        if args.tags:
            params["tags"] = args.tags.split(",")

    elif args.operation == "search":
        if args.query:
            params["query"] = args.query
        if args.category:
            params["category"] = args.category
        if args.equipped is not None:
            params["equipped"] = args.equipped

    elif args.operation == "memories":
        if not args.name:
            print("❌ エラー: --name は必須です", file=sys.stderr)
            return 1
        params["name"] = args.name

    # ツール呼び出し
    result = call_mcp_tool("item", params, persona, server_url)
    print(format_output(result, args.format))

    return 0 if "error" not in result else 1


def main():
    """Main processing"""
    config = load_config()

    parser = argparse.ArgumentParser(
        description="Memory MCP Client - 全MCPツールのCLIインターフェース",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # 共通オプション
    parser.add_argument(
        "--persona",
        help=f"ペルソナ名（デフォルト: {config.get('persona', {}).get('default', 'default')}）"
    )
    parser.add_argument(
        "--url",
        help=f"MCPサーバーURL（デフォルト: {config.get('mcp_server', {}).get('url', 'http://localhost:26262')}）"
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="出力形式（デフォルト: text）"
    )

    # サブコマンド
    subparsers = parser.add_subparsers(dest="tool", help="MCPツール", required=True)

    # ===== get_context =====
    parser_context = subparsers.add_parser(
        "get_context",
        help="ペルソナの状態、時刻、メモリ統計を取得"
    )

    # ===== memory =====
    parser_memory = subparsers.add_parser(
        "memory",
        help="メモリ操作"
    )
    parser_memory.add_argument(
        "operation",
        choices=["create", "update", "delete", "search", "stats", "check_routines", "anniversary"],
        help="操作タイプ"
    )
    parser_memory.add_argument("--key", help="メモリキー（update/delete用）")
    parser_memory.add_argument("--content", help="メモリ内容（create/update用）")
    parser_memory.add_argument("--importance", type=float, help="重要度（0.0-1.0）")
    parser_memory.add_argument("--emotion_type", help="感情タイプ")
    parser_memory.add_argument("--emotion_intensity", type=float, help="感情強度（0.0-1.0）")
    parser_memory.add_argument("--tags", help="タグ（カンマ区切り）")
    parser_memory.add_argument("--context_tags", help="コンテキストタグ（カンマ区切り）")
    parser_memory.add_argument("--action_tag", help="行動タグ")
    parser_memory.add_argument("--query", help="検索クエリ（search用）")
    parser_memory.add_argument("--mode", choices=["semantic", "keyword", "hybrid", "related", "smart"], help="検索モード")
    parser_memory.add_argument("--top_k", type=int, help="検索結果数")
    parser_memory.add_argument("--date_range", help="日付範囲（例: '昨日', '先週', '2025-01-01,2025-01-31'）")
    parser_memory.add_argument("--delete_key", help="削除する記念日キー（anniversary用）")

    # ===== item =====
    parser_item = subparsers.add_parser(
        "item",
        help="アイテム操作"
    )
    parser_item.add_argument(
        "operation",
        choices=["add", "remove", "equip", "unequip", "update", "search", "history", "memories", "stats"],
        help="操作タイプ"
    )
    parser_item.add_argument("--name", help="アイテム名")
    parser_item.add_argument("--category", help="カテゴリ（clothing/accessory/item）")
    parser_item.add_argument("--description", help="説明")
    parser_item.add_argument("--tags", help="タグ（カンマ区切り）")
    parser_item.add_argument("--query", help="検索クエリ")
    parser_item.add_argument("--equipped", type=bool, help="装備中のみ検索（True/False）")
    # equip operation用
    parser_item.add_argument("--slot", help="装備スロット（equip/unequip用、例: top, foot, hand）")
    parser_item.add_argument("--equipment", help="装備辞書JSON（equip用、例: '{\"top\": \"白いドレス\", \"foot\": \"サンダル\"}'）")
    # unequip operation用
    parser_item.add_argument("--slots", help="装備解除するスロット（カンマ区切り、unequip用、例: top,foot）")

    args = parser.parse_args()

    # コマンド実行
    if args.tool == "get_context":
        return cmd_get_context(args, config)
    elif args.tool == "memory":
        return cmd_memory(args, config)
    elif args.tool == "item":
        return cmd_item(args, config)
    else:
        print(f"❌ 不明なツール: {args.tool}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
