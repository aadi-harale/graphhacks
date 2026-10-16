"""End-to-end synthetic judge walkthrough, run against a static local server.

This verifies browser interactions, not the separate live FalkorDB API.
Requires Python Playwright and Chrome on the runner.
"""
from pathlib import Path
import os
from playwright.sync_api import sync_playwright, expect

URL = os.getenv("SAHIAAYA_UI_URL", "http://127.0.0.1:8765/index.html")
EXPECT_GRAPH = os.getenv("SAHIAAYA_EXPECT_BACKEND") == "falkordb"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1365, "height": 880}, reduced_motion="reduce")
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(URL, wait_until="domcontentloaded")

        expect(page.locator("#heroStart")).to_be_visible()
        if EXPECT_GRAPH:
            expect(page.locator("#modeText")).to_contain_text("LIVE FALKORDB")
            expect(page.locator("#graphStamp")).to_have_text("GRAPH QUERY CONTEXT")
        else:
            expect(page.locator("#modeText")).to_contain_text("PUBLIC SYNTHETIC SIMULATION")
        expect(page.locator("#journeyConnect")).to_contain_text("Find old promises")
        expect(page.locator("#graphSteps .graph-step")).to_have_count(4)
        expect(page.locator("#status")).to_have_text("ASK SUPPLIER")
        expect(page.locator("#settledUnits")).to_have_text("0")

        page.locator("#heroStart").click()
        expect(page.locator("#tourPhase")).to_contain_text("STEP 1 OF 4")
        expect(page.locator("#status")).to_have_text("ASK SUPPLIER")

        page.locator("#tourNext").click()
        expect(page.locator("#tourPhase")).to_contain_text("STEP 2 OF 4")
        expect(page.locator("#status")).to_have_text("REVIEW SETTLEMENT")
        if EXPECT_GRAPH:
            expect(page.locator("#raw")).to_contain_text("falkordb.Q_OBLIGATIONS")
        expect(page.locator("#settledUnits")).to_have_text("0")

        page.locator("#tourNext").click()
        expect(page.locator("#tourPhase")).to_contain_text("STEP 3 OF 4")
        expect(page.locator("#settledUnits")).to_have_text("2")
        expect(page.locator("#owedUnits")).to_have_text("2")
        expect(page.locator("#audit li")).to_have_count(1)

        page.locator("#tourNext").click()
        expect(page.locator("#tourPhase")).to_contain_text("STEP 4 OF 4")
        expect(page.locator("#status")).to_have_text("DISPUTE")
        expect(page.locator("#settledUnits")).to_have_text("0")
        expect(page.locator("#owedUnits")).to_have_text("4")
        assert not errors, "JavaScript page errors: " + repr(errors)
        Path("docs/screenshots").mkdir(parents=True, exist_ok=True)
        page.screenshot(path="docs/screenshots/judge-live-desktop.png" if EXPECT_GRAPH else "docs/screenshots/judge-desktop.png", full_page=True)
        page.close()

        mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True, reduced_motion="reduce")
        mobile.goto(URL, wait_until="domcontentloaded")
        expect(mobile.locator("#heroStart")).to_be_visible()
        expect(mobile.locator("#journeyApprove")).to_be_visible()
        assert mobile.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2"), "Mobile page overflows horizontally"
        mobile.screenshot(path="docs/screenshots/judge-live-mobile.png" if EXPECT_GRAPH else "docs/screenshots/judge-mobile.png", full_page=True)
        mobile.close()
        browser.close()
        print("PASS: " + ("live FalkorDB" if EXPECT_GRAPH else "synthetic") + " desktop guided settlement, conflict negative control and mobile layout")

if __name__ == "__main__":
    main()
