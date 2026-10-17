"""Source-evidence counterfactuals on an actual FalkorDB instance.

These are deterministic policy+MCP transport tests, not real model tests.
Identical physical receipt quantities MUST not imply identical decisions.
"""
import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from app.resolve import CaseIn, ResolveStore
from app.graph import FalkorStore
from app.track1_mcp_loop import run_agent_mcp

live=pytest.mark.skipif(os.getenv("RUN_FALKOR_TESTS")!="1",reason="Requires live FalkorDB")
ROOT=Path(__file__).resolve().parents[1]

class ToolChoiceClient:
    """Test-double deliberately labeled as INJECTED, not a live LLM."""
    def __init__(self,tools):
        self.calls=list(tools)+[None]
        self.chat=NS(completions=NS(create=self.complete))
    def complete(self,**kwargs):
        name=self.calls.pop(0)
        if name is None:
            return NS(choices=[NS(message=NS(tool_calls=None,content="Inspected source-linked graph facts."))])
        arguments=(
          '{"action":"request_supplier"}' if name=="create_followup_draft"
          else '{"claim_id":"SHORT_A"}' if name=="inspect_cross_delivery"
          else "{}")
        return NS(choices=[NS(message=NS(tool_calls=[
            NS(id="tool-"+name,function=NS(name=name,arguments=arguments))],content=None))])

def input_case(identifier,fixture="fictional_two_delivery_case.json"):
    data=json.loads((ROOT/"examples"/fixture).read_text(encoding="utf-8"))
    data["case_id"]=identifier
    return CaseIn.model_validate(data)

def real_store():
    return ResolveStore(FalkorStore(graph_name="sahiaaya_resolve"))

def run_transported(case_id,receipt_id,tools):
    return asyncio.run(run_agent_mcp(case_id,receipt_id,
        "Find connected supplier promises and explain what remains uncertain.",
        client=ToolChoiceClient(tools)))

@live
def test_same_quantity_changes_justified_next_step_after_supplier_attribution(monkeypatch):
    monkeypatch.setenv("ALLOW_DEMO_MUTATIONS","1")
    store=real_store()
    case=input_case("ci_counterfactual_provenance")
    store.import_case(case)
    before=store.investigate(case.case_id,"LATER_2")
    assert before["receipt"]["qty"]==2 and before["decision"]["status"]=="ASK_SUPPLIER"
    trace_before=run_transported(case.case_id,"LATER_2",[
        "list_case_receipts","investigate_receipt","trace_claim_evidence",
        "inspect_cross_delivery","create_followup_draft"])
    assert trace_before["model_execution"]=="injected_client"
    assert trace_before["draft"]["action"]=="request_supplier"
    assert trace_before["tool_trace"][1]["result"]["decision"]["status"]=="ASK_SUPPLIER"
    assert {x["obligation"] for x in trace_before["evidence_paths"]}=={"SHORT_A","PROMO_B"}
    assert all("result" in step for step in trace_before["tool_trace"])
    store.attribute(case.case_id,"LATER_2","PROMO_B","fictional_supplier_promo_ref",0)
    after=store.investigate(case.case_id,"LATER_2")
    assert after["receipt"]["qty"]==before["receipt"]["qty"]
    assert {x["id"] for x in after["candidates"]}=={x["id"] for x in before["candidates"]}
    assert after["decision"]["status"]=="REVIEW_SETTLEMENT"
    assert after["decision"]["suggested_claim"]=="PROMO_B"
    trace_after=run_transported(case.case_id,"LATER_2",[
        "investigate_receipt","trace_claim_evidence"])
    assert trace_after["authoritative_decision"]["status"]=="REVIEW_SETTLEMENT"
    assert trace_after["tool_trace"][0]["result"]["statements"][0]["target_id"]=="PROMO_B"
    assert trace_before["tool_trace"][0]["tool"]!=trace_after["tool_trace"][0]["tool"]

@live
def test_conflicting_and_ineligible_source_data_block_settlement(monkeypatch):
    monkeypatch.setenv("ALLOW_DEMO_MUTATIONS","1")
    store=real_store()
    case=input_case("ci_track1_conflict_source")
    store.import_case(case)
    store.attribute(case.case_id,"LATER_2","PROMO_B","fictional_promo_ref",0)
    store.write("""MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt {id:$receipt})
CREATE (s:ResolveStatement {id:$id,target_id:'SHORT_A',reference:'fictional_conflicting_ref',active:true})
CREATE (s)-[:ABOUT]->(r) RETURN s.id""",
        {"tenant":"demo_shop","case":case.case_id,"receipt":"LATER_2","id":"counter_conflict"})
    finding=store.investigate(case.case_id,"LATER_2")
    assert finding["decision"]["status"]=="DISPUTE"
    assert finding["receipt"]["qty"]==2
    with pytest.raises(ValueError):
        store.approve(case.case_id,"LATER_2","PROMO_B",2,1,0)
    conflict_trace=run_transported(case.case_id,"LATER_2",[
        "investigate_receipt","trace_claim_evidence"])
    assert conflict_trace["authoritative_decision"]["status"]=="DISPUTE"
    assert len(conflict_trace["tool_trace"][0]["result"]["statements"])==2

    data=json.loads((ROOT/"examples"/"fictional_second_supplier_case.json").read_text())
    data["case_id"]="ci_track1_only_expired_promo"
    data["obligations"]=[data["obligations"][1]]
    expired=CaseIn.model_validate(data)
    store.import_case(expired)
    result=store.investigate(expired.case_id,"RICE_11")
    assert result["receipt"]["qty"]==4
    assert result["decision"]["status"]=="NEEDS_REVIEW"
    assert result["candidates"]==[]
    assert result["excluded_claims"][0]["reason"]=="SCHEME_NOT_ELIGIBLE"
    expired_trace=run_transported(expired.case_id,"RICE_11",[
        "investigate_receipt","trace_claim_evidence"])
    assert expired_trace["authoritative_decision"]["status"]=="NEEDS_REVIEW"
    assert expired_trace["evidence_paths"]==[]

@live
def test_repeated_receipt_allocation_stays_blocked(monkeypatch):
    monkeypatch.setenv("ALLOW_DEMO_MUTATIONS","1")
    store=real_store()
    original=json.loads((ROOT/"examples"/"fictional_two_delivery_case.json").read_text())
    original["case_id"]="ci_track1_allocation_replay"
    original["obligations"]=[original["obligations"][0]]
    original["receipts"]=[original["receipts"][1]]
    case=CaseIn.model_validate(original)
    store.import_case(case)
    store.attribute(case.case_id,"LATER_2","SHORT_A","fictional_replacement_confirmation",0)
    approved=store.approve(case.case_id,"LATER_2","SHORT_A",2,1,0)
    assert approved["decision"]["status"]=="ALREADY_ALLOCATED"
    assert approved["receipt"]["qty"]==2 and approved["receipt"]["available_qty"]==0
    with pytest.raises(ValueError):
        store.approve(case.case_id,"LATER_2","SHORT_A",2,2,1)
    assert len(store.investigate(case.case_id,"LATER_2")["allocations"])==1
    trace=run_transported(case.case_id,"LATER_2",[
        "investigate_receipt","trace_claim_evidence"])
    assert trace["authoritative_decision"]["status"]=="ALREADY_ALLOCATED"

def test_undocumented_promotion_rejected_by_input_schema():
    from pydantic import ValidationError
    data=json.loads((ROOT/"examples"/"fictional_two_delivery_case.json").read_text())
    data["obligations"][1].pop("scheme_terms")
    with pytest.raises(ValidationError,match="Promotion needs dated"):
        CaseIn.model_validate(data)
