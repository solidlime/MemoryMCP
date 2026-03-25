#!/usr/bin/env python3
"""
Test MCP REST API endpoints locally

This script tests the /mcp/v1/tools/* endpoints to ensure they are correctly configured.
"""

import sys
from pathlib import Path

import requests

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_endpoint(url: str, method: str = "POST", data: dict = None, persona: str = "nilou"):
    """Test a single endpoint"""
    headers = {"Authorization": f"Bearer {persona}", "Content-Type": "application/json"}

    try:
        if method == "POST":
            response = requests.post(url, headers=headers, json=data or {}, timeout=10)
        else:
            response = requests.get(url, headers=headers, timeout=10)

        print(f"\n{'=' * 60}")
        print(f"Testing: {method} {url}")
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            print("✅ Success")
            result = response.json()
            print(f"Response preview: {str(result)[:200]}...")
        else:
            print(f"❌ Failed: {response.status_code}")
            print(f"Response: {response.text[:200]}")

        return response.status_code == 200

    except requests.exceptions.ConnectionError:
        print(f"\n{'=' * 60}")
        print(f"Testing: {method} {url}")
        print("⚠️  Server not running - Connection refused")
        return None
    except Exception as e:
        print(f"\n{'=' * 60}")
        print(f"Testing: {method} {url}")
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all endpoint tests"""
    # Load config to get server URL
    from src.utils.config_utils import load_config

    config = load_config()

    server_url = config.get("mcp_server", {}).get("url", "http://localhost:26262")
    print(f"🌐 Testing MCP endpoints at: {server_url}")

    results = []

    # Test get_context (both GET and POST)
    results.append(
        ("GET /mcp/v1/tools/get_context", test_endpoint(f"{server_url}/mcp/v1/tools/get_context", method="GET"))
    )
    results.append(
        ("POST /mcp/v1/tools/get_context", test_endpoint(f"{server_url}/mcp/v1/tools/get_context", method="POST"))
    )

    # Test memory tool
    results.append(
        (
            "POST /mcp/v1/tools/memory (stats)",
            test_endpoint(f"{server_url}/mcp/v1/tools/memory", data={"operation": "stats"}),
        )
    )

    # Test item tool
    results.append(
        (
            "POST /mcp/v1/tools/item (stats)",
            test_endpoint(f"{server_url}/mcp/v1/tools/item", data={"operation": "stats"}),
        )
    )

    # Summary
    print(f"\n{'=' * 60}")
    print("📊 Test Summary:")
    print(f"{'=' * 60}")

    success_count = sum(1 for _, result in results if result is True)
    failed_count = sum(1 for _, result in results if result is False)
    skipped_count = sum(1 for _, result in results if result is None)

    for name, result in results:
        if result is True:
            print(f"✅ {name}")
        elif result is False:
            print(f"❌ {name}")
        else:
            print(f"⚠️  {name} (server not running)")

    print(f"\n✅ Passed: {success_count}")
    print(f"❌ Failed: {failed_count}")
    print(f"⚠️  Skipped (server not running): {skipped_count}")

    if skipped_count > 0:
        print("\n💡 Note: Start the MCP server to run these tests:")
        print("   python memory_mcp.py")
        return 0

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
