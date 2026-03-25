"""
Playwright E2E Test Fixtures.

MemoryMCP WebUI ダッシュボードの E2E テスト用フィクスチャ集。
テスト専用サーバーを起動し、テストペルソナにシードデータを投入する。
環境変数 MEMORY_MCP_URL が設定されている場合は既存サーバーを再利用する。
"""

import os
import shutil
import subprocess
import time

import pytest
import requests

# 環境変数 MEMORY_MCP_URL がある場合は既存サーバーを再利用
EXTERNAL_URL = os.environ.get("MEMORY_MCP_URL")
TEST_PORT = int(os.environ.get("MEMORY_MCP_PORT", "26299"))
BASE_URL = EXTERNAL_URL or f"http://localhost:{TEST_PORT}"

TEST_PERSONA = "e2e_test_persona"
DASHBOARD_URL = f"{BASE_URL}"

# テスト用データディレクトリ
E2E_DATA_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "e2e_test")


@pytest.fixture(scope="session")
def server():
    """MemoryMCPサーバーをE2Eテスト用に起動する。MEMORY_MCP_URL が設定されている場合はスキップ。"""
    if EXTERNAL_URL:
        # 既存サーバーのヘルスチェックのみ
        for _ in range(30):
            try:
                r = requests.get(f"{EXTERNAL_URL}/health", timeout=2)
                if r.status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(2)
        else:
            raise RuntimeError(f"External server at {EXTERNAL_URL} is not responding")
        yield None
        return

    env = os.environ.copy()
    env["MEMORY_MCP_SERVER_PORT"] = str(TEST_PORT)
    env["MEMORY_MCP_DATA_ROOT"] = E2E_DATA_ROOT

    proc = subprocess.Popen(
        ["python", "-m", "memory_mcp.main"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
    )

    # サーバー起動待ち（最大60秒）
    for _ in range(60):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=2)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        stdout, stderr = proc.communicate(timeout=5)
        proc.kill()
        raise RuntimeError(
            f"Server failed to start within 60s.\n"
            f"stdout: {stdout.decode(errors='replace')[-500:]}\n"
            f"stderr: {stderr.decode(errors='replace')[-500:]}"
        )

    yield proc

    proc.kill()
    proc.wait(timeout=10)


@pytest.fixture(scope="session")
def base_url():
    """ダッシュボードのベースURL。"""
    return DASHBOARD_URL


@pytest.fixture(scope="session")
def dashboard_url():
    """テストペルソナのダッシュボードURL。"""
    return f"{DASHBOARD_URL}/dashboard/{TEST_PERSONA}"


@pytest.fixture(scope="session")
def api_url():
    """APIのベースURL。"""
    return BASE_URL


@pytest.fixture(scope="session")
def browser_context(server, browser, dashboard_url):
    """ダッシュボードURL付きのブラウザコンテキスト。"""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
    )
    yield context
    context.close()


@pytest.fixture
def page(browser_context, dashboard_url):
    """各テスト用の新しいページ。"""
    pg = browser_context.new_page()
    pg.goto(dashboard_url)
    pg.wait_for_load_state("networkidle")
    yield pg
    pg.close()


@pytest.fixture
def mobile_page(server, browser, dashboard_url):
    """モバイルビューポートのページ。"""
    context = browser.new_context(
        viewport={"width": 375, "height": 667},
        is_mobile=True,
    )
    pg = context.new_page()
    pg.goto(dashboard_url)
    pg.wait_for_load_state("networkidle")
    yield pg
    pg.close()
    context.close()


@pytest.fixture(scope="session", autouse=True)
def seed_test_data(server):
    """テストデータをAPIでシード投入する。"""
    emotions = ["joy", "sadness", "trust", "neutral", "surprise"]
    for i in range(5):
        try:
            requests.post(
                f"{BASE_URL}/api/memories/{TEST_PERSONA}",
                json={
                    "content": (
                        f"E2E test memory {i}: "
                        f"This is a test memory for E2E testing with enough content to be meaningful. "
                        f"テスト記憶データ {i} — 日本語コンテンツも含む。"
                    ),
                    "importance": round(0.3 + (i * 0.15), 2),
                    "emotion_type": emotions[i],
                    "tags": [f"e2e_tag_{i}", "e2e", "playwright"],
                },
                timeout=10,
            )
        except Exception as e:
            print(f"Warning: Failed to seed memory {i}: {e}")

    yield

    # クリーンアップ: テスト用データディレクトリを削除
    try:
        if os.path.exists(E2E_DATA_ROOT):
            shutil.rmtree(E2E_DATA_ROOT, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture
def screenshot_dir():
    """スクリーンショット保存先ディレクトリ。"""
    d = os.path.join(os.path.dirname(__file__), "screenshots")
    os.makedirs(d, exist_ok=True)
    return d
