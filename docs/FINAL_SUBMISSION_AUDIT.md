# SahiAaya — Track 01 final submission evidence audit

**Audit date:** October 17, 2026  
**Scope:** Current public \`main\` of [aadi-harale/graphhacks](https://github.com/aadi-harale/graphhacks). Review only; **no application code or UI changes in this final documentation reconciliation**.  
**Verdict:** **PARTIALLY VERIFIED — do not claim winner-ready or fully live-model-verified.**

## 1. Exact execution architecture, with no contradictions

The repo contains two distinct paths:

1. **Original preset walkthrough — deterministic graph policy.** \`app/graph.py\` retrieves fictional supplier, invoice, receipt and historical evidence through FalkorDB. \`app/agent.py:investigate\` applies human-written policy rules to propose \`ASK_SUPPLIER\`, \`DISPUTE\`, \`REVIEW_SETTLEMENT\`, \`UNKNOWN\` or other bounded outcomes. A separate retailer-approved action is required for settlement. This is **not an LLM agent**.
2. **Track 01 unfamiliar-case investigator — model-directed function selection, MCP transport.** The live endpoint \`POST /api/agent/investigate\` in \`app/server.py\` calls \`app/track1_mcp_loop.py:run_agent_mcp\`. It retrieves descriptions for five bounded tools from the \`app/track1_mcp.py\` host, exposes those as function definitions to an OpenAI-compatible model, and receives the **model's chosen function name and arguments**. It then executes the chosen tool through a **real MCP Python \`ClientSession\` over stdio**. The MCP host runs predefined Cypher against the \`sahiaaya_resolve\` FalkorDB graph. Four tools read connected evidence; the fifth may persist only a policy-guarded internal follow-up draft. Actual settlement is a separate retailer-reviewed route. **MCP does not choose tools; the model chooses function calls and MCP transports/executes them.**

The original helper \`app/track1_agent.py:run_agent\` can invoke tools directly, but **the current live web endpoint does not call that helper**. Consequently, its existence must not be used to imply that the running web agent bypasses MCP.

No model can submit unrestricted Cypher through the documented agent tool catalog. No supplier is actually contacted and there is no autonomous settlement.

## 2. Verified evidence from repository CI

**Application-code baseline SHA:** [\`3450661ca0b2037c8e098df9bb449fd3c0c55832\`](https://github.com/aadi-harale/graphhacks/commit/3450661ca0b2037c8e098df9bb449fd3c0c55832).  
**Inspected passing GitHub Actions run:** [\`39025651473\`](https://github.com/aadi-harale/graphhacks/actions/runs/39025651473).

| Check | Exact observed result | Meaning |
| --- | --- | --- |
| Policy job | **23 passed, 9 skipped** (graph-only cases deliberately skipped without FalkorDB service) | Deterministic logic, SQL baseline, static/tool contract tests. **Not a paid model run.** |
| Live FalkorDB/MCP job | **26 passed, 0 skipped** (7.50s Pytest summary) | Actual live graph service, bounded MCP stdio client/server tool calls, injected-model tool sequence, persisted internal follow-up and graph source counterfactuals. **Model choices mocked/injected.** |
| Synthetic browser job | **PASSED** | KaamSabha-style receiving interface, visible states and responsive browser flow with fictional client-side results. |
| Live FalkorDB browser job | **PASSED** | Local FastAPI/FalkorDB-backed receiving, supplier simulation and guarded approval. Agent API test without a key confirms honest unavailable state; a UI-only mocked agent response tests clickable evidence paths. |
| Static/UI, syntax and proof report | **PASSED** in policy job | Compilation, UI DOM bindings and fair deterministic baseline. |

**Counterfactual actually proved in deterministic + real-graph tests:** for an otherwise unchanged **2-unit receipt**, before source attribution the policy returns \`ASK_SUPPLIER\`; after a source reference identifies a promotional claim, it returns \`REVIEW_SETTLEMENT\`; incompatible active supplier statements instead produce \`DISPUTE\`. Expired promotion data produces \`NEEDS_REVIEW\`, unknown units produce \`UNKNOWN_UNIT\`, and settled receipts return \`ALREADY_ALLOCATED\`. This proves a graph-backed **policy** response to evidence changes. It does **not** prove an independent real model chose different investigative paths.

**SQL control:** \`app/baseline.py\` is intentionally fair; equivalent structured evidence reproduces the same deterministic allocation decisions. No graph-only mathematical, latency, accuracy or commercial superiority is established.

## 3. Unrun/blocked critical gates

At audit time, the task execution environment was inspected:

- \`OPENAI_API_KEY\`: **absent**
- \`docker\` executable: **unavailable**
- Docker daemon: **unavailable**
- Privately configured external machine or its recordings: **not accessible or supplied**

Consequently:

| Required real-model scenario | Real configured-model result |
| --- | --- |
| Multiple competing claims, no receipt attribution | **NOT RUN** |
| Source evidence supports one obligation | **NOT RUN** |
| Conflicting supplier statements | **NOT RUN** |
| Expired/ineligible or undocumented promotion | **NOT RUN** |
| Already allocated / duplicated receipt | **NOT RUN** |
| Unknown unit or insufficient evidence | **NOT RUN** |

**Real-model tool names, arguments, next choices, source paths and final answers: NONE VERIFIED.** No genuine model call, API response, evidence transcript, or locally recorded video can be cited from this audit. The \`scripts/live_model_gate.py\` and \`scripts/record_real_judge.py\` files are runnable acceptance utilities, **not evidence that they have run successfully**.

The six-case runner creates new randomized synthetic supplier/SKU/document identities and requires \`--accept-api-cost\`. It stores per-case actual function requests, MCP returns, graph paths, decision states and safe follow-up drafts. Its summary reports differing tool sequences, refusing an all-green conclusion on safety or decision failures. Results must be inspected by the user before claiming model reasoning.

**Recording status:** no verified video. \`record_real_judge.py\` is designed to label an interrupted/failed recording \`UNVERIFIED_attempt.webm\`; only completion of its real local model/MCP, evidence, follow-up and approval checks produces the claimed \`sahiaaya_live_real_model.webm\`. This design has **not** been proven against a live model in this audit.

## 4. Exact local acceptance commands (Windows PowerShell)

The real model test requires credentials configured **privately on the user's machine**; never paste or commit a token in chat, source or a video. API usage may incur charges.

~~~powershell
git pull origin main
if (-not $env:OPENAI_API_KEY) { throw "Configure OPENAI_API_KEY privately before running" }
docker compose up -d --build
docker compose exec -e RUN_FALKOR_TESTS=1 app pytest tests/test_falkor_integration.py tests/test_graph_safety.py tests/test_resolve_intake.py tests/test_track1_agent.py tests/test_track1_counterfactual.py -v
docker compose exec app python -m scripts.live_model_gate --accept-api-cost
New-Item -ItemType Directory -Force -Path .\artifacts | Out-Null
docker cp "$(docker compose ps -q app):/app/artifacts/real_model" ".\artifacts"
python -m pip install playwright
python -m playwright install chromium
python -m scripts.record_real_judge
~~~

After running, inspect \`artifacts/real_model/summary.json\` and each case JSON: \`execution_kind=REAL_MODEL_API_NOT_MOCKED\`, \`model_execution=configured_api_client\`, \`engine=model_selected_mcp_graph_tools\`, \`transport=MCP stdio / ClientSession\`, actual \`tool_trace\` including bounded returned \`result\` objects, noninvented \`evidence_paths\`, correct authoritative policy status, and safe \`draft\`. For different evidence conditions, compare **actual model-selected tool sequences**, not merely deterministic verdicts. Confirm the draft remains after reopening the graph case. Only then inspect the silent recorded video against the real application state and narrate the canonical 2:50 guide.

The local instance binds to \`127.0.0.1\`. **Do not publish unauthenticated mutation endpoints.** The [Vercel preview](https://sahiaaya-graphhacks.vercel.app/) is intentionally a browser-side synthetic illustration, not a hosted FalkorDB/LLM service.

## 5. Submission-readiness status and limitations

| Criterion | Status |
| --- | --- |
| Clean, simple shopkeeper interface | Browser tests **PASS**; independent first-time human usability study **not performed** |
| FalkorDB graph is genuinely used to retrieve provenance | **PASS** in real graph tests |
| MCP is genuinely on the agent tool-execution path | **PASS** in injected-model/real-transport tests; source wired to live endpoint |
| Model independently chooses useful tools on unfamiliar cases | **UNVERIFIED** — real model not run |
| Model takes a guarded graph action and persists it | **PASS with mocked choices**, real model **unverified** |
| Graph evidence changes the justified policy outcome | **PASS** with same-quantity graph counterfactual |
| Fair SQLite comparison | Equal deterministic decisions confirmed; **no proven graph advantage in runtime or accuracy** |
| Six paid-model acceptance scenarios | **0/6 completed in this audit** |
| Genuine local Docker demo, video and video-to-source review | **NOT RUN/NOT VERIFIED** |
| Actual hackathon submission and compliance review | **NOT VERIFIED** |

Additional scope limitations: completely synthetic source records, no independent supplier attribution authentication, no real retail pilot or recovered payments, no production-grade tenant authorization, no hosted authenticated FalkorDB deployment, and no established competitor/winner guarantee.

**Go/no-go:** Stronger code and graph/MCP tests are verified, but **do not describe SahiAaya as fully submission-verified or winner-ready until the private real-model gate passes and its authentic local demo recording has been reviewed**.

This audit supersedes any earlier conversational summary that labeled scripted/mock-model selection or a public browser simulation as actual model execution. The current truth is code-wired MCP plus real graph transport, but unverified live model intelligence.
