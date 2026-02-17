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
import os
from pathlib import Path

# Try multiple possible locations for memory_mcp_client.py
# to support both local dev and Docker environments
POSSIBLE_PATHS = [
    # Local development structure
    Path(__file__).parent / ".github" / "skills" / "memory-mcp" / "scripts",
    # Docker/production structure (if mounted at /opt/memory-mcp)
    Path(__file__).parent / "scripts",
    # Alternative: check if we're already in the scripts directory
    Path(__file__).parent,
]

# Add environment variable override
if env_path := os.getenv("MEMORY_MCP_SCRIPTS_DIR"):
    POSSIBLE_PATHS.insert(0, Path(env_path))

# Find the correct scripts directory
scripts_dir = None
for path in POSSIBLE_PATHS:
    if (path / "memory_mcp_client.py").exists():
        scripts_dir = path
        break

if not scripts_dir:
    print("❌ Error: Could not locate memory_mcp_client.py", file=sys.stderr)
    print("   Searched in:", file=sys.stderr)
    for path in POSSIBLE_PATHS:
        print(f"     - {path}", file=sys.stderr)
    print("\n   Set MEMORY_MCP_SCRIPTS_DIR environment variable to specify location", file=sys.stderr)
    sys.exit(1)

# Add scripts directory to Python path
sys.path.insert(0, str(scripts_dir))

# Import and run the main client
try:
    from memory_mcp_client import main

    if __name__ == "__main__":
        sys.exit(main())
except ImportError as e:
    print(f"❌ Error: Could not import memory_mcp_client: {e}", file=sys.stderr)
    print(f"   Scripts directory: {scripts_dir}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}", file=sys.stderr)
    sys.exit(1)
