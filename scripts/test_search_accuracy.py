#!/usr/bin/env python3
"""
Phase 31.2: 検索精度診断ツール
現在の密ベクトル + Reranker実装での検索精度を測定
"""

import json
import requests
from typing import List, Dict

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
                "name": "search-accuracy-tester",
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

def call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """MCP HTTP経由でツール呼び出し（互換性用ラッパー）"""
    client = MCPClient()
    return client.call_tool(tool_name, arguments)

def search_memory(query: str, top_k: int = 5) -> Dict:
    """記憶検索を実行（search_memory使用）"""
    print(f"\n🔍 Query: '{query}'")
    print("-" * 80)
    
    # Phase 26.7: read_memory は次元エラーのため search_memory を使用
    result = call_mcp_tool("search_memory", {
        "query": query,
        "top_k": top_k,
        "fuzzy_match": True  # Fuzzy matchingを有効化
    })
    
    # 結果を表示
    content = result.get("content", [])
    if content:
        for item in content:
            text = item.get("text", "")
            print(text)
            
            # 結果件数を抽出
            if "**Result" in text:
                return {"found": True, "content": content}
    
    print("(結果なし)")
    return {"found": False, "content": content}

def main():
    print("=" * 80)
    print("🧪 検索精度診断テスト (Phase 31.2)")
    print("=" * 80)
    print(f"Persona: {PERSONA}")
    print(f"MCP URL: {MCP_URL}")
    print()
    
    # テストケース定義
    test_queries = [
        # 1. 固有名詞検索（Phase番号）
        {
            "category": "固有名詞（Phase番号）",
            "query": "Phase 28",
            "expected": "Phase 28の実装内容が上位に来るか"
        },
        
        # 2. 固有名詞検索（技術用語）
        {
            "category": "固有名詞（技術用語）",
            "query": "Qdrant",
            "expected": "Qdrant関連の記憶が取得できるか"
        },
        
        # 3. 固有名詞検索（人物名）
        {
            "category": "固有名詞（人物名）",
            "query": "らうらう",
            "expected": "ユーザー関連の記憶が取得できるか"
        },
        
        # 4. 意味的類似性（感情表現）
        {
            "category": "意味的類似性（感情）",
            "query": "嬉しい出来事",
            "expected": "joy感情タグの記憶が取得できるか"
        },
        
        # 5. 意味的類似性（成果・達成）
        {
            "category": "意味的類似性（成果）",
            "query": "プロジェクト完了",
            "expected": "技術的達成の記憶が取得できるか"
        },
        
        # 6. 複合検索（固有名詞 + 意味）
        {
            "category": "複合検索",
            "query": "Phase 30の成果",
            "expected": "Phase 30関連の完了記憶が取得できるか"
        },
        
        # 7. Obsidianリンク記法
        {
            "category": "Obsidianリンク",
            "query": "[[Authorization Bearer]]",
            "expected": "Phase 31のBearer認証実装が取得できるか"
        },
        
        # 8. 抽象的クエリ
        {
            "category": "抽象的クエリ",
            "query": "最近の開発作業",
            "expected": "直近のコーディング記憶が取得できるか"
        },
        
        # 9. 類似語検索
        {
            "category": "類似語検索",
            "query": "非同期処理",
            "expected": "async関連の実装記憶が取得できるか"
        },
        
        # 10. ネガティブケース（存在しない情報）
        {
            "category": "ネガティブケース",
            "query": "機械学習モデルの学習",
            "expected": "関連性の低い結果になるか（ノイズ検出）"
        }
    ]
    
    # 各テストケース実行
    results = []
    for i, test in enumerate(test_queries, 1):
        print(f"\n{'=' * 80}")
        print(f"📋 Test {i}/{len(test_queries)}: {test['category']}")
        print(f"期待値: {test['expected']}")
        
        try:
            result = search_memory(test["query"], top_k=5)
            results.append({
                "test_id": i,
                "category": test["category"],
                "query": test["query"],
                "status": "✅ SUCCESS",
                "result": result
            })
        except Exception as e:
            print(f"❌ ERROR: {e}")
            results.append({
                "test_id": i,
                "category": test["category"],
                "query": test["query"],
                "status": "❌ FAILED",
                "error": str(e)
            })
    
    # サマリー表示
    print(f"\n{'=' * 80}")
    print("📊 診断サマリー")
    print(f"{'=' * 80}")
    
    success_count = sum(1 for r in results if r["status"] == "✅ SUCCESS")
    total_count = len(results)
    
    print(f"成功: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)")
    print()
    
    print("【カテゴリ別結果】")
    for r in results:
        print(f"{r['status']} {r['category']}: {r['query']}")
    
    print(f"\n{'=' * 80}")
    print("💭 次のステップ:")
    print("1. 結果を確認して、どのカテゴリが弱いか特定")
    print("2. ハイブリッド検索が必要かどうか判断")
    print("3. 必要なら疎ベクトル実装へ（Phase 32）")
    print(f"{'=' * 80}")

if __name__ == "__main__":
    main()
