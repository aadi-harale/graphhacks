"""Integration tests run ONLY with RUN_FALKOR_TESTS=1 and live FalkorDB."""
import os
import pytest
from app.agent import investigate
from app.graph import FalkorStore

live=pytest.mark.skipif(os.getenv("RUN_FALKOR_TESTS")!="1",
                        reason="Requires live FalkorDB service and client")

@live
def test_graph_evidence_changes_action_and_preserves_open_claim():
    s=FalkorStore(graph_name="sahiaaya_ci_evidence")
    s.seed("ambiguous")
    ctx=s.fetch("RCP-52")
    assert set(o.id for o in ctx.obligations)=={"SHORT-41","PROMO-17"}
    assert investigate(ctx).status=="ASK_SUPPLIER"
    s.clarify("RCP-52","PROMO-17","SYNTHETIC-SUPPLIER-NOTE")
    ctx=s.fetch("RCP-52")
    d=investigate(ctx)
    assert d.status=="REVIEW_SETTLEMENT" and d.suggested_obligation=="PROMO-17"
    assert s.commit("RCP-52","PROMO-17",2,ctx.receipt.version,0,
                    "allocation-ci-1","retailer-confirmation")
    after=s.fetch("RCP-52")
    assert after.receipt.available_qty==0
    assert next(o for o in after.obligations if o.id=="SHORT-41").outstanding_qty==2
    assert len(s.history("RCP-52"))==1

@live
def test_unattributed_allocation_is_blocked():
    s=FalkorStore(graph_name="sahiaaya_ci_unattributed")
    s.seed("ambiguous")
    assert not s.commit("RCP-52","SHORT-41",2,0,0,"invalid","review")
    assert s.history("RCP-52")==[]

@live
def test_stale_retailer_approval_fails_after_supplier_correction():
    s=FalkorStore(graph_name="sahiaaya_ci_stale")
    s.seed("ambiguous")
    s.clarify("RCP-52","SHORT-41","SYNTHETIC-SUPPLIER-1")
    old=s.fetch("RCP-52").receipt.version
    s.clarify("RCP-52","PROMO-17","SYNTHETIC-SUPPLIER-2")
    assert not s.commit("RCP-52","SHORT-41",2,old,0,"stale","review")
    assert s.history("RCP-52")==[]
