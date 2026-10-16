# SahiAaya engineering charter

Use test-driven, evidence-led development. Before editing graph reads, settlement gates, or UI, consult .claude/skills/evidence-first-build/SKILL.md.

1. Start with a minimal counterexample and a failing test.
2. Preserve distinct supplier evidence, retailer confirmation and approval steps.
3. Python controls identity, quantities, versions and approval; model output cannot settle claims.
4. Unknown data fails closed. Never invent proof, prices or savings.
5. FalkorDB must provide the decision context through actual Cypher reads in live mode. Do not claim fixture mode is live mode.
6. Compare against an equally informed SQLite baseline, not a deliberately weak comparator.
7. Execute pytest, proof report, real FalkorDB tests, and a browser scenario; document all unrun checks.
8. Public source uses only fictional merchants and synthetic documents.

UI: calm mobile receiving desk, cream/deep green/amber, accessibility, focus states, responsive layouts. Avoid cosmetic animated graph displays.
