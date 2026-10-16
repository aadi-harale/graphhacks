# SahiAaya — executable build gates

## A — Decision model (unit tests)
Counterfactual cases change only source attribution; expected decisions change. Missing evidence remains uncertain. Execute:

```bash
python -m pytest -q tests/test_decisions.py tests/test_baseline.py
python -m scripts.proof_report
```

A fair SQLite+provenance baseline must receive the same inputs and is allowed to reach identical decisions. This does not prove graph-exclusive accuracy.

## B — Real FalkorDB (mandatory for submission)
On Windows with Docker Desktop:

```powershell
docker compose up -d --build
docker compose exec -e RUN_FALKOR_TESTS=1 app pytest tests/test_falkor_integration.py -v
```

The GitHub Actions integration job also starts FalkorDB and executes these tests. No successful run may be claimed until its conclusion is inspected. Ensure graph-backed evidence changes the action, and that version guards reject stale approvals.

## C — Distinguishing value
Evaluate unfamiliar, multi-delivery supplier histories with conflicting promises, corrections, and missing evidence. Compare investigation steps, manual evidence linking, false settlements, and useful clarification requests against a properly engineered SQL baseline.

## D — Usability and responsible deployment
Test physical-unit conversions, duplicate receipt IDs, immutable provenance, tenant isolation, concurrent approvals, supplier-authenticated statements and a responsive UI. Current demo has **no authentication** and must run only on localhost.

## Hackathon submission
Publish actual graph schema/Cypher examples, setup instructions, fully reproducible demo video, responsible AI coding disclosure, public source, and explicit failures/unknowns. No claimed commercial pilots.
