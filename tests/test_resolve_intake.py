"""FalkorDB-backed arbitrary synthetic case intake: separate from fixed demo fixtures."""
import json
import os
from pathlib import Path
import pytest
from app.resolve import CaseIn, ResolveStore, fingerprint, scheme_eligible

ROOT=Path(__file__).resolve().parents[1]
live=pytest.mark.skipif(os.getenv("RUN_FALKOR_TESTS")!="1", reason="Requires FalkorDB service")

def fixture(name):
    return json.loads((ROOT/"examples"/name).read_text(encoding="utf-8"))

def test_documented_terms_are_required():
    obj=fixture("fictional_two_delivery_case.json")
    obj["obligations"][1].pop("scheme_terms")
    with pytest.raises(ValueError,match="Promotion needs"):
        CaseIn.model_validate(obj)

def test_repeated_ids_rejected():
    obj=fixture("fictional_two_delivery_case.json")
    obj["receipts"][1]["id"]=obj["receipts"][0]["id"]
    with pytest.raises(ValueError, match="Duplicate receipt"):
        CaseIn.model_validate(obj)

def test_expired_scheme_fails_eligibility():
    obj=CaseIn.model_validate(fixture("fictional_second_supplier_case.json"))
    assert not scheme_eligible(obj.obligations[1])
    assert scheme_eligible(obj.obligations[0])

def test_order_of_json_properties_does_not_change_identity():
    obj=fixture("fictional_two_delivery_case.json")
    a=CaseIn.model_validate(obj)
    b=CaseIn.model_validate(dict(reversed(list(obj.items()))))
    assert fingerprint(a)==fingerprint(b)

@live
def test_unfamiliar_multi_receipt_history_and_idempotent_import():
    from app.graph import FalkorStore
    s=ResolveStore(FalkorStore(graph_name="sahiaaya_ci_resolve_intake"))
    data=CaseIn.model_validate(fixture("fictional_two_delivery_case.json"))
    assert s.import_case(data)["imported"]
    assert not s.import_case(data)["imported"]
    assert len(s.list_cases())==1
    first=s.investigate(data.case_id,"LATER_1")
    second=s.investigate(data.case_id,"LATER_2")
    assert {c["id"] for c in first["candidates"]}=={"SHORT_A","PROMO_B"}
    assert second["decision"]["status"]=="ASK_SUPPLIER"
    assert second["graph_trace"].count("POTENTIALLY_FULFILLS")==1
    with pytest.raises(ValueError,match="Case ID already"):
        revised=data.model_copy(update={"sku":"DIFFERENT"})
        s.import_case(revised)

@live
def test_second_supplier_and_scheme_are_distinct_and_falsifiable():
    from app.graph import FalkorStore
    s=ResolveStore(FalkorStore(graph_name="sahiaaya_ci_resolve_second"))
    a=CaseIn.model_validate(fixture("fictional_two_delivery_case.json"))
    b=CaseIn.model_validate(fixture("fictional_second_supplier_case.json"))
    s.import_case(a)
    s.import_case(b)
    state=s.investigate(b.case_id,"RICE_11")
    assert [c["id"] for c in state["candidates"]]==["SHORT_R1"]
    assert state["decision"]["status"]=="ASK_SUPPLIER"
    assert state["sku"]=="RICE1KG"
    # The expired promotion is not even a candidate, despite identical product.
    with pytest.raises(ValueError):
        s.attribute(b.case_id,"RICE_11","PROMO_INVALID","fictional_ref",0)

@live
def test_independent_delivery_allocation_guard_and_persistence():
    from app.graph import FalkorStore
    s=ResolveStore(FalkorStore(graph_name="sahiaaya_ci_resolve_review"))
    case=CaseIn.model_validate(fixture("fictional_two_delivery_case.json"))
    s.import_case(case)
    rid="LATER_2"
    first=s.investigate(case.case_id,rid)
    assert first["decision"]["status"]=="ASK_SUPPLIER"
    with pytest.raises(ValueError):
        s.approve(case.case_id,rid,"PROMO_B",2,0,0)
    proposed=s.attribute(case.case_id,rid,"PROMO_B","fictional_supplier_delivery_note",0)
    assert proposed["decision"]["status"]=="REVIEW_SETTLEMENT"
    assert proposed["decision"]["suggested_qty"]==2
    reviewed=s.approve(case.case_id,rid,"PROMO_B",2,1,0)
    assert reviewed["receipt"]["available_qty"]==0
    assert reviewed["decision"]["status"]=="ALREADY_ALLOCATED"
    assert reviewed["allocations"][0]["qty"]==2
    assert s.investigate(case.case_id,"LATER_1")["receipt"]["available_qty"]==1
    with pytest.raises(ValueError):
        s.approve(case.case_id,rid,"SHORT_A",2,1,0)
    assert len(s.investigate(case.case_id,rid)["allocations"])==1

@live
def test_unit_mismatch_is_explicitly_unknown():
    from app.graph import FalkorStore
    s=ResolveStore(FalkorStore(graph_name="sahiaaya_ci_resolve_unit"))
    obj=fixture("fictional_two_delivery_case.json")
    obj["case_id"]="shop_alpha_unknown_units"
    obj["receipts"][1]["unit"]="carton"
    c=CaseIn.model_validate(obj)
    s.import_case(c)
    got=s.investigate(c.case_id,"LATER_2")
    assert got["decision"]["status"]=="UNKNOWN_UNIT"
    assert got["candidates"]==[]
