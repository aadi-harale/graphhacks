# SahiAaya — Bill vs Box. Promise vs Proof.

**The supplier memory a kirana owner never had.** Suppliers short-ship, promise replacements, run schemes, then send deliveries without saying what they are for. SahiAaya keeps every bill, delivery, promise and document in a FalkorDB graph. Its agent reconciles the **whole** supplier ledger with `algo.maxFlow`, proposes only the allocations the evidence forces, and turns everything else into one precise question for the supplier.

**Graph Hacks × FalkorDB (Oct 15–18, 2026)** · Tracks: **01 Agents That Act on Connected Data** (primary) · **02 Agent Memory and Coordination**

> AI investigates. The graph remembers and reconciles. Rules verify. The shopkeeper approves.

## The 30-second story

Sharma Distributors bills a Pune kirana for 50 soaps; 48 arrive. Sharma promises 2 replacements. The shop has also earned 2 free soaps under a Diwali scheme that must be delivered by 7 October.

| Claim | Owed | Source |
| --- | --- | --- |
| Short-delivery replacement | 2 | Invoice 1041: billed 50, received 48 |
| Diwali scheme | 2 | Scheme circular; deliver by 7 Oct |

Two unlabelled drops of 2 soaps arrive — on 5 October and 9 October. Which promise did each settle?

- **A stock register / per-row rule** gives the first drop to the oldest claim (the shortage). The second drop is then stranded, and the scheme looks unpaid. **2 of 4 units settled — both against the wrong claim.**
- **SahiAaya** asks the graph. The 9 October drop arrived after the scheme window, so it can only be the shortage. That *forces* the 5 October drop onto the scheme. **4 of 4 units proposed, each with its evidence path** — no supplier statement needed and nothing guessed.

If both drops had arrived inside the window, either assignment would be valid. SahiAaya then proposes **nothing** and drafts: *"DROP_1 could be for DIWALI_SCHEME or SHORT_JUN; DROP_2 could be for … Please state which claim each delivery was for."*

## Why this needs FalkorDB

Take FalkorDB out and SahiAaya cannot reconcile, explain or settle anything.

| Capability | How the graph does it |
| --- | --- |
| Reconcile the whole ledger | `algo.maxFlow` over `LedgerSource → Receipt → Obligation → LedgerSink` |
| Prove an allocation is forced | Block one `POTENTIALLY_FULFILLS` edge, re-run `algo.maxFlow`; the drop is the units that edge carries in **every** maximum allocation |
| Explain every number | Path `Receipt → POTENTIALLY_FULFILLS → Obligation → SUPPORTED_BY → Document` |
| Refuse contradictions | A receipt with conflicting active `ResolveStatement`s gets zero flow capacity → `DISPUTE` |
| Settle safely | One guarded Cypher write: versions, eligibility, no contradicting statement, retailer approval — or nothing |
| Remember | Cases, statements, drafts and approvals persist; reopen a case days later and the agent resumes from the graph |

**The guarantee.** For edge *e*, forced(*e*) = F − F(*e* blocked), where F is the max flow. Every maximum allocation carries at least forced(*e*) on *e*, and the bound is tight. So when every recorded delivery really was meant to settle an open claim, a forced proposal can never contradict the truth. `tests/test_ledger.py` checks this by brute force on 150 random networks.

## Results

`scripts/benchmark.py` generates 60 synthetic ledgers per setting, each with a **planted truth** (what each delivery was really for). Scores are against that truth, not against the algorithm.

<!-- BENCHMARK-TABLE -->
| Setting | Method | Units settled correctly | Units settled **wrongly** | Units left as supplier questions | Cases with any wrong settlement |
| --- | --- | --- | --- | --- | --- |
| Every delivery settles a claim (238 units, 60 cases) | Per-row FIFO | 154 | 80 | 4 | 33/60 |
| Every delivery settles a claim (238 units, 60 cases) | **SahiAaya graph** | 95 | 0 | 143 | 0/60 |
| Some cases also hold a fresh order (15%) (284 units, 60 cases) | Per-row FIFO | 171 | 98 | 15 | 40/60 |
| Some cases also hold a fresh order (15%) (284 units, 60 cases) | **SahiAaya graph** | 116 | 0 | 168 | 0/60 |

Engine: `python_fallback (this FalkorDB build has no algo.maxFlow)` · seed 11 · source: local run. Graph proposals equal the equally informed SQL comparator in 60/60, 60/60 cases.

Honest reading:
- SahiAaya does **not** settle more units than a FIFO rule. It settles **only correct ones** and turns the rest into targeted supplier questions.
- An **equally informed** comparator — the same rows in SQLite plus the same max-flow maths in Python — reproduces the graph's proposals exactly. The claim is that the graph computes this natively, with traversable provenance, beside the agent's memory. It is **not** that SQL cannot.

## Try it (Docker)

```bash
git clone https://github.com/aadi-harale/graphhacks.git && cd graphhacks
docker compose up -d --build
```

Open http://localhost:8000 → **Try your own delivery history** → click **Load demo: two unlabelled drops (forced)**. The ledger panel shows 4 owed, 4 settleable, 4 forced, each with its path. Click **Shopkeeper approves 2** and watch the claim close. Then try **Load demo: symmetric drops (ambiguous)**: 0 forced, and the exact supplier question appears.

The Track 01 agent (**Investigate with agent**) needs a model key: see [docs/REAL_MODEL_SETUP.md](docs/REAL_MODEL_SETUP.md). The [Vercel preview](https://sahiaaya-graphhacks.vercel.app/) is a browser-only synthetic walkthrough. It does not host FalkorDB.

Tests:

```bash
docker compose exec app pytest -q
docker compose exec -e RUN_FALKOR_TESTS=1 app pytest -v tests/test_ledger.py
docker compose exec app python -m scripts.benchmark --cases 60 --noise 0.15 --live
```

## Graph model

```
(:ResolveCase)-[:HAS_RECEIPT]->(:ResolveReceipt {qty, available, received_on, confirmed, version})
(:ResolveCase)-[:HAS_OBLIGATION]->(:ResolveObligation {kind, original, remaining, eligible, deliver_by, version})
(:ResolveObligation)-[:SUPPORTED_BY]->(:ResolveDocument {ref})
(:ResolveReceipt)-[:POTENTIALLY_FULFILLS {flow_cap}]->(:ResolveObligation)   // date, unit and scheme-window checks
(:ResolveStatement {target_id, reference, active})-[:ABOUT]->(:ResolveReceipt)
(:LedgerSource)-[:FEEDS {flow_cap}]->(:ResolveReceipt)
(:ResolveObligation)-[:DRAINS {flow_cap}]->(:LedgerSink)
(:ResolveAllocation {qty, proof})-[:FROM]->(:ResolveReceipt), -[:SETTLES]->(:ResolveObligation)
(:ResolveApproval)-[:CONFIRMS]->(:ResolveAllocation)
(:ResolveFollowUp {action, question, status})-[:FOR_RECEIPT]->(:ResolveReceipt)
```

`flow_cap` is derived from graph facts on every reconcile. It is never a business fact. The original preset walkthrough (`app/graph.py`) uses an older `Receipt/Obligation/Allocation` schema in a separate graph.

## The Cypher the product depends on

The core algorithm call (`app/ledger.py`, `Q_MAXFLOW`):

```cypher
MATCH (src:LedgerSource {tenant:$tenant,case:$case}),(snk:LedgerSink {tenant:$tenant,case:$case})
CALL algo.maxFlow({sourceNodes:[src], targetNodes:[snk], capacityProperty:'flow_cap',
                   relationshipTypes:['FEEDS','POTENTIALLY_FULFILLS','DRAINS']})
YIELD edges, edgeFlows, maxFlow
UNWIND range(0, size(edges)-1) AS i
WITH edges[i] AS e, edgeFlows[i] AS units, maxFlow
WHERE type(e)='POTENTIALLY_FULFILLS'
RETURN startNode(e).id, endNode(e).id, units, maxFlow
```

Eligibility edges are created at intake (`app/resolve.py`):

```cypher
MATCH (c:ResolveCase {tenant:$tenant,id:$case})-[:HAS_RECEIPT]->(r:ResolveReceipt {id:$id})
MATCH (c)-[:HAS_OBLIGATION]->(o:ResolveObligation)
WHERE o.eligible=true AND o.created_on <= r.received_on AND r.unit=c.unit
  AND (coalesce(o.deliver_by,'')='' OR r.received_on <= o.deliver_by)
CREATE (r)-[:POTENTIALLY_FULFILLS]->(o)
```

Also in `app/ledger.py`:
- `Q_CAPS_RECEIPTS` — supplier attribution narrows edges; conflicts zero the receipt.
- `Q_BLOCK_EDGE` — the forced-unit test.
- `Q_PATH` — the evidence path.
- `Q_APPROVE_FORCED` — the guarded settlement write.

The per-receipt investigation queries are in `app/resolve.py` and `app/track1_agent.py`.

## The agent (Track 01) and its memory (Track 02)

The model chooses among six bounded tools. A real MCP stdio `ClientSession` carries each call to a FalkorDB tool host (`app/track1_mcp.py`):

| Tool | What it does |
| --- | --- |
| `list_case_receipts` | All deliveries in the case |
| `investigate_receipt` | Connected claims and the authoritative per-receipt decision |
| `trace_claim_evidence` | Receipt → claim → document paths and supplier statements |
| `inspect_cross_delivery` | One claim across every linked delivery and allocation |
| `reconcile_ledger` | **`algo.maxFlow` over the whole ledger: forced, ambiguous, still owed** |
| `create_followup_draft` | The only write: an internal, policy-checked draft question |

The model cannot write Cypher, contact a supplier, or settle. Settlement is a separate, retailer-approved, guarded write.

**Track 02 coverage:**
- **Episodic memory:** statements, follow-up drafts and approvals are versioned graph events.
- **Semantic memory:** claims and scheme terms.
- **Procedural memory:** eligibility rules encoded as graph edges.
- **Persistence:** reopen a case by ID after a refresh.
- **Handoff:** the shop assistant logs deliveries; the owner approves later from the same graph state.
- **Isolation:** user-entered cases live in their own graph (`sahiaaya_resolve`), apart from the resettable preset demo.

## Verification status

| Claim | Status |
| --- | --- |
| Ledger reconciliation, forced-unit proofs, conflicts, guarded approval | **Tested** on live FalkorDB (`tests/test_ledger.py`) |
| `algo.maxFlow` runs on `falkordb:latest` | **CI-checked**: the job fails if the engine falls back to Python |
| MCP transport incl. `reconcile_ledger` | **Tested** with injected tool choices over a real stdio session |
| Benchmark vs FIFO and equally informed SQL | **Run** on live graph; see Results |
| Real LLM choosing tools well on unfamiliar cases | **Not yet verified.** Acceptance script: `scripts/live_model_gate.py` |
| Real suppliers, invoices, payments | **None.** All data is synthetic |

## Limitations

- **Forced proposals assume each recorded delivery was meant to settle an open claim.** A fresh order recorded in the case could be mis-read. Every proposal therefore still needs the shopkeeper's approval. The benchmark's `noise` setting adds such fresh orders on purpose.
- **The forced-unit test temporarily edits one derived capacity per edge.** This runs under a process lock. It is fine for a local demo; production would compute on a snapshot.
- **No real identity or authentication.** Local mutation endpoints have neither. Do not expose them publicly (see [SECURITY.md](SECURITY.md)).
- **Synthetic data only.** No pilot, recovered money or real supplier was involved.

## AI use disclosure

AI coding assistants (Claude, among others) helped draft design, code, tests and docs. The team reviewed the graph model, queries and safety rules and validated them with executable tests. The max-flow modelling, the forced-unit rule and its brute-force test are explained in `app/flow.py`, `app/ledger.py` and `tests/test_ledger.py`.

More: [docs/TRACK01_IPHONE_AGENT.md](docs/TRACK01_IPHONE_AGENT.md) · [docs/NEW_CASE_WORKFLOW.md](docs/NEW_CASE_WORKFLOW.md) · [docs/FINAL_SUBMISSION_AUDIT.md](docs/FINAL_SUBMISSION_AUDIT.md) · [BUILD_GATES.md](BUILD_GATES.md) · [CLAUDE.md](CLAUDE.md)
