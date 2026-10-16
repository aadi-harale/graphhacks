# SahiAaya — EvidenceGap

**Bill vs Box. Promise vs Proof.** A graph-grounded supplier resolution agent for independent Indian retailers, built for Graph Hacks × FalkorDB (Oct 15–18, 2026).

The agent connects historic shortage claims, documented promotions, supplier statements and confirmed receipt evidence, then identifies exactly what needs clarification before any settlement can be reviewed.

## Judge experience and deployment modes (October 16, 2026)

- **Public interactive preview:** https://sahiaaya-graphhacks.vercel.app/ — an isolated browser-side fictional walk-through. **Does not query FalkorDB.** No external supplier communication or payments.
- **Real graph experience:** run the same UI via `docker compose up -d --build` on localhost:8000. The UI detects the FastAPI backend, which traverses actual FalkorDB evidence and stores reviewed synthetic allocations.
- **Live verification:** GitHub Actions runs a FalkorDB service and adversarial graph tests. See the latest [Actions runs](https://github.com/aadi-harale/graphhacks/actions). At the time of this update the conflict guard has passed its live regression. Browser smoke and unknown-history adoption testing remain in progress.
- **Judge demo:** [DEMO_JUDGE_GUIDE.md](DEMO_JUDGE_GUIDE.md) contains the exact three-minute story and truthful limitations.

## Judge-first home screen (October 16)

The public first screen now answers only three questions: **Who?** A small shopkeeper. **What went wrong?** Two missing soaps and two promised free soaps are still due; only two arrived. **What does SahiAaya do?** It checks the supplier history before claiming a promise is fulfilled.

The single primary button opens the guided proof → supplier response → retailer review story. Contradictory evidence, new-case import, Cypher traces and audit history remain available in clearly labeled optional disclosures. They are not hidden from reviewers; they are simply not mandatory reading on first visit. The public Vercel demonstration remains client-side and fictional; local Docker runs FalkorDB.

## First look: understand the whole product in 60 seconds

The interface now opens with the **retailer's real question**: two units arrived, but there are two different older promises for four units total. Click **See SahiAaya solve this →** to follow:

1. **Receive** — observe and confirm the goods.
2. **Connect** — recover earlier shortage and promotion obligations.
3. **Ask** — use the actual simulated supplier-response operation to attribute this receipt.
4. **Approve** — let the retailer review the suggested allocation; record two units settled and two still owed, or block the action if statements conflict.

The evidence chain below the interactive case shows how connected documents, the receipt, a supplier statement and retailer approval affect the final verdict. The public page is explicitly **a synthetic, client-only walkthrough**; Docker runs the same interface with actual FalkorDB Cypher queries. A real FalkorDB-backed browser video remains a distinct submission requirement.

**Reproducible browser checks:** `scripts/ui_browser_check.py` runs desktop and 390-pixel mobile Playwright checks in GitHub Actions. It covers the guided positive case, contradiction negative control and horizontal mobile overflow. Screenshots are attached as the `sahiaaya-browser-screenshots` Actions artifact.

**Design reference evidence:** the [October 7 First Commit recap](https://www.wemakedevs.org/blogs/first-commit-hackathon-recap-and-whats-next) credits Suraksha's clear human need, Beacon's approved response and CampusEvac's two-player coordination; [FalkorDB's August 18 recap](https://www.falkordb.com/blog/memory-meets-motion-the-falkordb-standouts/) describes Atrium's connected evidence changing a teaching action. The [September 30 Hack for Humanity recap](https://www.falkordb.com/blog/how-builders-at-hack-for-humanity-used-falkordb-to-solve-real-community-problems/) documents accessible input/output with evidence-backed graph decisions. We applied these **product-interaction lessons**, not an unverified claim about their visual aesthetics.

## New: enter an unfamiliar fictional delivery history

**The application is no longer limited to the fixed RCP-52 walkthrough.** In the local Docker app, scroll to **Try your own delivery history**, enter a supplier/SKU, the earlier **billed** and **actually received** counts, a documented promotional entitlement, and quantities for two later deliveries—or upload a separate *fictional* JSON fixture.

This creates new FalkorDB nodes and candidate relationships and lets you investigate, attribute and review quantities for either receipt. Promotions are eligible only if their recorded date and purchase threshold are satisfied; invalid terms are shown as excluded, not silently accepted. Duplicate case IDs with different content are rejected.

**Persistence safeguard:** the preset guided demo operates in the resettable graph \`sahiaaya_proof\`; imported histories live in the separate \`sahiaaya_resolve\` graph. Refresh the page, enter the generated case ID under **Reopen graph case**, and verify that reviewed allocations remain present even if the preset demo was reset.

Try \`examples/fictional_second_supplier_case.json\` for a second supplier with an expired promotional scheme. See [docs/NEW_CASE_WORKFLOW.md](docs/NEW_CASE_WORKFLOW.md) for the data format, endpoints, trust assumptions and exact demonstration.

**Limits:** These are typed, explicitly synthetic receipts and scheme terms—not independently authenticated real invoices. This local demo has no production identity, supplier messaging, real payments or security model for public mutation endpoints. The [Vercel preview](https://sahiaaya-graphhacks.vercel.app/) intentionally disables the new-case writer because it does not host FalkorDB.

## The demonstrated user problem

A retailer is owed two replacement units from a short delivery, plus two promotional units. Two units arrive. Either obligation could plausibly match, but the supplier hasn't identified the purpose.

SahiAaya asks for the precise missing attribution instead of double-counting the goods or inventing a recovery. After a **simulated** supplier response and explicit **demo** retailer approval, it allocates only the supported quantity, leaves other obligations open and records the review evidence.

This does **not** prove what happened in the physical world. Quantities, invoice documents and supplier replies in this repo are entirely fictional.

## Run on Windows (Docker Desktop)

```powershell
git clone https://github.com/aadi-harale/graphhacks.git
cd graphhacks
docker compose up -d --build
```

Open **http://localhost:8000**. The case loads automatically. Select **Unattributed delivery**, **Promotion proof**, or **Conflicting statements** to inspect how evidence changes the agent's action. The API refuses to serve a fabricated graph answer when FalkorDB is unreachable.

Run all tests, including **live** graph integration:

```powershell
docker compose exec app pytest -q
docker compose exec -e RUN_FALKOR_TESTS=1 app pytest tests/test_falkor_integration.py -v
```

Inspect local logs with `docker compose logs -f app falkordb`. Stop with `docker compose down`.

## Graph model and actual Cypher role

- `(:Receipt)-[:FROM_SUPPLIER]->(:Supplier)` and `(:Receipt)-[:FOR_SKU]->(:SKU)`
- `(:Obligation)-[:OWED_BY]->(:Supplier)` and `(:Obligation)-[:FOR_SKU]->(:SKU)`
- `(:Obligation)-[:AROSE_FROM]->(:SourceRecord)-[:SUPPORTED_BY]->(:Document)`
- `(:Promise)-[:PROMISED_FOR]->(:Obligation)`, with the promise linked to its evidence document
- `(:Statement)-[:ABOUT_RECEIPT]->(:Receipt)` and `(:Statement)-[:SUPPORTED_BY]->(:Document)`
- `(:Allocation)-[:USES_RECEIPT]->(:Receipt)`, `(:Allocation)-[:SETTLES]->(:Obligation)`, `(:RetailerApproval)-[:APPROVES]->(:Allocation)`

The core graph queries in `app/graph.py` resolve which obligations share the receipt's supplier and SKU, traverse historical sources and promises, inspect attributable supplier statements, and atomically attempt a version-checked reviewed allocation. The deterministic agent in `app/agent.py` must read the graph-fetched context to select its next action.

## Agent contract

Inputs: synthetic confirmed receipt, eligible obligations, historic source documents, supplier attribution and review state.

Actions: `ASK_SUPPLIER`, `ASK_RETAILER`, `DISPUTE`, `REVIEW_SETTLEMENT`, `UNKNOWN`, `ALREADY_ALLOCATED`. A model is **not required** in this MVP; the current agent is deterministic and is not an LLM-driven planner. Approval is always separate.

Output: next action, exact evidence request, candidate claim IDs, traversed provenance and reviewed allocation history.

## Endpoints

- `GET /api/health`
- `POST /api/demo/reset` — requires local `ALLOW_DEMO_RESET=1`
- `GET /api/investigate/RCP-52`
- `POST /api/investigate/RCP-52/simulate-supplier-response`
- `POST /api/investigate/RCP-52/approve-demo-settlement`

**These endpoints are unauthenticated. Do not expose on the public internet.**

## Tests and honest comparison

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python -m scripts.proof_report
```

The fair SQLite baseline, in `app/baseline.py`, uses the **same** receipt, claims and supplier statements. It is expected to reproduce the same deterministic decisions. A graph database is not uniquely capable of the underlying allocation arithmetic.

Competitive advantage remains **unproven**: we must show connected provenance retrieval reduces manual investigation work on unfamiliar histories, not just that the graph stores data.

See [BUILD_GATES.md](BUILD_GATES.md) for acceptance gates, [SECURITY.md](SECURITY.md) for deployment restrictions, and [CLAUDE.md](CLAUDE.md) for evidence-first engineering practice.

## AI use and source disclosure

AI assistance has been used to draft design, implementation and tests. All decisions and safety claims require developer review and executable validation. Inspiration: original SahiAaya retail receiving pitch, its later receipt-to-resolution refinement, and the official FalkorDB/WeMakeDevs Graph Hacks rules. No real retailer pilot or independently verified financial recovery is claimed.
