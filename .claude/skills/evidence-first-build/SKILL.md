---
name: evidence-first-build
description: Test-driven SahiAaya FalkorDB investigation and evidence-gated settlements.
---

# Evidence-first build process

1. State the exact invariant and what the available source records support.
2. Add a synthetic counterexample in tests: missing data, duplicate receipt, contradictory supplier statement, stale approval, wrong supplier or SKU.
3. Make the smallest change that satisfies the test.
4. Ensure FalkorDB graph reads actually affect the decision. Run RUN_FALKOR_TESTS=1 against a real instance before claiming integration success.
5. Run a strong, equally informed SQL comparator and report any equivalent results.
6. Verify the three-minute end-to-end workflow and honest audit output.
7. Update the README, testing evidence, AI-use disclosure, and outstanding limitations.
