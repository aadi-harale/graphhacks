"""End-to-end check of the deployed public site: API and real browser clicks."""
import json
import sys
import urllib.request

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "https://sahiaaya-graphhacks.vercel.app"


def note(title, msg, level="notice"):
    print(f"::{level} title={title}::{msg}")


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


ok = True
health = json.loads(urllib.request.urlopen(BASE + "/api/public/health", timeout=30).read())
note("Health", json.dumps(health))
forced = post("/api/public/ledger-demo", {"which": "forced"})
note("API forced", f"engine={forced['engine']} status={forced['status']} max={forced['max_settleable_units']} "
     f"forced={forced['forced_units']} proposals={[(p['receipt_id'], p['claim_id'], p['forced_units']) for p in forced['proposals']]}")
ok &= forced["engine"] == "falkordb.algo.maxFlow" and forced["forced_units"] == 4
p = next(x for x in forced["proposals"] if x["receipt_id"] == "DROP_1")
after = post(f"/api/public/ledger-demo/{forced['case_id']}/approve", {
    "receipt_id": p["receipt_id"], "claim_id": p["claim_id"], "quantity": p["forced_units"],
    "receipt_version": p["receipt_version"], "claim_version": p["claim_version"]})
owed = {o["id"]: o["outstanding_qty"] for o in after["obligations"]}
note("API approve", f"still owed after approving DROP_1: {owed}")
ok &= owed == {"SHORT_JUN": 2, "DIWALI_SCHEME": 0}
amb = post("/api/public/ledger-demo", {"which": "ambiguous"})
note("API ambiguous", f"status={amb['status']} forced={amb['forced_units']} question={amb['supplier_question'][:90]}")
ok &= amb["status"] == "ASK_SUPPLIER" and amb["forced_units"] == 0

from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE + "/", wait_until="networkidle")
    if not page.is_visible("#demoForced"):
        for sel in ("#simpleTryOwn", "text=Enter your own case"):
            try:
                page.click(sel, timeout=3000)
                break
            except Exception:
                pass
    page.click("#demoForced")
    page.wait_for_function("document.querySelector('#ledgerEngine').textContent.includes('LIVE') || document.querySelector('#ledgerEngine').textContent.includes('REPLAY')", timeout=45000)
    tag = page.inner_text("#ledgerEngine")
    stats = [page.inner_text(x) for x in ("#ledgerOwed", "#ledgerMax", "#ledgerForced", "#ledgerAmb")]
    note("Browser forced", f"tag={tag} stats={stats} note={page.inner_text('#ledgerReplayNote')[:120]}")
    ok &= "LIVE" in tag and stats == ["4", "4", "4", "0"]
    page.locator("#ledgerProposals button").first.click()
    page.wait_for_timeout(6000)
    note("Browser approve", page.inner_text("#ledgerClaims").replace("\n", " | ")[:200])
    page.click("#demoAmbiguous")
    page.wait_for_timeout(8000)
    note("Browser ambiguous", f"forced={page.inner_text('#ledgerForced')} amb={page.inner_text('#ledgerAmb')} q={page.inner_text('#ledgerQuestion')[:80]}")
    page.locator("#ledgerPanel").screenshot(path="live_panel.png")
    note("Page errors", str(errors[:3]))
    b.close()

note("Result", "PASS" if ok else "FAIL", "notice" if ok else "error")
sys.exit(0 if ok else 1)
