"""Direct graph-write adversarial tests. These must not rely on the HTTP guard."""
import os
import pytest
from app.graph import FalkorStore

live=pytest.mark.skipif(os.getenv("RUN_FALKOR_TESTS")!="1",reason="Live FalkorDB required")

@live
def test_conflicting_supplier_statements_block_direct_settlement():
    store=FalkorStore(graph_name="sahiaaya_ci_conflict_guard")
    store.seed("conflict")
    assert not store.commit("RCP-52","SHORT-41",2,0,0,"must-not-settle","retailer-review")
    assert store.history("RCP-52")==[]

@live
def test_unknown_pack_cannot_be_overridden_by_direct_allocation():
    store=FalkorStore(graph_name="sahiaaya_ci_unknown_unit_guard")
    store.seed("unknown_pack")
    store.clarify("RCP-52","SHORT-41","SYNTHETIC-SUPPLIER-REFERENCE")
    ctx=store.fetch("RCP-52")
    assert not store.commit("RCP-52","SHORT-41",2,ctx.receipt.version,0,
                            "must-not-settle","retailer-review")

@live
def test_graph_provenance_is_traceable_and_wrong_tenant_rejected():
    store=FalkorStore(graph_name="sahiaaya_ci_provenance")
    store.seed("ambiguous")
    ctx=store.fetch("RCP-52")
    assert "HistoricalSource:" in " ".join(ctx.paths["SHORT-41"])
    assert "Document:" in " ".join(ctx.paths["PROMO-17"])
    with pytest.raises(KeyError):
        store.fetch("RCP-52",tenant="unrelated_shop")
