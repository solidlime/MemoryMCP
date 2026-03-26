"""
WebUI バグ調査スクリプト。
http://nas:26262 のルートから全タブを操作し、バグ・エラーを収集する。
"""

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://nas:26262"
PERSONA = "herta"
DASHBOARD_URL = BASE_URL  # dashboard は / で提供される
SCREENSHOTS_DIR = Path(__file__).parent.parent / "tests" / "e2e" / "screenshots" / "investigation"

TABS = [
    "overview",
    "analytics",
    "memories",
    "graph",
    "import-export",
    "personas",
    "settings",
    "admin",
]


def save_screenshot(page, name: str):
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOTS_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"  📸 Screenshot: {path.name}")


def run_investigation():
    bugs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})

        # --- コンソールエラー収集 ---
        console_errors: list[str] = []
        js_errors: list[str] = []

        page = context.new_page()
        page.on("pageerror", lambda e: js_errors.append(str(e)))
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ("error", "warning") else None)

        # =====================================================================
        # 1. ルートアクセス
        # =====================================================================
        print("\n=== 1. ルートアクセス ===")
        try:
            resp = page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
            print(f"  Status: {resp.status if resp else 'N/A'}")
            save_screenshot(page, "01_root")
            url_after = page.url
            print(f"  Redirected to: {url_after}")
            if resp and resp.status >= 400:
                bugs.append({"tab": "root", "bug": f"ルートが {resp.status} を返す"})
        except Exception as e:
            bugs.append({"tab": "root", "bug": f"ルートアクセス失敗: {e}"})
            print(f"  ❌ ERROR: {e}")

        # =====================================================================
        # 2. ダッシュボードへ直接アクセス
        # =====================================================================
        print(f"\n=== 2. ダッシュボード ({DASHBOARD_URL}) ===")
        try:
            resp = page.goto(DASHBOARD_URL, wait_until="networkidle", timeout=20000)
            print(f"  Status: {resp.status if resp else 'N/A'}")
            title = page.title()
            print(f"  Title: {title}")
            save_screenshot(page, "02_dashboard_initial")
            if resp and resp.status >= 400:
                bugs.append({"tab": "dashboard", "bug": f"ダッシュボードが {resp.status} を返す"})
        except Exception as e:
            bugs.append({"tab": "dashboard", "bug": f"ダッシュボードアクセス失敗: {e}"})
            print(f"  ❌ ERROR: {e}")

        # =====================================================================
        # 2b. ペルソナ選択
        # =====================================================================
        print(f"\n=== 2b. ペルソナ選択: {PERSONA} ===")
        try:
            sel = page.locator("#persona-select")
            if sel.count() == 0:
                bugs.append({"tab": "persona-select", "bug": "#persona-select が存在しない"})
                print("  ❌ #persona-select 未検出")
            else:
                # 選択肢一覧
                options = sel.locator("option").all_text_contents()
                print(f"  選択肢: {options}")
                if PERSONA in options or any(PERSONA in o for o in options):
                    sel.select_option(PERSONA)
                    page.wait_for_timeout(2000)
                    page.wait_for_load_state("networkidle")
                    save_screenshot(page, "02b_persona_selected")
                    print(f"  ✅ {PERSONA} 選択完了")
                else:
                    bugs.append({"tab": "persona-select", "bug": f"ペルソナ '{PERSONA}' が選択肢にない: {options}"})
                    print(f"  ❌ {PERSONA} が選択肢にない")
                    # 最初の選択肢を使う
                    if options:
                        first = options[0].strip()
                        sel.select_option(index=0)
                        page.wait_for_timeout(2000)
                        print(f"  ℹ️ 代わりに '{first}' を選択")
        except Exception as e:
            bugs.append({"tab": "persona-select", "bug": f"ペルソナ選択エラー: {e}"})
            print(f"  ❌ EXCEPTION: {e}")

        # =====================================================================
        # 3. 全タブを順に操作
        # =====================================================================
        for tab in TABS:
            print(f"\n=== タブ: {tab} ===")
            tab_errors_before = len(js_errors)

            try:
                btn = page.locator(f"[data-tab='{tab}']")
                if btn.count() == 0:
                    bugs.append({"tab": tab, "bug": "タブボタンが DOM に存在しない"})
                    print(f"  ❌ タブボタン未検出")
                    continue

                btn.click()
                page.wait_for_timeout(2500)
                save_screenshot(page, f"03_tab_{tab}")

                # パネル表示チェック
                panel = page.locator(f"#tab-{tab}")
                if panel.count() == 0:
                    bugs.append({"tab": tab, "bug": f"#tab-{tab} パネルが DOM に存在しない"})
                    print(f"  ❌ パネル未検出: #tab-{tab}")
                elif not panel.is_visible():
                    bugs.append({"tab": tab, "bug": f"#tab-{tab} パネルが表示されていない"})
                    print(f"  ❌ パネル非表示")
                else:
                    print(f"  ✅ パネル表示OK")

                # active クラスチェック
                active_panel = page.locator(f"#tab-{tab}.active")
                if active_panel.count() == 0:
                    bugs.append({"tab": tab, "bug": f"#tab-{tab} に .active クラスが付いていない"})
                    print(f"  ❌ .active クラスなし")
                else:
                    print(f"  ✅ .active クラスあり")

                # active パネル数チェック（1つだけのはず）
                active_panels = page.locator(".tab-panel.active")
                count = active_panels.count()
                if count != 1:
                    bugs.append({"tab": tab, "bug": f"active パネルが {count} 個ある（1個のはず）"})
                    print(f"  ❌ active パネル数: {count}")

                # コンテンツチェック
                text = page.locator(f"#tab-{tab}").inner_text()
                if len(text.strip()) < 10:
                    bugs.append({"tab": tab, "bug": f"パネルのコンテンツが空（{len(text.strip())}文字）"})
                    print(f"  ❌ コンテンツ空 ({len(text.strip())}文字)")
                else:
                    print(f"  ✅ コンテンツあり ({len(text.strip())}文字)")

                # タブ固有チェック
                _check_tab_specific(page, tab, bugs)

                # JS エラー
                new_js_errors = js_errors[tab_errors_before:]
                if new_js_errors:
                    for err in new_js_errors:
                        bugs.append({"tab": tab, "bug": f"JSエラー: {err}"})
                    print(f"  ❌ JSエラー {len(new_js_errors)}件: {new_js_errors[:2]}")
                else:
                    print(f"  ✅ JSエラーなし")

            except Exception as e:
                bugs.append({"tab": tab, "bug": f"タブ操作中に例外: {e}"})
                print(f"  ❌ EXCEPTION: {e}")

        # =====================================================================
        # 4. API エンドポイント確認
        # =====================================================================
        print("\n=== 4. API エンドポイント確認 ===")
        api_endpoints = [
            f"/api/stats/{PERSONA}",
            f"/api/recent/{PERSONA}",
            f"/api/emotions/{PERSONA}",
            f"/api/observations/{PERSONA}",
            f"/api/strengths/{PERSONA}",
            f"/api/graph/{PERSONA}",
            f"/api/items/{PERSONA}",
            "/api/settings",
            "/api/personas",
        ]
        for ep in api_endpoints:
            try:
                resp = page.goto(f"{BASE_URL}{ep}", wait_until="domcontentloaded", timeout=10000)
                status = resp.status if resp else "?"
                body = page.content()
                # JSONパース試行
                try:
                    json.loads(page.evaluate("document.body.innerText"))
                    print(f"  {status} ✅ {ep}")
                except Exception:
                    if status < 400:
                        print(f"  {status} ⚠️  {ep} (非JSON?)")
                    else:
                        bugs.append({"tab": "api", "bug": f"{ep} が {status} を返す"})
                        print(f"  {status} ❌ {ep}")
            except Exception as e:
                bugs.append({"tab": "api", "bug": f"{ep} でエラー: {e}"})
                print(f"  ❌ {ep}: {e}")

        # =====================================================================
        # 5. コンソールエラーまとめ
        # =====================================================================
        print("\n=== 5. コンソールエラーまとめ ===")
        if console_errors:
            for e in console_errors[:20]:
                print(f"  {e}")
        else:
            print("  (なし)")

        browser.close()

    # =====================================================================
    # 結果出力
    # =====================================================================
    print("\n" + "=" * 60)
    print(f"🐛 発見したバグ: {len(bugs)} 件")
    print("=" * 60)
    for i, b in enumerate(bugs, 1):
        print(f"  [{i}] [{b['tab']}] {b['bug']}")

    # JSON保存
    out = SCREENSHOTS_DIR / "bugs.json"
    out.write_text(json.dumps(bugs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📄 バグリスト保存: {out}")
    return bugs


def _check_tab_specific(page, tab: str, bugs: list):
    """タブ固有の要素チェック。"""
    if tab == "analytics":
        # 感情チャートとフィルターボタン
        btns = page.locator(".emo-days-btn")
        if btns.count() != 4:
            bugs.append({"tab": tab, "bug": f".emo-days-btn が {btns.count()} 個（4個のはず）"})
            print(f"    ❌ 期間フィルターボタン数: {btns.count()}")
        else:
            print(f"    ✅ 期間フィルターボタン: {btns.count()} 個")

        # チャート canvas
        for cid in ("#chart-emotions", "#chart-strength"):
            c = page.locator(cid)
            if c.count() == 0:
                bugs.append({"tab": tab, "bug": f"{cid} が存在しない"})
                print(f"    ❌ canvas {cid} 未検出")
            else:
                print(f"    ✅ canvas {cid} あり")

        # #analytics-content
        ac = page.locator("#analytics-content")
        if ac.count() == 0:
            bugs.append({"tab": tab, "bug": "#analytics-content が存在しない"})
        else:
            txt = ac.inner_text().strip()
            if len(txt) == 0:
                bugs.append({"tab": tab, "bug": "#analytics-content が空"})
                print(f"    ❌ #analytics-content 空")

    elif tab == "memories":
        # 検索フィールド
        inp = page.locator("input[type='text'], input[type='search'], input[placeholder]")
        print(f"    入力フィールド: {inp.count()} 個")

        # メモリカード or 空状態
        cards = page.locator(".memory-card, .glass-card, [class*='memory']")
        print(f"    メモリカード候補: {cards.count()} 個")

    elif tab == "graph":
        # vis-network コンテナ
        container = page.locator("#graph-container, #knowledge-graph, canvas")
        print(f"    グラフコンテナ候補: {container.count()} 個")
        if container.count() == 0:
            bugs.append({"tab": tab, "bug": "グラフコンテナが存在しない（vis-network未描画）"})

    elif tab == "overview":
        # 統計カード
        stats = page.locator(".stat-card, .glass, [class*='stat']")
        print(f"    統計カード候補: {stats.count()} 個")

    elif tab == "settings":
        # 入力フィールドかボタン
        inputs = page.locator("input, button, select")
        print(f"    フォーム要素: {inputs.count()} 個")

    elif tab == "admin":
        # ボタン
        btns = page.locator("button")
        print(f"    ボタン: {btns.count()} 個")

    elif tab == "personas":
        cards = page.locator(".persona-card, .glass, [class*='persona']")
        print(f"    ペルソナカード候補: {cards.count()} 個")

    elif tab == "import-export":
        btns = page.locator("button")
        print(f"    ボタン: {btns.count()} 個")


if __name__ == "__main__":
    run_investigation()
