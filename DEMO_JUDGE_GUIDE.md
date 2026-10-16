# SahiAaya — Three-minute judge demonstration

## One problem, one investigation, one action, one checked outcome

**Opening line:** A shopkeeper receives two soap units. His supplier already owed two units as an old shortage and two units as a promotional entitlement. The new invoice looks fine. Which promise did this box fulfil?

| Timing | Action on screen | What the judge should understand |
| --- | --- | --- |
| 0:00–0:25 | Three-step story and today's inward receipt | Not all errors are inside one invoice. |
| 0:25–0:55 | Unattributed delivery | Two obligations match. System holds instead of making up a settlement. |
| 0:55–1:30 | Simulated supplier selects PROMO-17 with a reference | Connected historical evidence changes the proposed action. |
| 1:30–1:55 | Retailer approves the proposal | Exactly two units settle PROMO-17. SHORT-41 remains open. |
| 1:55–2:20 | Reset and choose conflicting statements | Same counts but contradictory provenance block the action. |
| 2:20–2:45 | Show replacement-confirmed variant | Identical receipt quantities lead to a different outcome. |
| 2:45–3:00 | Open evidence trail, show actual Cypher query and live tests | Demonstrate the sponsor graph drives the actual backend. |

## Two distinct deployment modes — don't mix them up

**Vercel public page:** Safe browser-local fictional scenario simulator. It is intentionally NOT a live FalkorDB instance and cannot prove the hackathon graph requirement alone.

**Local Docker app:** Same page served by FastAPI with FalkorDB container. Browser detects the real backend via /api/health; investigations call Cypher, supplier confirmations write graph evidence, retailer approval commits reviewed allocations. The local demo has no user authentication, so only expose ports on 127.0.0.1.

Use the Docker version, with real green FalkorDB integration tests, for the submission video. Use Vercel as an easy-to-explore preview for judges.

## Research-informed choices

- October 7, 2026 First Commit winner recap: Suraksha solved an ordinary-person safety need; Beacon Night Shift demonstrated investigate → propose → approve → verify; CampusEvac made two human roles consequential. https://www.wemakedevs.org/blogs/first-commit-hackathon-recap-and-whats-next
- August 18, 2026 FalkorDB standout recap: Atrium's graph changes the next teaching action; Drift couples changed evidence to a governed downstream action. https://www.falkordb.com/blog/memory-meets-motion-the-falkordb-standouts/
- DisburseProof source: https://github.com/aadi-harale/disburseproof. Its strong failure-versus-protection experiment demonstrates how to make one property memorable. Its published README explicitly limits the experiment to its own built-in synthetic processor, not external beneficiary systems. We avoid the same adoption overclaim for SahiAaya.

**Pending:** The user has said they will share actual judge comments on DisburseProof, but those comments have not been provided yet. Do not invent them.

## Questions to anticipate

**Is this just OCR?** No. OCR is optional input convenience. Historical obligation evidence is the product.

**Can SQL achieve the same decisions?** Yes. The current SQLite baseline with equivalent facts returns the same decisions. We do not claim exclusivity. FalkorDB is the decision-critical graph backend in our submitted implementation.

**Can a supplier response alone settle a claim?** No. Attributable statement plus confirmed receipt plus retailer-reviewed allocation are required.

**Is money recovered?** No real money moves. A simulated settlement is not a recovered credit.

**Is the public URL live FalkorDB?** No; the status badge and README explicitly disclose browser simulation.

## Work still required

1. CI green on latest commit; include actual FalkorDB container integration test evidence.
2. Run Docker app and verify the same UI presents LIVE FALKORDB.
3. Test unknown synthetic histories, not only fixed preset screens.
4. Verify public URL loads for a logged-out browser and on mobile.
5. Record the live graph demo, not just the public simulation.
