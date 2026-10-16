import pytest
from app.agent import investigate
from app.demo_data import scenario_context

@pytest.mark.parametrize(("scenario", "status", "target"), [
    ("ambiguous", "ASK_SUPPLIER", None),
    ("shortage_confirmed", "REVIEW_SETTLEMENT", "SHORT-41"),
    ("promotion_confirmed", "REVIEW_SETTLEMENT", "PROMO-17"),
    ("conflict", "DISPUTE", None),
    ("unknown_pack", "UNKNOWN", None),
    ("not_received", "ASK_RETAILER", None),
    ("wrong_target", "DISPUTE", None),
    ("single", "ASK_SUPPLIER", None),
    ("no_open", "NO_OPEN_CLAIMS", None),
])
def test_counterfactuals(scenario, status, target):
    decision = investigate(scenario_context(scenario))
    assert decision.status == status
    assert decision.suggested_obligation == target
    assert decision.risk == "review_required"

def test_same_quantities_different_evidence_changes_action():
    cases = [investigate(scenario_context(x))
             for x in ("ambiguous", "shortage_confirmed",
                       "promotion_confirmed", "conflict")]
    assert len({(x.status, x.suggested_obligation) for x in cases}) == 4
    assert all(x.receipt_id == "RCP-52" for x in cases)

def test_never_settles_automatically():
    for scenario in ("shortage_confirmed", "promotion_confirmed"):
        d = investigate(scenario_context(scenario))
        assert d.status == "REVIEW_SETTLEMENT"
        assert d.risk == "review_required"
