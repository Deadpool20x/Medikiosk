"""Drive P01 -> P03 and capture screenshots at 4 breakpoints via Playwright sync API."""
import os, sys, time, json
from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"
OUT = r"D:\project\Medikishok\frontend\.next\p03-screens"
WIDTHS = [1440, 1024, 768, 390]

os.makedirs(OUT, exist_ok=True)


def go_through_p03(page):
    # P01
    page.goto(f"{BASE}/")
    page.wait_for_selector("button:has-text('English')", timeout=15000)
    page.click("button:has-text('English')")
    page.click("button:has-text('New Patient')")
    page.click("button:has-text('Continue to Consent')")
    # Patient welcome form
    page.wait_for_selector("input[placeholder='Enter your name']", timeout=15000)
    page.fill("input[placeholder='Enter your name']", "Screenshot User")
    page.fill("input[placeholder='Enter your age']", "42")
    page.click("button:has-text('Male')")
    page.click("button:has-text('Start Now')")
    # P02 Consent
    page.wait_for_selector("#consent-agreement", timeout=15000)
    page.check("#consent-agreement")
    page.click("button:has-text('Agree & Continue')")
    # P03 Patient code
    page.wait_for_selector(".mk-p03-code", timeout=15000)
    # Wait until the code text is no longer the placeholder
    page.wait_for_function(
        "() => { const el = document.querySelector('.mk-p03-code'); return el && el.textContent && el.textContent.trim() !== 'Generating…'; }",
        timeout=15000,
    )


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for w in WIDTHS:
            ctx = browser.new_context(viewport={"width": w, "height": 1200})
            page = ctx.new_page()
            try:
                go_through_p03(page)
            except Exception as e:
                print(f"[{w}] error during flow: {e}", file=sys.stderr)
            page.wait_for_timeout(500)
            shot = page.screenshot(full_page=True, path=os.path.join(OUT, f"p03-{w}.png"))
            print(f"[{w}] saved", shot)
            ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
