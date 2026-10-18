# SahiAaya — EvidenceGap

**Bill vs Box. Promise vs Proof.** A graph-grounded supplier resolution agent for independent Indian retailers, built for Graph Hacks × FalkorDB (Oct 15–18, 2026).

The local application has two separate capabilities: a **deterministic, FalkorDB-backed settlement policy** that checks recorded evidence and a **model-directed investigation path** that can ask bounded graph questions and save an internal follow-up draft. The agent never approves settlements. Live model performance has **not** been verified in this audit.

## Track 01 — Agents That Act on Connected Data

**Prize track: iPhone 18 Pro.** Official rules: https://www.wemakedevs.org/hackathons/falkordb/rules .

A shopkeeper receives fewer items than billed, then faces an ambiguous replacement delivery: was the supplier fulfilling the old shortage or a separate promotion? SahiAaya uses FalkorDB to investigate previous receipts, obligations, source documents and supplier statements, then drafts a precise follow-up. The shopkeeper reviews any eventual allocation.

### Judge experience

- **[Public preview](https://sahiaaya-graphhacks.vercel.app/):** KaamSabha-style **Check delivery → Follow up → Resolve**. A clearly disclosed *browser-only synthetic walkthrough*. This cannot establish live FalkorDB or model operation.
- **Actual Track 01 demo:** `docker compose up -d --build`, open http://localhost:8000, use **Enter your own case** and **Investigate with agent**. When configured with a real model API key, the model may choose bounded function calls; the FastAPI backend invokes the selected tools through an **MCP stdio ClientSession** and retrieves FalkorDB evidence. MCP is the tool **transport**, not the tool-selection algorithm. A locally supplied `OPENAI_API_KEY` is required for real model selection.
- **Explainable, safe output:** graph paths, named MCP tools, authoritative graph-policy verdict, source-referenced follow-up draft, and human-approved settlement. No real supplier is contacted or money moved.
- **Verification:** GitHub Actions tests the actual MCP client/server transport against a live FalkorDB service while simulating model tool choices. That proves transport and guardrails, **not** real-model quality. **No real-key model execution or verified local recording is available yet**. They are mandatory remaining acceptance gates.

**[Track 01 architecture, run instructions and submission gates](docs/TRACK01_IPHONE_AGENT.md)** · **[Full browser and FalkorDB CI](https://github.com/aadi-harale/graphhacks/actions)**

## New: enter an unfamiliar fictional delivery history

**The application is no longer limited to the fixed RCP-52 walkthrough.** In the local Docker app, scroll to **Try your own delivery history**, enter a supplier/SKU, the earlier **billed** and **actually received** counts, a documented promotional entitlement, and quantities for two later deliveries—or upload a separate *fictional* JSON fixture.

This creates new FalkorDB nodes and candidate relationships and lets you investigate, attribute and review quantities for either receipt. Promotions are eligible only if their recorded date and purchase threshold are satisfied; invalid terms are shown as excluded, not silently accepted. Duplicate case IDs with different content are rejected.

**Persistence safeguard:** the preset guided demo operates in the resettable graph `sahiaaya_proof`; imported histories live in the separate `sahiaaya_resolve` graph. Refresh the page, enter the generated case ID under **Reopen graph case**, and verify that reviewed allocations remain present even if the preset demo was reset.

Try `examples/fictional_second_supplier_case.json` for a second supplier with an expired promotional scheme. See [docs/NEW_CASE_WORKFLOW.md](docs/NEW_CASE_WORKFLOW.md) for the data format, endpoints, trust assumptions and exact demonstration.

**Limits:** These are typed, explicitly synthetic receipts and scheme terms—not independently authenticated real invoices. This local demo has no production identity, supplier messaging, real payments or security model for public mutation endpoints. The [Vercel preview](https://sahiaaya-graphhacks.vercel.app/) intentionally disables the new-case writer because it does not host FalkorDB.

## The demonstrated user problem

A retailer is owed two replacement units from a short delivery, plus two promotional units. Two units arrive. Either obligation could plausibly match, but the supplier hasn't identified the purpose.

SahiAaya asks for the precise missing attribution instead of double-counting the goods or inventing a recovery. After a **simulated** supplier response and explicit **demo** retailer approval, it allocates only the supported quantity, leaves other obligations open and records the review evidence.

This does **not** prove what happened in the physical world. Quantities, invoice documents and supplier replies in this repo are entirely fictional.

## Optional model provider: OpenRouter (local only)

The Track 01 agent uses an OpenAI-compatible Python client. **OpenRouter is supported as an optional API endpoint** without changing FalkorDB or the user interface. The database remains the *local* Docker FalkorDB instance. The current public Vercel site is still a simulation.

**Security:** Never paste or commit a key; if a key has appeared in a chat, revoke it and create a fresh limited-use key at https://openrouter.ai/keys. On Windows PowerShell, in the project directory:

~~~powershell
# Enter your NEW OpenRouter key into this local shell, hidden.
$secure = Read-Host "New OpenRouter API key" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
$env:OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
$env:SAHIAAYA_AGENT_MODEL = "openrouter/free"
docker compose up -d --no-deps --force-recreate app
docker compose exec app python -c "import os; print('OpenRouter endpoint:', os.getenv('OPENAI_BASE_URL') == 'https://openrouter.ai/api/v1'); print('Key configured:', bool(os.getenv('OPENAI_API_KEY'))); print('Model:', os.getenv('SAHIAAYA_AGENT_MODEL'))"
# Run ONE real-model case first. Can be rate-limited or fail; no pass is assumed.
docker compose exec app python -m scripts.live_model_gate --accept-api-cost --only unattributed
~~~

The variable named \`OPENAI_API_KEY\` is deliberately reused because the application uses the OpenAI-compatible SDK; it now contains your **OpenRouter** credential, not an OpenAI Platform key. \`OPENAI_BASE_URL\` is configurable in Docker Compose and otherwise defaults to the official OpenAI API URL. \`openrouter/free\` uses an available free model that can support requested features; its model selection can vary, and rate limits/availability may prevent reliable six-case evidence. For a final judge recording, prefer a fixed tool-capable OpenRouter model with a supported quota. If the first case fails, inspect the case's \`error\` field before paying or rerunning all six. **No live OpenRouter model test has been performed by this documentation change.**

## Run on Windows (Docker Desktop)

```powershell
git clone https://github.com/aadi-harale/graphhacks.git
cd graphhacks
docker compose up -d --build
```

Open **http://localhost:8000**. The shopkeeper-first UI starts with **Check delivery → Follow up → Resolve**. The existing synthetic case and additional scenarios are available in **Advanced workspace**. For model-directed graph investigation, choose **Enter your own case**, then **Investigate with agent**; this additionally requires a locally configured API key. The API refuses to serve a fabricated graph answer when FalkorDB is unreachable.

Run all tests, including **live** graph integration:

```powershell
docker compose exec app pytest -q
docker compose exec -e RUN_FALKOR_TESTS=1 app pytest tests/test_falkor_integration.py -v
```

Inspect local logs with `docker compose logs -f app falkordb`. Stop with `docker compose down`.

## Graph model and actual Cypher role

**Two related, distinct graph schemas exist in this repository.** The relationships immediately below describe the original `app/graph.py` / `app/agent.py` walkthrough. New, user-entered histories use the `Resolve*` schema described afterward; these should not be presented as identical.

- `(:Receipt)-[:FROM_SUPPLIER]->(:Supplier)` and `(:Receipt)-[:FOR_SKU]->(:SKU)`
- `(:Obligation)-[:OWED_BY]->(:Supplier)` and `(:Obligation)-[:FOR_SKU]->(:SKU)`
- `(:Obligation)-[:AROSE_FROM]->(:SourceRecord)-[:SUPPORTED_BY]->(:Document)`
- `(:Promise)-[:PROMISED_FOR]->(:Obligation)`, with the promise linked to its evidence document
- `(:Statement)-[:ABOUT_RECEIPT]->(:Receipt)` and `(:Statement)-[:SUPPORTED_BY]->(:Document)`
- `(:Allocation)-[:USES_RECEIPT]->(:Receipt)`, `(:Allocation)-[:SETTLES]->(:Obligation)`, `(:RetailerApproval)-[:APPROVES]->(:Allocation)`

`app/graph.py` uses prewritten Cypher and the deterministic `app/agent.py` policy for the preset walkthrough. The new-case engine in `app/resolve.py` instead traverses `(ResolveCase)-[:HAS_RECEIPT]->(ResolveReceipt)-[:POTENTIALLY_FULFILLS]->(ResolveObligation)-[:SUPPORTED_BY]->(ResolveDocument)`, relevant supplier statements, and prior allocation records. Its policy evaluates evidence and blocks unsupported/duplicate settlement. `app/track1_agent.py` exposes bounded tools on this new-case graph. The live web API (`app/server.py`) calls `run_agent_mcp` in `app/track1_mcp_loop.py`; it does **not** use the legacy direct-function `run_agent()` helper for this endpoint.

## Agent contract and graph safety

Two clearly separated layers:

1. **Deterministic policy engine.** FalkorDB retrieves candidate obligations, prior receipts and documents. Policy returns ASK_SUPPLIER, ASK_RETAILER, DISPUTE, REVIEW_SETTLEMENT or another bounded state. Only the retailer approves settlement.
2. **Model-directed Track 01 investigator.** The model receives a bounded function catalog derived from the MCP host, selects tool calls via the model provider's function-calling API, and the application executes those calls using MCP stdio `ClientSession` and prewritten FalkorDB queries. Four tools read evidence; one may persist a policy-guarded **internal draft**. MCP handles transport; **real model tool selection has not yet been run or inspected**. No free-form Cypher, supplier messaging or automatic settlement.

The model is optional for simple receiving but required for the Track 01 agent demonstration. CI proves **MCP transport with an injected/mock model** and live FalkorDB, not real-model decisions. The public Vercel site is a fictional browser simulation, not a live graph or agent. [Read the dated submission verification audit](docs/FINAL_SUBMISSION_AUDIT.md).

## API endpoints

- GET /api/health — local graph health
- POST /api/demo/reset, GET /api/investigate/RCP-52 — predefined walkthrough
- POST /api/investigate/RCP-52/simulate-supplier-response and /approve-demo-settlement — reviewed synthetic case actions
- POST /api/resolve/cases, GET /api/resolve/cases/{case_id}/receipts/{receipt_id} — unfamiliar synthetic histories
- POST /api/agent/investigate — real model-selected MCP graph tools and a guarded internal draft; requires OPENAI_API_KEY
- GET /api/resolve/cases/{case_id}/receipts/{receipt_id}/followups — saved draft history
- POST /api/resolve/cases/{case_id}/receipts/{receipt_id}/attribute and /approve — separate retailer-reviewed actions

**These local mutation endpoints are not authenticated. Do not expose them or the FalkorDB service to the public internet.** Real deployment requires authorization and authentication.

## Tests and honest comparison

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python -m scripts.proof_report
```

The fair SQLite baseline, in `app/baseline.py`, uses the **same** receipt, claims and supplier statements. It is expected to reproduce the same deterministic decisions. A graph database is not uniquely capable of the underlying allocation arithmetic.

Competitive advantage remains **unproven**: a fair SQLite baseline reproduces deterministic decisions given equivalent evidence. The demonstrated graph role is connected provenance retrieval and auditable graph-backed actions; no measured SQL performance or accuracy advantage is claimed.

See [BUILD_GATES.md](BUILD_GATES.md) for acceptance gates, [SECURITY.md](SECURITY.md) for deployment restrictions, and [CLAUDE.md](CLAUDE.md) for evidence-first engineering practice.

## AI use and source disclosure

AI assistance has been used to draft design, implementation and tests. All decisions and safety claims require developer review and executable validation. Inspiration: original SahiAaya retail receiving pitch, its later receipt-to-resolution refinement, and the official FalkorDB/WeMakeDevs Graph Hacks rules. No real retailer pilot or independently verified financial recovery is claimed.
