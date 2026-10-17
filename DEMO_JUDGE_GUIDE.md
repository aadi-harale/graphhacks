# SahiAaya — Track 01 judge demonstration (2 minutes 50 seconds)

**Record from the real local FalkorDB + MCP + model application. The public Vercel page is a fictional browser simulator. Do not mislabel mock-model tests as real model reasoning.**

## On-screen story

| Time | Action | What to say |
| --- | --- | --- |
| 0:00–0:20 | Shopkeeper homepage: 50 billed, 48 received. Check delivery. | "The shopkeeper spots two missing soaps. That's the easy part. What happens when the supplier promises to replace them later?" |
| 0:20–0:45 | Enter a new supplier history with two old promises and a later two-soap receipt. | "Two arrived later, but the supplier also owed two promotional soaps. Which old promise did this box fulfill?" |
| 0:45–1:30 | Run real agent. Reveal chosen MCP tools, real FalkorDB evidence and source-document paths. | "The model selected these tools; they traverse connected invoices, claims, deliveries and documents. It didn't guess an answer from the quantity." |
| 1:30–1:55 | Show actual internal follow-up draft. Refresh and reopen the same case. | "With missing attribution, the agent asks a precise question and stores it with the receipt. It doesn't send or settle anything." |
| 1:55–2:20 | Simulate supplier attribution, then separately approve as shopkeeper. | "With support and human review, the promotional promise is recorded as settled. The original shortage remains open." |
| 2:20–2:40 | Show same-quantity conflict/ineligible counterfactual. | "With conflicting history, exactly the same quantity does NOT authorize a settlement." |
| 2:40–2:50 | Display actual tool transcript, graph paths and live CI tests. | "Connected evidence drives tool selection, bounded action and auditable decisions." |

The basic product should stay easy. Only open technical details after the judge sees the outcome.

## Windows PowerShell: exact run commands

Set OPENAI_API_KEY securely on your own PC, outside the repository and this chat. API usage may incur charges.

~~~powershell
git pull origin main
if (-not $env:OPENAI_API_KEY) { throw "Set OPENAI_API_KEY locally first" }
docker compose up -d --build
docker compose exec -e RUN_FALKOR_TESTS=1 app pytest tests/test_track1_agent.py tests/test_track1_counterfactual.py -v
docker compose exec app python -m scripts.live_model_gate --accept-api-cost
New-Item -ItemType Directory -Force -Path .\artifacts | Out-Null
docker cp "$(docker compose ps -q app):/app/artifacts/real_model" ".\artifacts"
python -m pip install playwright
python -m playwright install chromium
python -m scripts.record_real_judge
~~~

The acceptance gate generates six unfamiliar fictional case IDs, invokes a real configured model and collects actual MCP tool requests and responses; it fails if the expected policy outcome or provenance/transport checks are not met. Results are saved to artifacts/real_model/summary.json and individual case JSON files. It also reports whether different model-selected tool sequences occurred. Never call a failed or unavailable run a live model pass.

The Playwright recorder uses the real localhost Docker app, saves a SILENT recordings/sahiaaya_live_real_model.webm and screenshots, and requires a real-model tool trace, saved internal follow-up and separately approved settlement. Add narration separately.

## Judge proof checklist

- New synthetic supplier case that was not coded into the agent prompt.
- Engine = model_selected_mcp_graph_tools, transport = MCP stdio / ClientSession, model_execution = configured_api_client.
- Actual model tool names and arguments paired with bounded FalkorDB results and document provenance paths.
- Internal follow-up draft saved in the graph and recovered after reopening.
- Supplier attribution plus separate retailer approval, with old obligation correctly outstanding.
- Same receipt quantity plus changed source evidence changes the policy action.
- Contradictions, expired schemes, missing promotion documentation, unknown units, duplicate allocation and unsafe writes are handled conservatively.

## Honest limitations

This local application uses fictional data and has **no authentication on demo mutations**; bind it only to localhost. A supplier reference is not independently authenticated. No real supplier has been contacted, no payments occurred and no money recovery or retailer adoption is established. The public Vercel experience is not connected to FalkorDB or a hosted model.

Without a configured real model API key, the genuine MCP client/server/FalkorDB integration tests still prove tool transport and safeguards, but they DO NOT prove real model tool selection. Do not submit only the browser simulation as evidence of the live agent.
