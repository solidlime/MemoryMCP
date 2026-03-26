"""詳細バグ調査スクリプト。"""
from playwright.sync_api import sync_playwright
from pathlib import Path

SCREENSHOTS = Path("tests/e2e/screenshots/investigation")
SCREENSHOTS.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # ネットワークエラーを収集
    network_errors = []
    page.on("response", lambda r: network_errors.append(f"{r.status} {r.url}") if r.status >= 400 else None)
    js_errors = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))

    page.goto("http://nas:26262", wait_until="networkidle")
    page.locator("#persona-select").select_option("herta")
    page.wait_for_timeout(2000)
    page.wait_for_load_state("networkidle")

    # ===== ANALYTICS =====
    print("=== ANALYTICS タブ ===")
    page.click('[data-tab="analytics"]')
    page.wait_for_timeout(3000)

    print("canvas IDs:")
    for c in page.locator("canvas").all():
        print(f"  id={c.get_attribute('id')}")
    print("chart-emotions:", page.locator("#chart-emotions").count())
    print("analytics-content HTML snippet:")
    ac_html = page.locator("#analytics-content").inner_html()
    print(ac_html[:2000])
    print()

    # ===== GRAPH =====
    print("=== GRAPH タブ ===")
    page.click('[data-tab="graph"]')
    page.wait_for_timeout(3000)
    print("graph panel inner_text:", repr(page.locator("#tab-graph").inner_text()[:300]))
    print("graph panel inner_html snippet:")
    print(page.locator("#tab-graph").inner_html()[:2000])
    print()

    # ===== IMPORT-EXPORT =====
    print("=== IMPORT-EXPORT タブ ===")
    page.click('[data-tab="import-export"]')
    page.wait_for_timeout(2000)
    print("import-export panel inner_text:", repr(page.locator("#tab-import-export").inner_text()[:300]))
    print("import-export panel inner_html snippet:")
    print(page.locator("#tab-import-export").inner_html()[:2000])
    print()

    # ===== PERSONAS =====
    print("=== PERSONAS タブ ===")
    page.click('[data-tab="personas"]')
    page.wait_for_timeout(2000)
    print("personas panel inner_text:", repr(page.locator("#tab-personas").inner_text()[:300]))
    print("persona-grid inner_html snippet:")
    print(page.locator("#persona-grid").inner_html()[:1000] if page.locator("#persona-grid").count() else "(#persona-grid not found)")
    print()

    print("=== ネットワークエラー ===")
    for e in network_errors:
        print(f"  {e}")

    print("=== JSエラー ===")
    for e in js_errors:
        print(f"  {e}")

    browser.close()
