# SahiAaya Resolve — new supplier history, without editing code

This is a **local, synthetic-only** FalkorDB workflow, not a publicly hosted retailer service.

## What is new

Instead of requiring one hardcoded `RCP-52` scenario, the local app can now create an independent fictional case with one supplier and SKU, multiple outstanding claims and **multiple later receipts**. A new receipt's candidate obligations come from graph relationships created at ingestion; they are not manually listed in the UI.

On **http://localhost:8000**, scroll to **Try your own delivery history**:

1. Enter fictional supplier/SKU and an earlier billed-versus-observed quantity. The shortage is computed automatically; edit promotional eligibility thresholds and two later delivery quantities.
2. Click **Create case & investigate**. The service validates the structured records and writes a case-specific graph.
3. Select `LATER_A` or `LATER_B`. The agent follows `ResolveCase → ResolveReceipt → POTENTIALLY_FULFILLS → ResolveObligation → ResolveDocument` and reports possible candidates.
4. Record a **fictional** supplier attribution. The UI reveals only a *proposed* allocation.
5. Click **Retailer review & record allocation** to commit the bounded quantity. The other receipt and unallocated claims remain unchanged.
6. Copy the case ID, refresh, and **Reopen graph case** to verify database persistence.

To check a truly different dataset, upload `examples/fictional_second_supplier_case.json` through the same form. Its promotional claim has an **expired eligibility window**, so the API explicitly returns `SCHEME_NOT_ELIGIBLE` instead of silently closing the promotion.

## JSON import contract

```json
{
  "synthetic_only": true,
  "case_id": "fictional_case_unique",
  "supplier_id": "fictional_wholesaler",
  "sku": "SOAP100",
  "unit": "piece",
  "obligations": [
    {"id":"OLD_SHORT","kind":"shortage","qty":3,"created_on":"2026-10-01","document_ref":"fictional_invoice_1"},
    {"id":"OLD_OFFER","kind":"promotion","qty":2,"created_on":"2026-10-02","earned_on":"2026-10-02","document_ref":"fictional_terms",
      "scheme_terms":{"valid_from":"2026-09-01","valid_to":"2026-10-31","min_purchase":10,"purchase_qty":12}}
  ],
  "receipts": [
    {"id":"LATER_1","received_on":"2026-10-08","qty":1,"unit":"piece","retailer_confirmed":true,"document_ref":"fictional_delivery_A"},
    {"id":"LATER_2","received_on":"2026-10-12","qty":2,"unit":"piece","retailer_confirmed":true,"document_ref":"fictional_delivery_B"}
  ]
}
```

Limits: up to 20 obligations and 20 receipts per case, exact unit matching only (no unverified carton-to-piece conversion), and purchase thresholds and offer dates required for promotional obligations. Existing case IDs can be re-imported only with byte-equivalent normalized content; an altered history conflicts instead of minting additional quantities.

## Local endpoints

- `POST /api/resolve/cases` — import a new synthetic case, reject duplicates or invalid scheme terms
- `GET /api/resolve/cases` — list fictional cases
- `GET /api/resolve/cases/{case_id}/receipts` — retrieve stored receipts after refresh
- `GET /api/resolve/cases/{case_id}/receipts/{receipt_id}` — perform fresh Cypher investigation
- `POST /api/resolve/cases/{case_id}/receipts/{receipt_id}/attribute` — record a simulated supplier response with optimistic receipt version
- `POST /api/resolve/cases/{case_id}/receipts/{receipt_id}/approve` — reviewer-confirmed, version-checked quantity allocation

All writes require the local `ALLOW_DEMO_MUTATIONS=1` environment setting. The Docker configuration binds the API and FalkorDB to localhost. **Never expose these unauthenticated endpoints publicly.**

The public Vercel project remains a browser-only synthetic demonstration. Its new-case action is deliberately disabled; it cannot claim it wrote real graph data.

## What the results do — and do not — prove

- Incoming structured records can be transformed into actual graph nodes and scoped edges.
- An unrelated or expired scheme is excluded with an explicit reason.
- Graph-based candidate discovery drives the next action.
- A supplier attribution needs an identifiable *fictional* source reference, and the retailer still approves.
- A reviewed quantity cannot be allocated beyond its remaining eligible capacity in the documented single-writer demo.
- No real supplier verified the documents, no physical receipt was independently authenticated, and no credit or money was recovered.
- SQL plus equivalent rules can make the same deterministic decisions; no speed, accuracy or adoption advantage is claimed without a measured baseline.

## Verification

```powershell
docker compose up -d --build
docker compose exec -e RUN_FALKOR_TESTS=1 app pytest tests/test_resolve_intake.py -v
```

GitHub Actions also runs a real browser test in the FalkorDB service job: manual-case creation, attribution, reviewer approval, reloading, second delivery and unknown JSON import.

**Minimum judge demo:** show initial preset in 50 seconds, then change a fictional new receipt quantity, import it, retrieve cross-delivery obligations, attribute one receipt, approve it, and reopen the case. Show the incorrect promotion excluded in the second fixture as a negative control.
