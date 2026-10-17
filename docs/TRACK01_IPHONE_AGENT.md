# Track 01 / iPhone 18 Pro — SahiAaya Graph Investigator

**As checked October 17, 2026:** The prize for Track 01, **Agents That Act on Connected Data**, is an **iPhone 18 Pro** (not Track 02 or 03). Official rules: https://www.wemakedevs.org/hackathons/falkordb/rules . The submission deadline is **October 18, 2026, 11:59 PM IST**.

## The change that matters

The previous SahiAaya EvidenceGap system was graph-backed but **not itself a model-directed agent**: the next action was chosen by a deterministic Python branch, and the public Vercel preview operated entirely without a live graph.

The new **Track 01 Graph Investigator** exposes bounded tools to a real function-calling model. The model selects which ones to use; all source facts come from FalkorDB. The code refuses any approval or unsupported write. The only available agent write creates an **internal draft follow-up** connected to the investigated receipt.

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

The web API now calls `run_agent_mcp`. The model chooses among five bounded function definitions, then an **MCP Python ClientSession over stdio** calls `app.track1_mcp`. The MCP server executes human-written Cypher against the `sahiaaya_resolve` graph. Four tools are read-only; `create_followup_draft` is the sole mutation tool and is guarded by evidence retrieval, current policy, source-version checks and local-only mutation mode.

```text
Question → model chooses tool → MCP ClientSession → typed MCP tool
         → FalkorDB Cypher → evidence and path → model chooses next tool
         → guarded internal follow-up DRAFT → persistent graph node
```

The model never generates Cypher, sends a supplier message or approves settlement. **MCP is now the actual transport of the local web agent**, not just an optional stand-alone endpoint.

**Proof level:** GitHub CI validates a fake model choosing tools over an authentic MCP stdio connection and actual FalkorDB graph; it checks the saved draft can be re-read. This does NOT prove that the live OpenAI model selects the right tools, because there is no configured model key in CI.

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

For actual model selection, set `OPENAI_API_KEY` in your local shell **before** launching Docker. Click **Investigate with agent**, confirm the returned engine is `model_selected_mcp_graph_tools`, inspect its MCP tool sequence and graph paths, then reopen the saved case and follow-up. Do not represent the automated fake-model tool selection as a real model run.

## The judge-facing demo (2 minutes 30 seconds)

1. **0:00–0:23 — Simple real-life problem.** Shopkeeper invoiced for 50 soaps, physically received 48; shortage recorded. Supplier also owed a separate documented promotion. Fictional example.
2. **0:23–0:50 — A later delivery.** New two-unit receipt appears in a two-delivery history. SahiAaya cannot decide from quantity alone which prior promise it fulfils.
3. **0:50–1:26 — Agent picks graph tools.** Show tool trace: investigate → source documents → cross-delivery obligation links. Display one multi-hop graph path and the recorded source reference.
4. **1:26–1:49 — Agent acts.** It creates a specific supplier clarification *draft* as a new graph-linked node. Reopen the case and show the durable follow-up. No message was sent.
5. **1:49–2:10 — Evidence arrives, human verifies.** Enter a **simulated** supplier answer, then retailer approval. Two promotional units settle, the original shortage remains open.
6. **2:10–2:30 — Adversarial test.** Repeat with contradictory references or ineligible scheme; the policy blocks closure. Show the live FalkorDB integration CI run.

Record from the **local Docker application, not merely Vercel**. Public Vercel currently shows a browser-only fictional walkthrough and is not evidence of an agent running.

## Go/no-go gates (must be real before submission)

- [x] The repo has real FalkorDB graph query and bounded reviewed-settlement integration tests.
- [x] Model function-call **contract** tested with fake model messages and verified read-only graph tools.
- [ ] Actual tool selection demonstrated with a **real** model and the selected model's API key (no such key is stored or assumed).
- [ ] Complete agent session on unfamiliar case, including saved draft, recorded on video with FalkorDB query paths.
- [ ] Compare against normal typed SQL supplier-ledger investigation on equally informed input. Existing SQL baseline matches simple status decisions, so **no graph-exclusivity or accuracy superiority claim** is justified.
- [ ] Clarity: unfamiliar human understands need and result in first 20 seconds.
- [ ] Final README names Track 01, graph model, Cypher tools, instructions and AI-coding disclosure.
- [ ] Submission and video complete before October 18, 23:59 IST.

The current agent refit is a **stronger Track 01 fit** but no winner guarantee. It remains a fictional local MVP; no direct supplier authenticity check, real money recovery or real-store pilot was performed.

## What the past winners suggest

Atrium (first at FalkorDB's August 2026 Memory Meets Motion) used misconceptions connected by graph edges to make the same lesson grade lead to different interventions. See https://www.falkordb.com/blog/memory-meets-motion-the-falkordb-standouts/ (August 18). We should likewise show identical delivery quantities but **different graph-backed next actions**. The October 7 First Commit winner recap describes Beacon's investigate → propose → approve → verify loop. See https://www.wemakedevs.org/blogs/first-commit-hackathon-recap-and-whats-next . These precedents inform the interaction, but do not establish a particular prize-winning scoring formula.
