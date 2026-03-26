"""Post-fix verification: chart-emotions + memory modal"""
import asyncio
from playwright.async_api import async_playwright

URL = "http://nas:26262"

async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch()
        pg = await br.new_page()
        errors = []
        pg.on("console", lambda m: errors.append(m) if m.type == "error" else None)

        await pg.goto(URL)
        await pg.wait_for_timeout(1000)
        await pg.select_option("#persona-select", "herta")
        await pg.wait_for_timeout(2000)

        # --- Analytics ---
        await pg.click("[data-tab=analytics]")
        await pg.wait_for_timeout(3000)
        html = await pg.inner_html("#tab-analytics")
        has_emotions_canvas = await pg.query_selector("#chart-emotions")
        emotions_div = await pg.query_selector("[id^=chart-emotions-nodata], .no-data")
        print("=== Analytics ===")
        print(f"  #chart-emotions canvas: {'FOUND' if has_emotions_canvas else 'NOT FOUND'}")
        # check for no-data placeholder
        snippets = [s for s in html.split("<") if "emotion" in s.lower() or "no" in s.lower() and "data" in s.lower()]
        print(f"  emotion-related HTML: {snippets[:3]}")
        print(f"  HTML length: {len(html)}")

        # --- Memory modal ---
        await pg.click("[data-tab=memories]")
        await pg.wait_for_timeout(2000)
        cards = await pg.query_selector_all("[data-memjson]")
        print(f"\n=== Memories ===")
        print(f"  Cards found: {len(cards)}")
        if cards:
            await cards[0].click()
            await pg.wait_for_timeout(600)
            overlay = await pg.query_selector("#mem-modal-overlay")
            if overlay:
                display = await overlay.evaluate("el => el.style.display")
                has_show = await overlay.evaluate("el => el.classList.contains('show')")
                modal_html = await overlay.inner_html()
                print(f"  Modal display: {display}")
                print(f"  Modal has 'show' class: {has_show}")
                print(f"  Modal HTML length: {len(modal_html)}")
                if has_show and display == "flex":
                    print("  ✅ Modal VISIBLE — bug FIXED")
                else:
                    print(f"  ❌ Modal NOT visible (display={display}, show={has_show})")
            else:
                print("  ❌ #mem-modal-overlay not in DOM")
        await pg.screenshot(path="tests/e2e/screenshots/investigation/verify_modal.png")

        # --- JS errors ---
        real_errors = [e for e in errors if "tailwind" not in e.text]
        print(f"\n=== JS Errors: {len(real_errors)} ===")
        for e in real_errors:
            print(f"  {e.text}")

        await br.close()

asyncio.run(main())
