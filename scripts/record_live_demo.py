from playwright.sync_api import sync_playwright
import pathlib, shutil

OUT = pathlib.Path("rec"); shutil.rmtree(OUT, ignore_errors=True); OUT.mkdir()
URL = "https://sahiaaya-graphhacks.vercel.app/"

def glide(pg, sel):
    """Move the mouse to an element so the click is visible, then click."""
    el = pg.locator(sel).first
    el.scroll_into_view_if_needed()
    pg.wait_for_timeout(400)
    b = el.bounding_box()
    pg.mouse.move(b["x"]+b["width"]/2, b["y"]+b["height"]/2, steps=25)
    pg.wait_for_timeout(500)
    el.click()

with sync_playwright() as p:
    b = p.chromium.launch(args=["--force-color-profile=srgb","--hide-scrollbars"])
    ctx = b.new_context(viewport={"width":1280,"height":720},
                        record_video_dir=str(OUT), record_video_size={"width":1920,"height":1080})
    pg = ctx.new_page()
    pg.goto(URL, wait_until="networkidle"); pg.wait_for_timeout(2500)

    # open the demo area
    if not pg.is_visible("#demoForced"):
        for sel in ("#simpleTryOwn", "text=Enter your own case"):
            try:
                glide(pg, sel); pg.wait_for_timeout(1200); break
            except Exception: pass

    pg.locator("#ledgerPanel").scroll_into_view_if_needed(); pg.wait_for_timeout(1200)

    # --- FORCED demo ---
    glide(pg, "#demoForced")
    pg.wait_for_function("document.querySelector('#ledgerEngine').textContent.includes('LIVE')", timeout=60000)
    pg.wait_for_timeout(600)
    pg.locator("#ledgerPanel").scroll_into_view_if_needed()
    pg.wait_for_timeout(5000)                       # let viewers read 4 / 4 / 4 / 0
    print("forced:", pg.inner_text("#ledgerEngine"), [pg.inner_text(x) for x in ("#ledgerOwed","#ledgerMax","#ledgerForced","#ledgerAmb")])

    # approve the first forced proposal
    glide(pg, "#ledgerProposals button")
    pg.wait_for_timeout(6000)
    print("after approve:", pg.inner_text("#ledgerClaims").replace("\n"," | ")[:160])
    pg.wait_for_timeout(2500)

    # --- AMBIGUOUS demo ---
    glide(pg, "#demoAmbiguous")
    pg.wait_for_timeout(9000)
    pg.locator("#ledgerPanel").scroll_into_view_if_needed()
    pg.wait_for_timeout(5000)                       # let viewers read the question
    print("ambiguous:", pg.inner_text("#ledgerForced"), pg.inner_text("#ledgerAmb"), pg.inner_text("#ledgerQuestion")[:90])

    ctx.close(); b.close()
print("video:", [f.name for f in OUT.iterdir()])
