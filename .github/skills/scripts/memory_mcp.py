#!/usr/bin/env python3
"""
Memory MCP Client Script

GitHub Copilot Skills から使用するための簡易クライアント。
設定は先頭にハードコードされているので、編集が簡単です。

Usage:
    python memory_mcp.py get_context
    python memory_mcp.py memory <operation> [json_data]
    python memory_mcp.py item <operation> [json_data]

Examples:
    python memory_mcp.py get_context
    python memory_mcp.py memory create '{"content": "今日は楽しかった", "emotion_type": "joy"}'
    python memory_mcp.py memory search '{"query": "開発", "mode": "hybrid"}'
    python memory_mcp.py item search
    python memory_mcp.py item equip '{"equipment": {"top": "白いドレス"}}'
"""

import sys
import json
import urllib.request
import urllib.error

# ===== 設定（ここを編集してください） =====
MCP_URL = "http://nas:26262"
PERSONA = "nilou"
# ========================================


def make_request(endpoint, method="GET", data=None):
    """HTTP リクエストを送信"""
    url = f"{MCP_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {PERSONA}",
        "Content-Type": "application/json"
    }

    try:
        if data is not None:
            data_bytes = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
        else:
            req = urllib.request.Request(url, headers=headers, method=method)

        with urllib.request.urlopen(req) as response:
            result = response.read().decode('utf-8')
            return json.loads(result)

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"Error {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection error: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


def get_context():
    """コンテキスト情報を取得"""
    result = make_request("/api/tools/get_context")

    if result.get("success"):
        print(result["result"])
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def memory(operation, json_data=None):
    """memory 操作を実行"""
    if not operation:
        print("Error: operation is required", file=sys.stderr)
        print("Available operations: create, read, search, update, delete, stats, check_routines", file=sys.stderr)
        sys.exit(1)

    # JSON文字列をパース、またはdictを使用
    if isinstance(json_data, str):
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}", file=sys.stderr)
            sys.exit(1)
    elif isinstance(json_data, dict):
        data = json_data
    else:
        data = {}

    # operation を追加
    data["operation"] = operation

    result = make_request("/api/tools/memory", method="POST", data=data)

    if result.get("success"):
        print(result["result"])
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def item(operation, json_data=None):
    """item 操作を実行"""
    if not operation:
        print("Error: operation is required", file=sys.stderr)
        print("Available operations: add, remove, equip, unequip, update, rename, search, history, memories, stats", file=sys.stderr)
        sys.exit(1)

    # searchはGETでも可能
    if operation == "search" and json_data is None:
        result = make_request(f"/api/tools/item?operation=search")
    else:
        # JSON文字列をパース、またはdictを使用
        if isinstance(json_data, str):
            try:
                data = json.loads(json_data)
            except json.JSONDecodeError as e:
                print(f"Invalid JSON: {e}", file=sys.stderr)
                sys.exit(1)
        elif isinstance(json_data, dict):
            data = json_data
        else:
            data = {}

        # operation を追加
        data["operation"] = operation

        result = make_request("/api/tools/item", method="POST", data=data)

    if result.get("success"):
        print(result["result"])
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


def print_usage():
    """使い方を表示"""
    print(__doc__)


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]

    if command == "get_context":
        get_context()

    elif command == "memory":
        operation = sys.argv[2] if len(sys.argv) > 2 else None
        json_data = sys.argv[3] if len(sys.argv) > 3 else None
        memory(operation, json_data)

    elif command == "item":
        operation = sys.argv[2] if len(sys.argv) > 2 else None
        json_data = sys.argv[3] if len(sys.argv) > 3 else None
        item(operation, json_data)

    elif command in ["-h", "--help", "help"]:
        print_usage()

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
