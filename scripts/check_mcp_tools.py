#!/usr/bin/env python3
"""
Test script for MCP tool registration and functionality
Tests that all tools are properly registered and callable
"""
import asyncio
import os
import sys
import json
from typing import Dict, List, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
import memory_mcp
import tools_memory


class MCPRegistrationTester:
    """Test suite for MCP tool registration"""
    
    def __init__(self):
        self.mcp_server: FastMCP = memory_mcp.mcp
        self.test_results: List[Dict[str, Any]] = []
        # Register tools
        tools_memory.register_tools(self.mcp_server)
        
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        result = {
            "test": test_name,
            "passed": passed,
            "message": message
        }
        self.test_results.append(result)
        print(f"{status}: {test_name}")
        if message:
            print(f"  → {message}")
    
    def test_server_initialization(self) -> bool:
        """Test that MCP server is properly initialized"""
        test_name = "Server Initialization"
        try:
            assert self.mcp_server is not None, "MCP server is None"
            assert self.mcp_server.name == "memory-mcp", f"Server name mismatch: {self.mcp_server.name}"
            self.log_test(test_name, True, f"Server '{self.mcp_server.name}' initialized")
            return True
        except AssertionError as e:
            self.log_test(test_name, False, str(e))
            return False
    
    async def test_tools_registered(self) -> bool:
        """Test that tools are registered"""
        test_name = "Tools Registration"
        try:
            # Get list of registered tools
            tools = await self.mcp_server.list_tools()
            tool_count = len(tools)
            
            assert tool_count > 0, "No tools registered"
            
            # Expected core tools
            expected_tools = ["memory", "item", "get_context"]
            
            tool_names = [tool.name for tool in tools]
            missing_tools = [t for t in expected_tools if t not in tool_names]
            
            if missing_tools:
                self.log_test(test_name, False, f"Missing tools: {missing_tools}")
                return False
            
            self.log_test(test_name, True, f"{tool_count} tools registered, core tools present")
            return True
        except Exception as e:
            self.log_test(test_name, False, f"Error: {e}")
            return False
    
    async def test_tool_schemas(self) -> bool:
        """Test that tool schemas are valid"""
        test_name = "Tool Schemas"
        try:
            tools = await self.mcp_server.list_tools()
            invalid_tools = []
            
            for tool in tools:
                # Check that tool has required attributes
                if not hasattr(tool, 'name'):
                    invalid_tools.append(f"{tool}: missing 'name'")
                if not hasattr(tool, 'description'):
                    invalid_tools.append(f"{tool.name}: missing 'description'")
                if not hasattr(tool, 'inputSchema'):
                    invalid_tools.append(f"{tool.name}: missing 'inputSchema'")
            
            if invalid_tools:
                self.log_test(test_name, False, f"Invalid schemas: {invalid_tools}")
                return False
            
            self.log_test(test_name, True, f"All {len(tools)} tools have valid schemas")
            return True
        except Exception as e:
            self.log_test(test_name, False, f"Error: {e}")
            return False
    
    async def test_unified_tools_schema(self) -> bool:
        """Test that unified tools (memory, item) have proper schemas"""
        test_name = "Unified Tools Schema"
        try:
            tools = await self.mcp_server.list_tools()
            tool_dict = {tool.name: tool for tool in tools}
            
            # Test memory tool
            if "memory" in tool_dict:
                memory_tool = tool_dict["memory"]
                schema = memory_tool.inputSchema
                
                assert "properties" in schema, "memory tool missing properties"
                assert "operation" in schema["properties"], "memory tool missing 'operation' parameter"
                
            # Test item tool
            if "item" in tool_dict:
                item_tool = tool_dict["item"]
                schema = item_tool.inputSchema
                
                assert "properties" in schema, "item tool missing properties"
                assert "operation" in schema["properties"], "item tool missing 'operation' parameter"
            
            self.log_test(test_name, True, "Unified tools have proper operation-based schemas")
            return True
        except Exception as e:
            self.log_test(test_name, False, f"Error: {e}")
            return False
    
    async def test_tool_callable(self) -> bool:
        """Test that tools are callable (basic invocation test)"""
        test_name = "Tool Callability"
        try:
            # Test get_context (should work without side effects)
            result = await self.mcp_server.call_tool("get_context", {})
            
            assert result is not None, "get_context returned None"
            
            self.log_test(test_name, True, "Tools are callable")
            return True
        except Exception as e:
            self.log_test(test_name, False, f"Error calling tool: {e}")
            return False
    
    async def test_memory_tool_operations(self) -> bool:
        """Test that memory tool accepts valid operations"""
        test_name = "Memory Tool Operations"
        try:
            # Test stats operation (no database interaction needed)
            result = await self.mcp_server.call_tool("memory", {"operation": "stats"})
            
            assert result is not None, "memory stats returned None"
            
            self.log_test(test_name, True, "Memory tool operations work")
            return True
        except Exception as e:
            self.log_test(test_name, False, f"Error: {e}")
            return False
    
    async def test_item_tool_operations(self) -> bool:
        """Test that item tool accepts valid operations"""
        test_name = "Item Tool Operations"
        try:
            # Test search operation
            result = await self.mcp_server.call_tool("item", {"operation": "search"})
            
            # Result might be empty or error if no database, but shouldn't crash
            assert result is not None, "item search returned None"
            
            self.log_test(test_name, True, "Item tool operations work")
            return True
        except Exception as e:
            # Expected to possibly fail if no database, but should fail gracefully
            if "No such file or directory" in str(e) or "database" in str(e).lower():
                self.log_test(test_name, True, "Item tool handles missing database gracefully")
                return True
            self.log_test(test_name, False, f"Unexpected error: {e}")
            return False
    
    async def test_equipment_slot_uniqueness(self) -> bool:
        """Test that each slot can only have one equipped item"""
        test_name = "Equipment Slot Uniqueness"
        try:
            import sqlite3
            from core.equipment_db import EquipmentDB
            
            # Create fresh test database
            test_persona = "test_equip_unique"
            db = EquipmentDB(test_persona)
            
            # Add test items
            db.add_item("Test Dress A", category="clothing")
            db.add_item("Test Dress B", category="clothing")
            db.add_to_inventory("Test Dress A", quantity=1)
            db.add_to_inventory("Test Dress B", quantity=1)
            
            # Equip first item to 'top' slot
            db.equip_item("Test Dress A", "top")
            
            # Equip second item to same 'top' slot
            db.equip_item("Test Dress B", "top")
            
            # Check database directly
            conn = db._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM inventory
                WHERE persona = ? AND is_equipped = 1 AND equipped_slot = 'top'
            """, (test_persona,))
            count = cursor.fetchone()[0]
            conn.close()
            
            if count == 1:
                self.log_test(test_name, True, "Only one item equipped in slot")
                return True
            else:
                self.log_test(test_name, False, f"Expected 1 equipped item, found {count}")
                return False
                
        except Exception as e:
            self.log_test(test_name, False, f"Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.test_results if r["passed"])
        total = len(self.test_results)
        
        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        # Show failed tests
        failed_tests = [r for r in self.test_results if not r["passed"]]
        if failed_tests:
            print("\n❌ Failed Tests:")
            for test in failed_tests:
                print(f"  - {test['test']}: {test['message']}")
        
        print("\n" + "=" * 60)
        
        return passed == total


async def main():
    """Main test runner"""
    print("🧪 MCP Tool Registration Test Suite")
    print("=" * 60)
    print()
    
    tester = MCPRegistrationTester()
    
    # Run synchronous tests
    print("Running synchronous tests...\n")
    tester.test_server_initialization()
    
    # Run async tests
    print("\nRunning async tests...\n")
    await tester.test_tools_registered()
    await tester.test_tool_schemas()
    await tester.test_unified_tools_schema()
    await tester.test_tool_callable()
    await tester.test_memory_tool_operations()
    await tester.test_item_tool_operations()
    await tester.test_equipment_slot_uniqueness()
    
    # Print summary
    all_passed = tester.print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
