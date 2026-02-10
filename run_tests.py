"""
Memory MCP Test Runner
Simple test runner for Memory MCP Server

使い方:
    # すべてのテストを実行
    python run_tests.py

    # 特定のテストのみ
    python run_tests.py --test http
    python run_tests.py --test search
    python run_tests.py --test migrate

    # 詳細出力
    python run_tests.py -v
"""

import argparse
import subprocess
import sys
from pathlib import Path

# テスト定義
TESTS = {
    "http": {
        "name": "HTTP API Test",
        "file": "tests/test_http_api.py",
        "description": "MCPサーバーのHTTPエンドポイントをテスト"
    },
    "search": {
        "name": "Search Accuracy Test",
        "file": "tests/test_search_accuracy.py",
        "description": "検索機能の精度をテスト"
    },
    "migrate": {
        "name": "Schema Migration",
        "file": "tests/migrate_schema.py",
        "description": "データベーススキーママイグレーション"
    }
}


def run_test(test_key: str, verbose: bool = False) -> bool:
    """
    指定されたテストを実行

    Args:
        test_key: テストキー
        verbose: 詳細出力

    Returns:
        成功時True、失敗時False
    """
    test = TESTS.get(test_key)
    if not test:
        print(f"❌ Unknown test: {test_key}")
        return False

    print(f"\n{'=' * 60}")
    print(f"🧪 {test['name']}")
    print(f"📝 {test['description']}")
    print(f"{'=' * 60}\n")

    test_file = Path(test["file"])
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(test_file)],
            capture_output=not verbose,
            text=True,
            timeout=300  # 5 minutes
        )

        if result.returncode == 0:
            print(f"✅ {test['name']} passed!")
            if verbose and result.stdout:
                print(result.stdout)
            return True
        else:
            print(f"❌ {test['name']} failed!")
            if result.stderr:
                print("Error output:")
                print(result.stderr)
            if verbose and result.stdout:
                print("Standard output:")
                print(result.stdout)
            return False

    except subprocess.TimeoutExpired:
        print(f"⏱️  {test['name']} timed out!")
        return False
    except Exception as e:
        print(f"❌ Error running {test['name']}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Memory MCP Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--test", "-t",
        choices=list(TESTS.keys()),
        help="Run specific test (default: all)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available tests"
    )

    args = parser.parse_args()

    if args.list:
        print("\n📋 Available Tests:\n")
        for key, test in TESTS.items():
            print(f"  {key:10} - {test['name']}")
            print(f"             {test['description']}")
            print()
        return

    # Run tests
    if args.test:
        # Run specific test
        success = run_test(args.test, args.verbose)
        sys.exit(0 if success else 1)
    else:
        # Run all tests
        print("\n🚀 Running all tests...\n")
        results = {}
        for test_key in TESTS:
            results[test_key] = run_test(test_key, args.verbose)

        # Summary
        print(f"\n{'=' * 60}")
        print("📊 Test Summary")
        print(f"{'=' * 60}\n")

        passed = sum(1 for r in results.values() if r)
        total = len(results)

        for test_key, success in results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"  {status} - {TESTS[test_key]['name']}")

        print(f"\n📈 Result: {passed}/{total} tests passed")

        sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
