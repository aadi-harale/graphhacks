# SahiAaya — EvidenceGap
**Bill vs Box. Promise vs Proof.** Graph Hacks × FalkorDB 2026.

SahiAaya investigates supplier promises across historical receipts, identifies the exact missing evidence to resolve a competing claim, and refuses to mark a settlement verified on the basis of a plausible quantity match alone.

## Build status

This branch is under active development. The deterministic evidence-decision core and its synthetic fixtures are present. **Do not claim live FalkorDB integration, external retailer validation, or financial recovery until verified.**

The graph is intended to supply all evidence paths to the decision tool, not merely visualize a decision already made elsewhere.

## Invariants

- Same quantities and SKU can yield different next actions because supplier evidence differs.
- Missing or contradictory evidence must not silently settle a claim.
- One unit of confirmed receipt capacity may not settle two obligations.
- Supplier attribution, retailer receipt confirmation, and retailer settlement approval are separate events.
- No autonomous payments, invoices, or external messages.

See CLAUDE.md and .claude/skills/evidence-first-build/SKILL.md before changes.

## Run local decision tests

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

## Source and limitations

This branch incorporates the EvidenceGap prototype developed Oct 15–16, 2026. Synthetic data only. A SQL model can reproduce the deterministic decisions; our graph-specific claim must be demonstrated with actual FalkorDB queries and a meaningful reduction in evidence investigation effort.

AI-assisted implementation is disclosed. No genuine supplier documents or access credentials are required.
