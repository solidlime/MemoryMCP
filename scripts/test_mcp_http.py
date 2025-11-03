#!/usr/bin/env python3
"""
test_mcp_http.py - HTTP MCP Endpoint Testing Script

Tests all MCP tools via HTTP endpoint to ensure proper functionality.
This script assumes MCP server is already running on localhost:26262.

Usage:
    python test_mcp_http.py
    
    # Or with custom URL
    python test_mcp_http.py --url http://localhost:26262
"""

import json
import requests
import sys
import time
from typing import Dict, Any, Optional

# Configuration
DEFAULT_MCP_URL = "http://localhost:26262"
PERSONA = "default"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "Authorization": f"Bearer {PERSONA}"  # Use Bearer token for persona (Open WebUI compatible)
}

# Test data
TEST_MEMORY_CONTENT = "Test memory: らうらうとニィロウのデバッグテスト"
TEST_SEARCH_QUERY = "デバッグ"


class MCPTester:
    """HTTP MCP endpoint tester"""
    
    def __init__(self, base_url: str = DEFAULT_MCP_URL):
        self.base_url = base_url
        self.mcp_url = f"{base_url}/mcp"
        self.session = requests.Session()  # Use persistent session
        self.session.headers.update(HEADERS)
        self.request_id = 0
        self.session_id = None  # Session ID from initialize
        
    def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send JSON-RPC request to MCP endpoint"""
        self.request_id += 1
        
        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        
        # Add session ID to headers if available (after initialize)
        headers = HEADERS.copy()
        if self.session_id and method != "initialize":
            headers["mcp-session-id"] = self.session_id
        
        try:
            response = requests.post(self.mcp_url, json=payload, headers=headers)
            response.raise_for_status()
            
            # Extract session ID from response headers (if present and not already set)
            if not self.session_id and "mcp-session-id" in response.headers:
                self.session_id = response.headers["mcp-session-id"]
                
        except requests.exceptions.HTTPError as e:
            # Print detailed error info
            print(f"\n  ❌ HTTP Error: {e}")
            print(f"  Request: {method}")
            print(f"  Response status: {response.status_code}")
            print(f"  Response body: {response.text[:500]}")
            raise
        
        # Parse SSE response
        lines = response.text.strip().split('\n')
        for line in lines:
            if line.startswith('data: '):
                data = json.loads(line[6:])
                return data
        
        raise ValueError(f"No data in response: {response.text}")
    
    def test_health(self) -> bool:
        """Test health endpoint"""
        print("🏥 Testing health endpoint...")
        try:
            response = requests.get(f"{self.base_url}/health")
            response.raise_for_status()
            data = response.json()
            print(f"  ✅ Health: {data.get('status')}, Persona: {data.get('persona')}")
            return True
        except Exception as e:
            print(f"  ❌ Health check failed: {e}")
            return False
    
    def test_initialize(self) -> bool:
        """Test MCP initialize"""
        print("\n🔌 Testing MCP initialize...")
        try:
            result = self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            })
            
            if "result" in result:
                server_info = result["result"].get("serverInfo", {})
                
                # Session ID is extracted automatically in _send_request from headers
                if self.session_id:
                    print(f"  ✅ Session ID: {self.session_id[:16]}...")
                
                print(f"  ✅ Initialize: {server_info.get('name')} v{server_info.get('version')}")
                return True
            else:
                print(f"  ❌ Initialize failed: {result}")
                return False
                
        except Exception as e:
            print(f"  ❌ Initialize error: {e}")
            return False
    
    def test_list_tools(self) -> bool:
        """Test tools/list"""
        print("\n🔧 Testing tools/list...")
        try:
            result = self._send_request("tools/list")
            
            if "result" in result:
                tools = result["result"].get("tools", [])
                print(f"  ✅ Found {len(tools)} tools:")
                for tool in tools[:5]:  # Show first 5
                    print(f"     - {tool.get('name')}")
                if len(tools) > 5:
                    print(f"     ... and {len(tools) - 5} more")
                return True
            else:
                print(f"  ❌ List tools failed: {result}")
                return False
                
        except Exception as e:
            print(f"  ❌ List tools error: {e}")
            return False
    
    def test_get_session_context(self) -> bool:
        """Test get_session_context tool"""
        print("\n📋 Testing get_session_context...")
        try:
            result = self._send_request("tools/call", {
                "name": "get_session_context",
                "arguments": {}
            })
            
            if "result" in result:
                content = result["result"].get("content", [])
                if content and len(content) > 0:
                    text = content[0].get("text", "")
                    lines = text.split('\n')[:5]  # First 5 lines
                    print("  ✅ Session context retrieved:")
                    for line in lines:
                        print(f"     {line}")
                    return True
            
            print(f"  ❌ Get session context failed: {result}")
            return False
            
        except Exception as e:
            print(f"  ❌ Get session context error: {e}")
            return False
    
    def test_create_memory(self) -> Optional[str]:
        """Test create_memory tool"""
        print("\n💾 Testing create_memory...")
        try:
            timestamp = int(time.time())
            content = f"{TEST_MEMORY_CONTENT} (timestamp: {timestamp})"
            
            result = self._send_request("tools/call", {
                "name": "create_memory",
                "arguments": {
                    "content": content,  # Fixed: was "content_or_query"
                    "importance": 0.8,
                    "context_tags": ["test", "debug"]
                }
            })
            
            if "result" in result:
                response_content = result["result"].get("content", [])
                if response_content:
                    text = response_content[0].get("text", "")
                    # Extract memory key from response
                    if "memory_" in text:
                        memory_key = text.split("memory_")[1].split()[0]
                        memory_key = "memory_" + memory_key.replace("'", "").replace('"', '').replace('`', '')
                        print(f"  ✅ Memory created: {memory_key}")
                        return memory_key
            
            print(f"  ❌ Create memory failed: {result}")
            return None
            
        except Exception as e:
            print(f"  ❌ Create memory error: {e}")
            return None
    
    def test_read_memory(self, query: str = TEST_SEARCH_QUERY) -> bool:
        """Test read_memory tool"""
        print(f"\n🔍 Testing read_memory (query: '{query}')...")
        try:
            result = self._send_request("tools/call", {
                "name": "read_memory",
                "arguments": {
                    "query": query,
                    "top_k": 3
                }
            })
            
            if "result" in result:
                content = result["result"].get("content", [])
                if content:
                    text = content[0].get("text", "")
                    # Count results
                    result_count = text.count("**Result")
                    print(f"  ✅ Found {result_count} memories")
                    return True
            
            print(f"  ❌ Read memory failed: {result}")
            return False
            
        except Exception as e:
            print(f"  ❌ Read memory error: {e}")
            return False
    
    def test_search_memory(self, query: str = TEST_SEARCH_QUERY) -> bool:
        """Test search_memory tool"""
        print(f"\n🔎 Testing search_memory (query: '{query}')...")
        try:
            result = self._send_request("tools/call", {
                "name": "search_memory",
                "arguments": {
                    "query": query,
                    "top_k": 3,
                    "fuzzy_match": True
                }
            })
            
            if "result" in result:
                content = result["result"].get("content", [])
                if content:
                    text = content[0].get("text", "")
                    # Count results
                    result_count = text.count("key:")
                    print(f"  ✅ Found {result_count} memories")
                    return True
            
            print(f"  ❌ Search memory failed: {result}")
            return False
            
        except Exception as e:
            print(f"  ❌ Search memory error: {e}")
            return False
    
    def test_delete_memory(self, memory_key: str) -> bool:
        """Test delete_memory tool"""
        print(f"\n🗑️  Testing delete_memory (key: {memory_key})...")
        try:
            result = self._send_request("tools/call", {
                "name": "delete_memory",
                "arguments": {
                    "key_or_query": memory_key
                }
            })
            
            if "result" in result:
                content = result["result"].get("content", [])
                if content:
                    text = content[0].get("text", "")
                    if "削除しました" in text or "Deleted" in text:
                        print(f"  ✅ Memory deleted successfully")
                        return True
            
            print(f"  ❌ Delete memory failed: {result}")
            return False
            
        except Exception as e:
            print(f"  ❌ Delete memory error: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """Run all tests in sequence"""
        print("=" * 60)
        print("🧪 MCP HTTP Endpoint Test Suite")
        print("=" * 60)
        
        results = []
        
        # Basic connectivity
        results.append(("Health Check", self.test_health()))
        results.append(("MCP Initialize", self.test_initialize()))
        results.append(("List Tools", self.test_list_tools()))
        
        # Tool tests
        results.append(("Get Session Context", self.test_get_session_context()))
        
        # CRUD operations
        memory_key = self.test_create_memory()
        results.append(("Create Memory", memory_key is not None))
        
        results.append(("Read Memory", self.test_read_memory()))
        results.append(("Search Memory", self.test_search_memory()))
        
        if memory_key:
            results.append(("Delete Memory", self.test_delete_memory(memory_key)))
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 Test Summary")
        print("=" * 60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} - {test_name}")
        
        print("-" * 60)
        print(f"Total: {passed}/{total} passed ({passed/total*100:.1f}%)")
        print("=" * 60)
        
        return passed == total


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test MCP HTTP endpoints")
    parser.add_argument("--url", default=DEFAULT_MCP_URL, help="MCP server URL")
    args = parser.parse_args()
    
    tester = MCPTester(args.url)
    
    try:
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
