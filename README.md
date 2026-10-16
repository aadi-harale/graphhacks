# SahiAaya — EvidenceGap

**Bill vs Box. Promise vs Proof.** A graph-grounded supplier resolution agent for independent Indian retailers, built for Graph Hacks × FalkorDB (Oct 15–18, 2026).

The agent connects historic shortage claims, documented promotions, supplier statements and confirmed receipt evidence, then identifies exactly what needs clarification before any settlement can be reviewed.

## Judge experience and deployment modes (October 16, 2026)

- **Public interactive preview:** https://sahiaaya-graphhacks.vercel.app/ — an isolated browser-side fictional walk-through. **Does not query FalkorDB.** No external supplier communication or payments.
- **Real graph experience:** run the same UI via `docker compose up -d --build` on localhost:8000. The UI detects the FastAPI backend, which traverses actual FalkorDB evidence and stores reviewed synthetic allocations.
- **Live verification:** GitHub Actions runs a FalkorDB service and adversarial graph tests. See the latest [Actions runs](https://github.com/aadi-harale/graphhacks/actions). At the time of this update the conflict guard has passed its live regression. Browser smoke and unknown-history adoption testing remain in progress.
- **Judge demo:** [DEMO_JUDGE_GUIDE.md](DEMO_JUDGE_GUIDE.md) contains the exact three-minute story and truthful limitations.

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
