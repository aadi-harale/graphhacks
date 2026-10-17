# Track 01 / iPhone 18 Pro — SahiAaya Graph Investigator

**As checked October 17, 2026:** The prize for Track 01, **Agents That Act on Connected Data**, is an **iPhone 18 Pro** (not Track 02 or 03). Official rules: https://www.wemakedevs.org/hackathons/falkordb/rules . The submission deadline is **October 18, 2026, 11:59 PM IST**.

## The change that matters

The previous SahiAaya EvidenceGap system was graph-backed but **not itself a model-directed agent**: the next action was chosen by a deterministic Python branch, and the public Vercel preview operated entirely without a live graph.

The **Track 01 Graph Investigator** exposes a bounded tool catalog to a function-calling model. With a provider API key, that model can choose functions based on previous results. In CI, those choices are **injected**; MCP transport and FalkorDB results are real. Genuine model tool choices have not been captured. The code refuses any approval or unsupported write. The only available agent write creates an **internal draft follow-up** connected to the investigated receipt.

Track requirements and organizer's October 15 primary-source explanation:
- https://www.wemakedevs.org/hackathons/falkordb
- https://www.wemakedevs.org/blogs/how-to-build-an-agent-that-reasons-over-a-graph
- https://www.wemakedevs.org/hackathons/falkordb/rules

### Agent tools

| Tool | Why it exists | Changes data? |
| --- | --- | --- |
| `list_case_receipts` | Discover prior deliveries in the same fictional case | No |
| `investigate_receipt` | Retrieve canonical policy decision, candidate claims and graph path | No |
| `trace_claim_evidence` | Traverse receipt → potentially fulfilled obligation → supporting document, alongside supplier statement | No |
| `inspect_cross_delivery` | Follow the same obligation across multiple delivery and allocation records | No |
| `create_followup_draft` | Persist a source-versioned, evidence-linked *internal* clarification/review task | **Yes, draft only** |

The deterministic core still controls actual allocation safety. Existing retailer-review endpoints are **not agent tools**. A fabricated model sentence can neither change the canonical decision nor bypass the graph-write guard.

### Live MCP path

The web API calls `run_agent_mcp`, discovers five bounded tools from the MCP host, and advertises them to an OpenAI-compatible **function-calling model**. The model chooses tool names and arguments; the application executes them through **MCP Python ClientSession over stdio** and `app.track1_mcp`. The MCP server executes human-written Cypher against the `sahiaaya_resolve` graph. Four tools are read-only; `create_followup_draft` is the sole mutation tool and is guarded by evidence retrieval, current policy, source-version checks and local-only mutation mode.

```text
Question → model chooses tool → MCP ClientSession → typed MCP tool
         → FalkorDB Cypher → evidence and path → model chooses next tool
         → guarded internal follow-up DRAFT → persistent graph node
```

The model is never offered arbitrary-Cypher, supplier-message or settlement-approval tools. **MCP is the tool-execution transport, not the tool-choice mechanism.** The endpoint uses this route, but only injected-model MCP runs are verified so far.

**Verified proof level:** [Application-code baseline CI](https://github.com/aadi-harale/graphhacks/actions/runs/39025651473): 23 passing policy tests and 9 graph-only skips in the policy job; 26 passing real FalkorDB/MCP tests; both browser jobs passed. MCP tests inject fake-model selections, so **no genuine model-choice run or real-model demo recording is verified**. See [submission audit](FINAL_SUBMISSION_AUDIT.md).

## How to run real agent mode

The real agent requires **a key you supply locally**. API use may incur charges; no model API call is made unless you configure the environment variable and press the local investigation button.

```powershell
git pull origin main
$env:OPENAI_API_KEY = "PASTE_YOUR_KEY_LOCALLY_NOT_IN_GITHUB"
docker compose up -d --build
```

Open http://localhost:8000. Under **Try a different delivery**, import `examples/fictional_two_delivery_case.json` or enter fresh fictional quantities. Create the case, select a receipt, and click **Investigate with agent**. Review the selected tools, graph paths, policy result and persistent follow-up draft.

The model is configured via `SAHIAAYA_AGENT_MODEL` (default `gpt-4o-mini`), which can be overridden in your local environment. The backend has a bounded maximum number of rounds and disallows free-form Cypher, external messages and settlement write tools.

You can also launch the MCP host independently using `python -m app.track1_mcp` (stdio). It exposes four read-only tools and one strictly guarded internal-draft writer; no settlement endpoint or supplier send is exposed.

**Do not paste or commit API keys into source, screenshots or GitHub.**

## How to verify the actual MCP transport

```powershell
docker compose up -d --build
# In the repository directory, CI runs this same graph-backed test:
docker compose exec -e RUN_FALKOR_TESTS=1 app pytest tests/test_track1_agent.py -v
```

For genuine model tool selection, configure `OPENAI_API_KEY` locally **before** starting Docker. Require `engine=model_selected_mcp_graph_tools` **and** `model_execution=configured_api_client`, then inspect actual tool choices, arguments, MCP results and persisted follow-up. These labels alone are not proof: the complete source-grounded transcript and safety checks must also pass. Never pass off injected-model tests as live-model evidence.

## Acceptance gates: model, MCP and graph evidence

**CI verification:** real FalkorDB + real MCP stdio transport + a controlled injected model. This confirms the tool interface, graph traversals, receipt-versus-source-evidence counterfactual, conflicts, scheme ineligibility and allocation guards. It does **not** prove that an actual model chooses tools intelligently.

**Live model acceptance (must be done on a machine with an API key):**

~~~powershell
git pull origin main
if (-not $env:OPENAI_API_KEY) { throw "Configure an API key locally; do not commit it" }
docker compose up -d --build
docker compose exec -e RUN_FALKOR_TESTS=1 app pytest tests/test_track1_agent.py tests/test_track1_counterfactual.py -v
docker compose exec app python -m scripts.live_model_gate --accept-api-cost
New-Item -ItemType Directory -Force -Path .\artifacts | Out-Null
docker cp "$(docker compose ps -q app):/app/artifacts/real_model" ".\artifacts"
python -m pip install playwright
python -m playwright install chromium
python -m scripts.record_real_judge
~~~

The acceptance runner randomizes synthetic case, supplier, SKU and source-reference identifiers. Six distinct source conditions are tested: multiple competing obligations with no attribution, a supported assignment, conflicting statements, an ineligible promotion, an already-allocated receipt, and an unknown pack unit. It saves a JSON report per case with the *actual* model tool names, validated arguments, MCP results, evidence paths, subsequent tool decisions, final authoritative policy and persisted draft. Every scenario must pass. It separately reports whether tool choices differed across cases. If the model never changes path or fails a safety check, the gate fails instead of reporting a win.

The browser video recorder also fails closed if the model is unavailable, no persisted draft appears or the reviewed settlement doesn't succeed. A failed attempt is labeled UNVERIFIED_attempt.webm, not a real-model success recording. Successful runs create recordings/sahiaaya_live_real_model.webm and evidence screenshots. The video is silent; record narration separately. API usage may incur charges.

The public Vercel preview is a fictional UI illustration and cannot run the hosted MCP model. Do not publish local unauthenticated mutation endpoints, real retailer information or model API keys.

## Judge demo — canonical 2 minutes 50 seconds

Use **[DEMO_JUDGE_GUIDE.md](../DEMO_JUDGE_GUIDE.md)** as the only timecoded 2:50 script. It begins with the shopkeeper's problem, then shows actual tool requests and graph evidence, a saved internal follow-up, simulated supplier attribution, and separate retailer approval. Record it from local Docker, not Vercel. **No verified real-model video exists yet.**

## Go/no-go gates (must be real before submission)

- [x] The repo has real FalkorDB graph query and bounded reviewed-settlement integration tests.
- [x] Model function-call **contract** tested with fake model messages and verified read-only graph tools.
- [x] Actual MCP ClientSession transport tested with injected model decisions and live FalkorDB.
- [x] Graph-backed same-quantity evidence counterfactual, conflict, ineligibility, already-allocated replay and undocumented-promotion rejection tested.
- [ ] Tool selection demonstrated using a **real model and privately configured API key** (neither available nor run in this audit environment).
- [ ] Six-scenario real-model gate, unfamiliar case, evidence-dependent tool choices, and locally recorded persistent draft + retailer approval verified.
- [ ] Compare against normal typed SQL supplier-ledger investigation on equally informed input. Existing SQL baseline matches simple status decisions, so **no graph-exclusivity or accuracy superiority claim** is justified.
- [ ] Clarity: unfamiliar human understands need and result in first 20 seconds.
- [x] README and architecture distinguish deterministic policy, model-directed MCP tool selection, public simulation and fake-model verification.
- [ ] Submission and video complete before October 18, 23:59 IST (not verified by this audit).

The current agent refit is a **stronger Track 01 fit** but no winner guarantee. It remains a fictional local MVP; no direct supplier authenticity check, real money recovery or real-store pilot was performed.

## What the past winners suggest

Atrium (first at FalkorDB's August 2026 Memory Meets Motion) used misconceptions connected by graph edges to make the same lesson grade lead to different interventions. See https://www.falkordb.com/blog/memory-meets-motion-the-falkordb-standouts/ (August 18). We should likewise show identical delivery quantities but **different graph-backed next actions**. The October 7 First Commit winner recap describes Beacon's investigate → propose → approve → verify loop. See https://www.wemakedevs.org/blogs/first-commit-hackathon-recap-and-whats-next . These precedents inform the interaction, but do not establish a particular prize-winning scoring formula.
