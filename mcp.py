#!/usr/bin/env python3
"""
MCP Client Wrapper - Cross-platform helper for Memory MCP operations

This wrapper provides a simplified interface to Memory MCP client,
making it easy to use on both Windows and Unix-like systems.

Usage:
    python mcp.py --persona nilou get_context
    python mcp.py --persona nilou memory create --content "..." --importance 0.8
    python mcp.py --persona nilou item equip --slot top --name "Red Dress"

All arguments are passed directly to the underlying memory_mcp_client.py script.
"""
import sys
from pathlib import Path

# Add scripts directory to Python path
SCRIPTS_DIR = Path(__file__).parent / ".github" / "skills" / "memory-mcp" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# Import and run the main client
try:
    from memory_mcp_client import main

    if __name__ == "__main__":
        sys.exit(main())
except ImportError as e:
    print(f"❌ Error: Could not import memory_mcp_client: {e}", file=sys.stderr)
    print(f"   Expected location: {SCRIPTS_DIR / 'memory_mcp_client.py'}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}", file=sys.stderr)
    sys.exit(1)
