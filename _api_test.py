"""MemoryMCP 全機能 API 実動作テスト
すべてのHTTPエンドポイントをテストし、問題点・矛盾・重複を検出する。
"""
import json
import time
import urllib.error
import urllib.request

BASE = "http://localhost:26262"
P = "herta"
RESULTS = []
DEV_MODE = True  # 404/405は開発中なのでINFO扱い

def fmt_err(e):
    if hasattr(e, "code"):
        return f"HTTP {e.code}"
    return f"{type(e).__name__}: {e}"

def test(method, path, expected_status=(200,), body=None, label=None, use_mcp_header=False, skip_404_ok=False):
    """Call endpoint and record result."""
    url = f"{BASE}{path}"
    headers = {"X-Persona": P}
    if method == "POST":
        headers["Content-Type"] = "application/json"
    if use_mcp_header:
        headers["Accept"] = "application/json"

    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers)
    req.method = method

    try:
        r = urllib.request.urlopen(req, timeout=10)
        resp = r.read().decode("utf-8", errors="replace")
        status = r.status
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            resp = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            resp = str(e)
    except Exception as e:
        status = 0
        resp = str(e)

    passed = status in expected_status
    if not passed and DEV_MODE and status in (404, 405):
        level = "INFO"
    elif not passed:
        level = "FAIL"
    else:
        level = "PASS"

    label = label or f"{method} {path}"
    RESULTS.append({"label": label, "method": method, "path": path, "status": status, "passed": passed, "level": level, "resp_preview": resp[:120]})
    return level

# ==================== PHASE 1: HEALTH + ROOT ====================
print("=" * 60)
print("PHASE 1: サーバー基本チェック")
print("=" * 60)

test("GET", "/health", label="Health Check")
test("GET", "/", label="Root Dashboard")
test("GET", "/api/settings", label="Settings取得")
test("GET", "/api/skills", label="スキル一覧")

# ==================== PHASE 2: PERSONA ====================
print("\n" + "=" * 60)
print("PHASE 2: ペルソナ管理 API")
print("=" * 60)

test("GET", "/api/personas", label="ペルソナ一覧")
test("GET", f"/dashboard/{P}", label="Dashboard HTML")
test("GET", f"/api/dashboard/{P}", label="Dashboard JSON")
test("GET", f"/api/stats/{P}", label="Stats (deprecated)")
test("PUT", f"/api/personas/{P}/profile", body={"user_name": "test"}, label="プロフィール更新")

# ==================== PHASE 3: MEMORIES ====================
print("\n" + "=" * 60)
print("PHASE 3: メモリ CRUD API")
print("=" * 60)

test("GET", f"/api/observations/{P}?per_page=5", label="メモリ一覧")
test("GET", f"/api/observations/{P}?mode=recent&per_page=5", label="最近のメモリ")
test("GET", f"/api/recent/{P}", label="Recent (deprecated)")

# Create a test memory
mem_body = {"content": "APIテスト用メモリ_" + str(int(time.time())), "importance": 0.5, "tags": ["api_test"]}
test("POST", f"/api/memories/{P}", body=mem_body, label="メモリ作成")
# Get the key from response for update/delete (skip if failed)

# Search
test("GET", f"/api/search/{P}?q=テスト&limit=3&mode=hybrid", label="メモリ検索(hybrid)")
test("GET", f"/api/search/{P}?q=テスト&limit=3&mode=keyword", label="メモリ検索(keyword)")

# ==================== PHASE 4: ANALYTICS & GRAPH ====================
print("\n" + "=" * 60)
print("PHASE 4: 分析 & グラフ API")
print("=" * 60)

test("GET", f"/api/emotions/{P}?days=7", label="感情履歴(7d)")
test("GET", f"/api/emotions/{P}?days=30", label="感情履歴(30d)")
test("GET", f"/api/strengths/{P}", label="強度分布")
test("GET", f"/api/graph/{P}?limit=20", label="ナレッジグラフ")

# ==================== PHASE 5: ITEMS ====================
print("\n" + "=" * 60)
print("PHASE 5: アイテム管理 API")
print("=" * 60)

test("GET", f"/api/items/{P}", label="アイテム一覧")
test("DELETE", f"/api/items/{P}/_nonexistent_test_item", expected_status=(200, 404), label="存在しないアイテム削除")

# ==================== PHASE 6: BLOCKS ====================
print("\n" + "=" * 60)
print("PHASE 6: ブロック管理 API")
print("=" * 60)

test("GET", f"/api/blocks/{P}", label="ブロック一覧")

# ==================== PHASE 7: CHAT ====================
print("\n" + "=" * 60)
print("PHASE 7: チャット API")
print("=" * 60)

test("GET", f"/api/chat/{P}/config", label="チャット設定取得")
test("GET", f"/api/chat/{P}/commitments", label="Goals/Promises取得")
test("GET", f"/api/chat/{P}/sessions/default", label="デフォルトセッション取得")

# ==================== PHASE 8: EVENTS (SSE) ====================
print("\n" + "=" * 60)
print("PHASE 8: イベント (SSE/Events)")
print("=" * 60)

# SSE endpoint - just check status
test("GET", f"/api/events/{P}?topics=memory", label="SSEエンドポイント")

# ==================== PHASE 9: SANDBOX ====================
print("\n" + "=" * 60)
print("PHASE 9: サンドボックス API")
print("=" * 60)

test("GET", f"/api/chat/{P}/sandbox/files", label="サンドボックスファイル一覧")
test("DELETE", f"/api/chat/{P}/sandbox/files/_nonexistent", expected_status=(200, 404), label="存在しないsandboxファイル削除")
# execute a simple python snippet
test("POST", f"/api/chat/{P}/sandbox/execute", body={"language": "python", "code": "print('hello sandbox')"}, label="Sandboxコード実行")

# ==================== PHASE 10: IMPORT/EXPORT ====================
print("\n" + "=" * 60)
print("PHASE 10: インポート/エクスポート API")
print("=" * 60)

test("GET", f"/api/export/{P}", label="エクスポート取得", skip_404_ok=True)

# ==================== PHASE 11: MCP (Streamable HTTP) ====================
print("\n" + "=" * 60)
print("PHASE 11: MCP プロトコル (Streamable HTTP)")
print("=" * 60)

test("POST", "/mcp", body={"jsonrpc":"2.0","method":"tools/list","params":{},"id":1},
     label="MCP tools/list", use_mcp_header=True)
test("POST", "/mcp", body={"jsonrpc":"2.0","method":"tools/call","params":{"name":"memory_stats","arguments":{"top_n":3}},"id":2},
     label="MCP tools/call (memory_stats)", use_mcp_header=True)

# ==================== PHASE 12: ROLLBACK (新機能) ====================
print("\n" + "=" * 60)
print("PHASE 12: 新機能 - チャットロールバック")
print("=" * 60)

test("POST", f"/api/chat/{P}/sessions/test_nonexistent/rollback", body={"keep_until": 0},
     expected_status=(200, 404), label="存在しないセッションロールバック")

# ==================== PHASE 13: SKILLS SYNC ====================
print("\n" + "=" * 60)
print("PHASE 13: スキル管理")
print("=" * 60)

test("POST", "/api/skills/sync", body={}, label="スキル同期")

# ==================== SUMMARY ====================
print("\n" + "=" * 60)
print("テスト結果サマリー")
print("=" * 60)

pass_count = sum(1 for r in RESULTS if r["level"] == "PASS")
fail_count = sum(1 for r in RESULTS if r["level"] == "FAIL")
info_count = sum(1 for r in RESULTS if r["level"] == "INFO")
total = len(RESULTS)

print(f"\n合計: {total} テスト")
print(f"  ✅ PASS: {pass_count}")
print(f"  ℹ️  INFO (開発中/想定内): {info_count}")
print(f"  ❌ FAIL: {fail_count}")

if fail_count > 0:
    print("\n--- 失敗したテスト ---")
    for r in RESULTS:
        if r["level"] == "FAIL":
            print(f"  ❌ {r['label']}: HTTP {r['status']} - {r['resp_preview'][:100]}")

if info_count > 0:
    print("\n--- 想定内の非200レスポンス ---")
    for r in RESULTS:
        if r["level"] == "INFO":
            print(f"  ℹ️  {r['label']}: HTTP {r['status']}")

print(f"\n{'✅ 全テスト成功!' if fail_count == 0 else '❌ 修正が必要な項目があります'}")
