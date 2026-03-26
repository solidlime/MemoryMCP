"""Verify all bug fixes: modal, tooltip HTML, persona emoji, skeleton tabs"""
import asyncio
from playwright.async_api import async_playwright

URL = "http://nas:26262"
PASS = "\u2705"
FAIL = "\u274c"

async def main():
    results = []

    async with async_playwright() as p:
        br = await p.chromium.launch()
        pg = await br.new_page()
        js_errors = []
        pg.on("console", lambda m: js_errors.append(m.text) if m.type == "error" and "tailwind" not in m.text else None)

        await pg.goto(URL)
        await pg.wait_for_timeout(1000)
        await pg.select_option("#persona-select", "herta")
        await pg.wait_for_timeout(2000)

        # ── 1. Memory modal ────────────────────────────────────────────
        await pg.click("[data-tab=memories]")
        await pg.wait_for_timeout(2000)
        cards = await pg.query_selector_all("[data-memjson]")
        if cards:
            await cards[0].click()
            await pg.wait_for_timeout(500)
            overlay = await pg.query_selector("#mem-modal-overlay")
            has_show = await overlay.evaluate("el => el.classList.contains('show')") if overlay else False
            display  = await overlay.evaluate("el => el.style.display") if overlay else "none"
            ok = has_show and display == "flex"
            results.append((ok, "Memory modal visible on card click"))
            # close
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(300)
        else:
            results.append((False, "Memory modal — no cards found"))

        # ── 2. Graph tab loads (showSkeleton fix) ─────────────────────
        await pg.click("[data-tab=graph]")
        await pg.wait_for_timeout(3000)
        container = await pg.query_selector("#graph-container")
        results.append((container is not None, "Graph #graph-container preserved after skeleton"))

        # ── 3. Graph tooltip returns DOM element (no raw HTML) ─────────
        await pg.screenshot(path="tests/e2e/screenshots/investigation/verify_graph_tooltip.png")
        # Hover over first visible node via JS evaluation
        tooltip_ok = await pg.evaluate("""() => {
            if (typeof buildTooltip === 'undefined') return 'no buildTooltip fn';
            var fakeNode = {content:'Test content', tags:['tag1'], emotion_type:'joy', importance:0.8};
            var result = buildTooltip(fakeNode);
            return (result instanceof HTMLElement) ? 'DOM_ELEMENT' : ('STRING:' + typeof result);
        }""")
        results.append((tooltip_ok == "DOM_ELEMENT", f"Graph buildTooltip returns DOM element ({tooltip_ok})"))

        # ── 4. Personas tab loads + emoji ─────────────────────────────
        await pg.click("[data-tab=personas]")
        await pg.wait_for_timeout(2000)
        persona_html = await pg.inner_html("#persona-grid") if await pg.query_selector("#persona-grid") else ""
        grid_ok = len(persona_html) > 100
        results.append((grid_ok, "Personas #persona-grid has content"))

        # Check no raw \\U escape codes in rendered HTML
        has_bad_escape = "\\U0001f" in persona_html or "U0001f" in persona_html
        results.append((not has_bad_escape, "Persona emoji rendered correctly (no \\U0001f in HTML)"))
        # Check actual emoji appear
        has_emoji = any(c in persona_html for c in ["👤","📝","💭","🔄","🗑","😊","😐"])
        results.append((has_emoji, "Persona emoji characters present in HTML"))

        # ── 5. Import-Export loads ─────────────────────────────────────
        await pg.click("[data-tab=import-export]")
        await pg.wait_for_timeout(2000)
        ie_content = await pg.inner_html("#import-export-content") if await pg.query_selector("#import-export-content") else ""
        results.append((len(ie_content) > 200, "Import-Export #import-export-content has content"))

        # ── 6. No JS errors ────────────────────────────────────────────
        results.append((len(js_errors) == 0, f"No JS errors ({len(js_errors)} found: {js_errors[:2]})"))

        await pg.screenshot(path="tests/e2e/screenshots/investigation/verify_all_final.png")
        await br.close()

    print("\n" + "="*60)
    print("VERIFICATION RESULTS")
    print("="*60)
    all_pass = True
    for ok, msg in results:
        icon = PASS if ok else FAIL
        print(f"  {icon} {msg}")
        if not ok:
            all_pass = False
    print("="*60)
    print(f"\n{'ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED'}")
    return all_pass

if __name__ == "__main__":
    asyncio.run(main())
