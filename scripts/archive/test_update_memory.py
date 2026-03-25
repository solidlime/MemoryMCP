#!/usr/bin/env python3
"""
Phase 31.2: update_memory 動作確認テスト
自然言語クエリで既存記憶を更新できるかテスト
"""

import json

import requests

# MCP HTTP Server設定
BASE_URL = "http://192.168.50.178:26262"
MCP_URL = f"{BASE_URL}/mcp"
PERSONA = "nilou"


class MCPClient:
    """FastMCP HTTP クライアント"""

    def __init__(self):
        self.request_id = 0
        self.session_id = None
        self._initialized = False

    def _send_request(self, method: str, params: dict = None) -> dict:
        """JSON-RPC リクエスト送信"""
        self.request_id += 1

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {PERSONA}",
        }

        if self.session_id and method != "initialize":
            headers["mcp-session-id"] = self.session_id

        payload = {"jsonrpc": "2.0", "id": self.request_id, "method": method, "params": params or {}}

        response = requests.post(MCP_URL, json=payload, headers=headers)
        response.raise_for_status()

        # セッションID取得
        if not self.session_id and "mcp-session-id" in response.headers:
            self.session_id = response.headers["mcp-session-id"]

        # SSEレスポンスをパース
        lines = response.text.strip().split("\n")
        for line in lines:
            if line.startswith("data: "):
                return json.loads(line[6:])

        raise ValueError(f"No data in response: {response.text}")

    def initialize(self):
        """MCP セッション初期化"""
        if self._initialized:
            return

        result = self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "update-memory-tester", "version": "1.0.0"},
            },
        )

        if "result" not in result:
            raise Exception(f"Initialize failed: {result}")

        self._initialized = True

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """ツール呼び出し"""
        if not self._initialized:
            self.initialize()

        result = self._send_request("tools/call", {"name": tool_name, "arguments": arguments})

        if "error" in result:
            raise Exception(result["error"].get("message", "Unknown error"))

        return result.get("result", {})


def test_create_test_memory():
    """テスト用記憶を作成"""
    print("\n" + "=" * 80)
    print("📝 Step 1: テスト用記憶を作成")
    print("=" * 80)

    client = MCPClient()

    try:
        result = client.call_tool(
            "create_memory",
            {
                "content": "Phase 31.2のテスト用記憶です。これは更新テストのためのダミーデータ。",
                "importance": 0.5,
                "context_tags": ["testing"],
            },
        )

        content = result.get("content", [])
        if content:
            for item in content:
                text = item.get("text", "")
                print(text)
            print("\n✅ テスト用記憶を作成しました")
            return True
        else:
            print("⚠️  作成失敗")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_update_memory(query: str, new_content: str, description: str):
    """update_memory テスト"""
    print(f"\n{'=' * 80}")
    print(f"🧪 Test: {description}")
    print(f"Query: '{query}'")
    print(f"New Content: '{new_content}'")
    print("-" * 80)

    client = MCPClient()

    try:
        result = client.call_tool("update_memory", {"query": query, "content": new_content, "importance": 0.8})

        content = result.get("content", [])
        if content:
            for item in content:
                text = item.get("text", "")
                print(text)

            # 成功判定：「更新しました」または「Updated memory」が含まれるか
            full_text = " ".join([item.get("text", "") for item in content])
            if "更新" in full_text or "Updated" in full_text:
                print("\n✅ SUCCESS: update_memory が動作しました！")
                return True
            elif "作成" in full_text or "Created" in full_text:
                print("\n⚠️  WARNING: 既存記憶が見つからず新規作成されました")
                return False
            else:
                print("\n⚠️  結果が不明確です")
                return False
        else:
            print("⚠️  結果なし")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_read_to_verify(query: str):
    """更新後の記憶を確認"""
    print(f"\n{'=' * 80}")
    print("🔍 Verification: 更新された記憶を確認")
    print(f"Query: '{query}'")
    print("-" * 80)

    client = MCPClient()

    try:
        result = client.call_tool("read_memory", {"query": query, "top_k": 3})

        content = result.get("content", [])
        if content:
            for item in content:
                text = item.get("text", "")
                print(text)
            print("\n✅ 記憶を確認しました")
            return True
        else:
            print("⚠️  結果なし")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def main():
    print("=" * 80)
    print("🔧 Phase 31.2: update_memory 動作確認テスト")
    print("=" * 80)
    print(f"Target: {MCP_URL}")
    print(f"Persona: {PERSONA}")
    print()

    # Step 1: テスト用記憶を作成
    if not test_create_test_memory():
        print("\n❌ テスト用記憶の作成に失敗しました")
        return

    # Step 2: 自然言語クエリで更新
    tests = [
        (
            "Phase 31.2のテスト",
            "Phase 31.2のテスト用記憶を更新しました！update_memoryが正常動作しています✨",
            "完全一致クエリで更新",
        ),
        ("テスト用記憶", "再度更新テスト。自然言語クエリでの検索が動作している証拠💕", "部分一致クエリで更新"),
    ]

    results = []
    for query, new_content, desc in tests:
        success = test_update_memory(query, new_content, desc)
        results.append((desc, "✅ PASS" if success else "❌ FAIL"))

        if success:
            # 更新確認
            test_read_to_verify(query)

    # サマリー
    print(f"\n{'=' * 80}")
    print("📊 テスト結果サマリー")
    print("=" * 80)
    for desc, status in results:
        print(f"{status} {desc}")

    pass_count = sum(1 for _, status in results if "PASS" in status)
    total_count = len(results)
    print(f"\n合計: {pass_count}/{total_count} PASS ({pass_count / total_count * 100:.0f}%)")
    print("=" * 80)


if __name__ == "__main__":
    main()
