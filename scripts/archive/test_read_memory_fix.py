#!/usr/bin/env python3
"""
Phase 31.2: read_memory 次元エラー修正テスト
意味的検索が正しく動作するかテスト
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
            "Authorization": f"Bearer {PERSONA}"
        }
        
        if self.session_id and method != "initialize":
            headers["mcp-session-id"] = self.session_id
        
        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        
        response = requests.post(MCP_URL, json=payload, headers=headers)
        response.raise_for_status()
        
        # セッションID取得
        if not self.session_id and "mcp-session-id" in response.headers:
            self.session_id = response.headers["mcp-session-id"]
        
        # SSEレスポンスをパース
        lines = response.text.strip().split('\n')
        for line in lines:
            if line.startswith('data: '):
                return json.loads(line[6:])
        
        raise ValueError(f"No data in response: {response.text}")
    
    def initialize(self):
        """MCP セッション初期化"""
        if self._initialized:
            return
        
        result = self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "read-memory-tester",
                "version": "1.0.0"
            }
        })
        
        if "result" not in result:
            raise Exception(f"Initialize failed: {result}")
        
        self._initialized = True
    
    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """ツール呼び出し"""
        if not self._initialized:
            self.initialize()
        
        result = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        if "error" in result:
            raise Exception(result["error"].get("message", "Unknown error"))
        
        return result.get("result", {})

def test_read_memory(query: str, description: str):
    """read_memory テスト"""
    print(f"\n{'='*80}")
    print(f"🧪 Test: {description}")
    print(f"Query: '{query}'")
    print("-" * 80)
    
    client = MCPClient()
    
    try:
        result = client.call_tool("read_memory", {
            "query": query,
            "top_k": 5
        })
        
        content = result.get("content", [])
        if content:
            for item in content:
                text = item.get("text", "")
                print(text)
            print("\n✅ SUCCESS: read_memory が動作しました！")
            return True
        else:
            print("⚠️  結果なし")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    print("=" * 80)
    print("🔧 Phase 31.2: read_memory 次元エラー修正テスト")
    print("=" * 80)
    print(f"Target: {MCP_URL}")
    print(f"Persona: {PERSONA}")
    print()
    
    # テストケース
    tests = [
        ("嬉しい出来事", "意味的類似性（感情）- joyタグの記憶を取得"),
        ("非同期処理", "類義語検索 - async関連の記憶を取得"),
        ("最近の開発作業", "抽象的クエリ - 直近のコーディング記憶を取得"),
        ("Phase 28", "固有名詞 - Phase 28関連の記憶を取得"),
    ]
    
    results = []
    for query, desc in tests:
        success = test_read_memory(query, desc)
        results.append((desc, "✅ PASS" if success else "❌ FAIL"))
    
    # サマリー
    print(f"\n{'='*80}")
    print("📊 テスト結果サマリー")
    print("=" * 80)
    for desc, status in results:
        print(f"{status} {desc}")
    
    pass_count = sum(1 for _, status in results if "PASS" in status)
    total_count = len(results)
    print(f"\n合計: {pass_count}/{total_count} PASS ({pass_count/total_count*100:.0f}%)")
    print("=" * 80)

if __name__ == "__main__":
    main()
