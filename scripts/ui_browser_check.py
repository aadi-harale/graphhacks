"""Check the KaamSabha-style 3-step flow on real browser and live graph.

The public preview is synthetic; the Docker test exercises the actual
FalkorDB-backed supplier response, guarded allocation and case storage.
"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

URL=os.getenv("SAHIAAYA_UI_URL","http://127.0.0.1:8765/index.html")
EXPECT_GRAPH=os.getenv("SAHIAAYA_EXPECT_BACKEND")=="falkordb"

def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(channel="chrome",headless=True)
        page=browser.new_page(viewport={"width":1365,"height":880},reduced_motion="reduce")
        errors=[]
        page.on("pageerror",lambda error: errors.append(str(error)))
        page.goto(URL,wait_until="domcontentloaded")
        expect(page.locator(".simple-intro h1")).to_contain_text("your supplier owes")
        expect(page.locator("#simpleCheck")).to_be_visible()
        expect(page.locator("#simpleBilled")).to_have_value("50")
        expect(page.locator("#simpleCounted")).to_have_value("48")
        expect(page.locator("#simpleHeading")).to_contain_text("check your delivery")
        expect(page.locator("#workspaceDetails")).not_to_have_attribute("open","")
        expect(page.locator("#newCase")).to_be_hidden()
        expect(page.locator("#simpleHistory")).to_be_hidden()
        if EXPECT_GRAPH:
            expect(page.locator("#modeText")).to_contain_text("LIVE FALKORDB")
        else:
            expect(page.locator("#modeText")).to_contain_text("PUBLIC SYNTHETIC SIMULATION")

        Path("docs/screenshots").mkdir(parents=True,exist_ok=True)
        page.screenshot(path="docs/screenshots/judge-live-desktop.png" if EXPECT_GRAPH else "docs/screenshots/judge-desktop.png",full_page=True)

        # Change quantities: show the user's own computed shortage, not fixed text.
        page.locator("#simpleCounted").fill("47")
        page.locator("#simpleCheck").click()
        expect(page.locator("#simpleHeading")).to_contain_text("3 soaps missing")
        expect(page.locator("#simpleMissingAmount")).to_have_text("3 still owed")
        page.locator("#simpleRestart").click()
        page.locator("#simpleCounted").fill("48")
        page.locator("#simpleCheck").click()
        expect(page.locator("#simpleHeading")).to_contain_text("2 soaps missing")
        expect(page.locator("#simpleNext")).to_be_visible()

        # Follow the earlier shortage into a connected later receipt.
        page.locator("#simpleNext").click()
        expect(page.locator("#simpleHeading")).to_contain_text("Two more soaps arrived")
        expect(page.locator("#simpleChoices")).to_be_visible()
        expect(page.locator("#simpleHistory")).to_be_visible()
        expect(page.locator("#simpleHistory")).to_contain_text("Old invoice")
        expect(page.locator("#simpleBalanceShort")).to_have_text("2 still owed")
        page.screenshot(path="docs/screenshots/judge-live-followup.png" if EXPECT_GRAPH else "docs/screenshots/judge-followup.png",full_page=True)

        # A supplier statement supports a PROPOSAL, never automatic closure.
        page.locator("#simpleChoosePromo").click()
        expect(page.locator("#simpleHeading")).to_contain_text("free soaps")
        expect(page.locator("#simpleBalancePromo")).to_have_text("2 still owed")
        expect(page.locator("#simpleNext")).to_be_visible()
        if EXPECT_GRAPH:
            expect(page.locator("#raw")).to_contain_text("falkordb.Q_OBLIGATIONS")
        page.locator("#simpleNext").click()
        expect(page.locator("#simpleHeading")).to_have_text("Free soaps recorded.")
        expect(page.locator("#simpleBalancePromo")).to_have_text("Settled ✓")
        expect(page.locator("#simpleBalanceShort")).to_have_text("2 still owed")
        expect(page.locator("#audit li")).to_have_count(1)
        page.screenshot(path="docs/screenshots/judge-live-outcome.png" if EXPECT_GRAPH else "docs/screenshots/judge-outcome.png",full_page=True)

        # Negative control: contradiction cannot silently settle anything.
        page.locator("#simpleRestart").click()
        page.locator("#simpleCheck").click()
        page.locator("#simpleNext").click()
        page.locator("#simpleChooseConflict").click()
        expect(page.locator("#simpleHeading")).to_have_text("Don't settle yet.")
        expect(page.locator("#simpleBalanceShort")).to_have_text("2 still owed")
        expect(page.locator("#simpleBalancePromo")).to_have_text("2 still owed")
        expect(page.locator("#simpleNext")).to_be_hidden()

        # Advanced workspace is intentional, optional and functional.
        page.locator("#simpleTryOwn").click()
        expect(page.locator("#workspaceDetails")).to_have_attribute("open","")
        expect(page.locator("#newCaseDetails")).to_have_attribute("open","")
        if EXPECT_GRAPH:
            page.locator("#newActual").fill("5")
            page.locator("#newReceiptTwo").fill("2")
            page.locator("#caseSubmit").click()
            expect(page.locator("#caseWorkbench")).to_be_visible()
            expect(page.locator("#caseDecisionStatus")).to_have_text("ASK SUPPLIER")
            expect(page.locator("#agentRun")).to_be_visible()
            page.locator("#agentRun").click()
            expect(page.locator("#agentResult")).to_contain_text("Agent unavailable")
            expect(page.locator("#agentResult")).to_contain_text("OPENAI_API_KEY")
            expect(page.locator("#caseClaims .claim-row")).to_have_count(2)
            case_id=page.locator("#resumeCaseId").input_value()
            assert case_id.startswith("retailer_")
            page.locator("#caseTarget").select_option("PROMO_OLD")
            page.locator("#caseAttribute").click()
            expect(page.locator("#caseDecisionStatus")).to_have_text("REVIEW SETTLEMENT")
            page.locator("#caseApprove").click()
            expect(page.locator("#caseAudit")).to_contain_text("2 units")
            expect(page.locator("#caseDecisionStatus")).to_have_text("ALREADY ALLOCATED")
            page.reload(wait_until="domcontentloaded")
            expect(page.locator("#modeText")).to_contain_text("LIVE FALKORDB")
            page.locator("#simpleTryOwn").click()
            page.locator("#resumeCaseId").fill(case_id)
            page.locator("#resumeCaseButton").click()
            expect(page.locator("#caseAudit")).to_contain_text("2 units")
            page.locator("#caseReceiptSelect").select_option("LATER_A")
            expect(page.locator("#caseDecisionStatus")).to_have_text("ASK SUPPLIER")
            page.locator("#newHistoryFile").set_input_files("examples/fictional_second_supplier_case.json")
            page.locator("#caseSubmit").click()
            expect(page.locator("#caseWorkbench")).to_be_visible()
            expect(page.locator("#caseClaims")).to_contain_text("SHORT_R1")
            expect(page.locator("#caseClaims")).to_contain_text("PROMO_INVALID")
            expect(page.locator("#caseClaims")).to_contain_text("scheme not eligible")
        assert not errors, "JavaScript page errors: "+repr(errors)
        page.close()

        mobile=browser.new_page(viewport={"width":390,"height":844},device_scale_factor=1,is_mobile=True,has_touch=True,reduced_motion="reduce")
        mobile.goto(URL,wait_until="domcontentloaded")
        expect(mobile.locator(".simple-intro h1")).to_be_visible()
        expect(mobile.locator("#simpleBilled")).to_be_visible()
        expect(mobile.locator("#simpleCheck")).to_be_visible()
        expect(mobile.locator("#workspaceDetails")).not_to_have_attribute("open","")
        mobile.locator("#simpleCheck").click()
        expect(mobile.locator("#simpleMissingAmount")).to_have_text("2 still owed")
        assert mobile.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2"),"Mobile page overflows horizontally"
        mobile.screenshot(path="docs/screenshots/judge-live-mobile.png" if EXPECT_GRAPH else "docs/screenshots/judge-mobile.png",full_page=True)
        mobile.close()
        browser.close()
        print("PASS:",("live FalkorDB" if EXPECT_GRAPH else "synthetic"),"easy receiving → follow-up → reviewed resolution; mobile layout")

if __name__=="__main__":
    main()
