#!/usr/bin/env python3
"""
Qdrantスコア調査：距離 vs 類似度
"""

import json
import requests

BASE_URL = "http://192.168.50.178:26262"
MCP_URL = f"{BASE_URL}/mcp"
PERSONA = "nilou"

class MCPClient:
    def __init__(self):
        self.request_id = 0
        self.session_id = None
        self._initialized = False
    
    def _send_request(self, method: str, params: dict = None) -> dict:
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
        
        if not self.session_id and "mcp-session-id" in response.headers:
            self.session_id = response.headers["mcp-session-id"]
        
        lines = response.text.strip().split('\n')
        for line in lines:
            if line.startswith('data: '):
                return json.loads(line[6:])
        raise ValueError(f"No data in response: {response.text}")
    
    def initialize(self):
        if self._initialized:
            return
        result = self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "score-tester", "version": "1.0.0"}
        })
        if "result" not in result:
            raise Exception(f"Initialize failed: {result}")
        self._initialized = True
    
    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        if not self._initialized:
            self.initialize()
        result = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        if "error" in result:
            raise Exception(result["error"].get("message", "Unknown error"))
        return result.get("result", {})

def main():
    print("="*80)
    print("🔍 Qdrant Score Investigation")
    print("="*80)
    
    client = MCPClient()
    
    # 既知の記憶を検索してスコアを見る
    queries = [
        "Phase 31.2完了",  # さっき作った記憶
        "Phase 31.2のテスト",  # テスト用記憶
    ]
    
    for query in queries:
        print(f"\nQuery: '{query}'")
        print("-" * 80)
        
        try:
            result = client.call_tool("read_memory", {
                "query": query,
                "top_k": 3
            })
            
            content = result.get("content", [])
            for item in content:
                text = item.get("text", "")
                # スコア情報を探す
                if "score:" in text.lower() or "similarity" in text.lower():
                    print(text[:200])
                    print()
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
