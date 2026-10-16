"""Fictional and explicitly synthetic supplier evidence."""
from .models import Context, Obligation, Statement, Receipt

TENANT = "demo_shop"
SUPPLIER = "supplier_sharma_demo"
SKU = "SOAP-100G"
SHORT = Obligation("SHORT-41", SKU, "short_delivery", 2, 2,
                   proof_ref="invoice-41:merchant-count")
PROMO = Obligation("PROMO-17", SKU, "promotional_entitlement", 2, 2,
                   proof_ref="offer-17:documented-terms")
PROMISES = {
    SHORT.id: ("promise-41:replacement-next-delivery",),
    PROMO.id: ("offer-17:two-promo-units-due",),
}

def scenario_context(scenario: str = "ambiguous") -> Context:
    known = {"ambiguous", "shortage_confirmed", "promotion_confirmed",
             "conflict", "unknown_pack", "not_received", "wrong_target",
             "single", "no_open"}
    if scenario not in known:
        raise ValueError("Unknown scenario")
    obligations = () if scenario == "no_open" else (SHORT,) if scenario == "single" else (SHORT, PROMO)
    receipt = Receipt("RCP-52", SUPPLIER, SKU, 2, 2, scenario != "not_received",
                      "photo-52:retailer-count", unit_known=scenario != "unknown_pack")
    statements = []
    if scenario in {"shortage_confirmed", "conflict"}:
        statements.append(Statement("supplier-note-71", "SHORT-41", "supplier-message-71"))
    if scenario in {"promotion_confirmed", "conflict"}:
        statements.append(Statement("supplier-note-72", "PROMO-17", "supplier-message-72"))
    if scenario == "wrong_target":
        statements.append(Statement("supplier-note-73", "OTHER-STORE-CLAIM", "supplier-message-73"))
    paths = {o.id: (f"Receipt:{receipt.id}", f"Supplier:{SUPPLIER}", f"SKU:{SKU}",
                    f"Obligation:{o.id}", f"Proof:{o.proof_ref}") for o in obligations}
    return Context(receipt, obligations, tuple(statements), dict(PROMISES),
                   paths, ("synthetic.fixture.loaded",))
