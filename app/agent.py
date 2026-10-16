"""Evidence-gap decision policy. Model language cannot authorize a settlement."""
from .models import Context, Decision

def investigate(ctx: Context) -> Decision:
    r = ctx.receipt
    obs = tuple(sorted((o for o in ctx.obligations if o.outstanding_qty > 0), key=lambda x: x.id))
    ids = tuple(o.id for o in obs)
    def out(status, title, explanation, ask="", target=None, qty=0):
        return Decision(status, r.id, title, explanation, ask, ids, target, qty,
                        ctx.paths, ctx.tool_trace + ("rules.check_receipt_capacity",))
    if not r.unit_known:
        return out("UNKNOWN", "Unit conversion unverified",
                   "The pack unit and conversion are not established.",
                   f"Confirm the pack unit and SKU on {r.id}.")
    if r.original_qty < 0 or not 0 <= r.available_qty <= r.original_qty:
        return out("UNKNOWN", "Invalid receipt accounting",
                   "Recorded quantities violate the receipt-capacity invariant.",
                   "Correct the receipt with attributable evidence.")
    if not r.retailer_confirmed:
        return out("ASK_RETAILER", "Confirm received goods",
                   "Supplier claims do not establish physical receipt.",
                   f"Confirm the actual quantity of {r.sku} received on {r.id}.")
    if r.available_qty == 0:
        return out("ALREADY_ALLOCATED", "No unallocated goods",
                   "The receipt has no remaining capacity for a settlement.")
    if not obs:
        return out("NO_OPEN_CLAIMS", "No eligible obligation",
                   "No open same-supplier, same-SKU obligation was found.")
    active = tuple(s for s in ctx.statements if s.active)
    targets = {s.target_id for s in active}
    if len(targets) > 1:
        return out("DISPUTE", "Conflicting supplier evidence",
                   "Active statements point to competing claims.",
                   "Ask the supplier to reconcile references: " + ", ".join(s.id for s in active))
    if len(targets) == 1:
        target = next(iter(targets))
        eligible = next((o for o in obs if o.id == target), None)
        if eligible is None:
            return out("DISPUTE", "Invalid supplier attribution",
                       "The attributed obligation is not eligible for this receipt.",
                       "Request a valid claim and product reference.")
        if any(not s.proof_ref.strip() for s in active):
            return out("UNKNOWN", "Supplier evidence missing",
                       "Attribution lacks an identifiable supplier source.",
                       "Obtain the actual message or document reference.")
        qty = min(r.available_qty, eligible.outstanding_qty)
        return out("REVIEW_SETTLEMENT", "Review potential settlement",
                   f"Recorded evidence supports proposing {qty} unit(s) to {target}, not automatic closure.",
                   "Retailer must explicitly review and approve.", target, qty)
    if len(obs) == 1:
        return out("ASK_SUPPLIER", "Purpose of delivery unconfirmed",
                   "A supplier/SKU match is not proof that a claim was settled.",
                   f"Did goods on receipt {r.id} fulfil {obs[0].id}? Cite the reference.")
    return out("ASK_SUPPLIER", "Competing obligations need attribution",
               "The received units could plausibly fulfil several open obligations.",
               f"Which claim did receipt {r.id} fulfil: {', '.join(ids)}? Provide the supplier reference.")
