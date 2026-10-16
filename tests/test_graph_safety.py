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


@live
def test_two_consistent_supplier_statements_can_support_one_reviewed_settlement():
    """Multiple agreeing references are not the same as competing allocations."""
    from app.agent import investigate
    store=FalkorStore(graph_name="sahiaaya_ci_same_target_corroboration")
    store.seed("shortage_confirmed")
    store.write("""MATCH (r:Receipt {tenant:$tenant,id:$rid})
CREATE (d:Document {tenant:$tenant,id:'second-proof',ref:'SYNTHETIC-CORROBORATING-REFERENCE'})
CREATE (st:Statement {tenant:$tenant,id:'second-note',target_id:'SHORT-41',active:true})
CREATE (st)-[:ABOUT_RECEIPT]->(r)
CREATE (st)-[:SUPPORTED_BY]->(d)
RETURN st.id""",{"tenant":"demo_shop","rid":"RCP-52"})
    ctx=store.fetch("RCP-52")
    assert len([s for s in ctx.statements if s.active]) == 2
    assert investigate(ctx).status == "REVIEW_SETTLEMENT"
    assert store.commit("RCP-52","SHORT-41",2,ctx.receipt.version,0,
                        "corroborated-allocation","retailer-reviewed")
    assert len(store.history("RCP-52")) == 1
