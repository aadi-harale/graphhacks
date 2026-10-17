"""Record a REAL local FalkorDB/MCP/model investigation in a Playwright video.

Requires a configured local OPENAI_API_KEY, Docker app and Playwright Chromium.
Usage: python -m scripts.record_real_judge
Fails closed if no real model trace. Video is SILENT, add narration later.
No browser-side fake responses are installed.
"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

URL=os.getenv("SAHIAAYA_UI_URL","http://127.0.0.1:8000/")
DEST=Path(os.getenv("SAHIAAYA_RECORD_DIR","recordings"))
DEST.mkdir(parents=True,exist_ok=True)

def main():
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        context=browser.new_context(viewport={"width":1440,"height":900},
                                    device_scale_factor=1,
                                    record_video_dir=str(DEST),
                                    record_video_size={"width":1440,"height":900},
                                    reduced_motion="reduce")
        page=context.new_page()
        errors=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        try:
            page.goto(URL,wait_until="domcontentloaded")
            expect(page.locator("#modeText")).to_contain_text("LIVE FALKORDB",timeout=15000)
            expect(page.locator("#simpleCheck")).to_be_visible()
            page.wait_for_timeout(1200)
            page.locator("#simpleCheck").click()
            expect(page.locator("#simpleMissingAmount")).to_have_text("2 still owed")
            page.wait_for_timeout(1250)
            page.locator("#simpleTryOwn").click()
            expect(page.locator("#newCase")).to_be_visible()
            page.locator("#newBilled").fill("50")
            page.locator("#newActual").fill("48")
            page.locator("#newReceiptTwo").fill("2")
            page.locator("#caseSubmit").click()
            expect(page.locator("#caseWorkbench")).to_be_visible(timeout=25000)
            expect(page.locator("#caseDecisionStatus")).to_have_text("ASK SUPPLIER")
            case_id=page.locator("#resumeCaseId").input_value()
            if not case_id.startswith("retailer_"):
                raise RuntimeError("Fresh case import not verified")
            page.screenshot(path=str(DEST/"01_new_case.png"),full_page=False)
            page.wait_for_timeout(1200)
            page.locator("#agentRun").click()
            expect(page.locator("#agentResult")).to_contain_text(
                "Real configured model + MCP",timeout=180000)
            expect(page.locator("#agentTransport")).to_contain_text("MCP stdio")
            expect(page.locator("#agentTrace .agent-trace-item").first).to_be_visible()
            expect(page.locator("#agentEvidencePaths .agent-evidence-row")).to_have_count(2)
            page.locator("#agentWorkbench").scroll_into_view_if_needed()
            page.wait_for_timeout(1500)
            page.screenshot(path=str(DEST/"02_real_agent.png"),full_page=False)
            page.locator("#agentEvidencePaths .agent-evidence-node").first.click()
            expect(page.locator("#agentNodeDetail")).to_contain_text("Receipt")
            page.locator("#agentTrace .agent-trace-item details").first.locator("summary").click()
            page.wait_for_timeout(1500)
            page.screenshot(path=str(DEST/"03_mcp_provenance.png"),full_page=False)
            page.locator("#agentTrace .agent-trace-item details").first.locator("summary").click()
            # Human confirmation deliberately separate from the agent.
            page.locator("#caseTarget").select_option("PROMO_OLD")
            page.locator("#caseAttribute").click()
            expect(page.locator("#caseDecisionStatus")).to_have_text("REVIEW SETTLEMENT")
            page.wait_for_timeout(800)
            page.locator("#caseApprove").click()
            expect(page.locator("#caseAudit")).to_contain_text("2 units")
            expect(page.locator("#caseDecisionStatus")).to_have_text("ALREADY ALLOCATED")
            page.screenshot(path=str(DEST/"04_retailer_approved.png"),full_page=False)
            if errors:
                raise RuntimeError("Browser errors: "+repr(errors))
            page.wait_for_timeout(1200)
            print("PASS: real graph, model, MCP trace, human-reviewed allocation",
                  "case:",case_id,"recording:",DEST)
        finally:
            video=page.video
            page.close()
            context.close()
            if video is not None:
                video.save_as(str(DEST/"sahiaaya_live_real_model.webm"))
            browser.close()

if __name__=="__main__":
    main()
