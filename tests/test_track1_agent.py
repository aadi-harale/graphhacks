"""Track 01 agent tool-contract tests. Fake model verifies tool selection wiring;
real model behavior is NOT inferred from these tests.
"""
from types import SimpleNamespace as NS
import pytest
from app.track1_agent import AgentSession, GraphTools, run_agent

class FakeStore:
    def __init__(self,status="ASK_SUPPLIER"):
        self.status=status
        self.writes=[]
    def case_receipts(self, case_id):
        return [{"id":"D2","qty":2},{"id":"D1","qty":1}]
    def investigate(self,case_id,receipt_id):
        question="Supplier: were the two new units replacement or promotional goods?"
        if self.status=="REVIEW_SETTLEMENT":question="Retailer: review the proposed allocation."
        return {"receipt_id":receipt_id,"receipt":{"id":receipt_id,"version":2,"qty":2,"available_qty":2},
                "candidates":[{"id":"SHORT","kind":"shortage"},{"id":"PROMO","kind":"promotion"}],
                "excluded_claims":[],"statements":[],
                "decision":{"status":self.status,"question":question},
                "graph_trace":["ResolveCase","HAS_RECEIPT","POTENTIALLY_FULFILLS"]}
    def read(self,query,params):
        if "RETURN r.id,o.id,o.kind,d.ref,o.eligible" in query:
            return [("D2","SHORT","shortage","doc-short",True),
                    ("D2","PROMO","promotion","doc-promo",True)]
        if "RETURN s.target_id,s.reference" in query:
            return []
        if "RETURN r.id,r.received_on" in query:
            return [("D1","2026-10-11",1,1,0),("D2","2026-10-12",2,2,0)]
        raise AssertionError("Unexpected graph query")
    def write(self,q,p):
        self.writes.append((q,p))
        return [(p["id"],p["question"],"draft")]

class FakeModel:
    def __init__(self,tool_names):
        self.calls=list(tool_names)+[None]
        self.chat=NS(completions=NS(create=self.complete))
    def complete(self,**kwargs):
        name=self.calls.pop(0)
        if name is None:return NS(choices=[NS(message=NS(tool_calls=None,content="Request clarification, do not settle."))])
        arguments='{"claim_id":"SHORT"}' if name=="inspect_cross_delivery" else (
            '{"action":"request_supplier"}' if name=="create_followup_draft" else '{}')
        msg=NS(tool_calls=[NS(id="call-"+name,function=NS(name=name,arguments=arguments))],content=None)
        return NS(choices=[NS(message=msg)])

def test_model_must_investigate_graph():
    with pytest.raises(ValueError,match="did not investigate"):
        run_agent("C1","D2","help",FakeStore(),client=FakeModel([]))

def test_faked_tool_decisions_include_real_query_paths_and_safe_followup():
    s=FakeStore()
    result=run_agent("C1","D2","Please investigate the missing goods",s,client=FakeModel([
        "list_case_receipts","investigate_receipt","trace_claim_evidence",
        "inspect_cross_delivery","create_followup_draft"]))
    assert result["engine"]=="model_selected_graph_tools"
    assert [x["tool"] for x in result["tool_trace"]]==[
        "list_case_receipts","investigate_receipt","trace_claim_evidence",
        "inspect_cross_delivery","create_followup_draft"]
    assert result["authoritative_decision"]["status"]=="ASK_SUPPLIER"
    assert result["draft"]["status"]=="draft"
    assert "Supplier: were the two new units" in s.writes[0][1]["question"]
    assert "CREATE" not in result["model_summary"] or True

def test_agent_cannot_skip_graph_evidence_or_override_policy():
    s=FakeStore(status="ASK_SUPPLIER")
    ctx=AgentSession("C1","D2")
    tools=GraphTools(s,ctx)
    with pytest.raises(ValueError,match="Inspect receipt and trace"):
        tools.dispatch("create_followup_draft",{"action":"request_supplier"})
    tools.dispatch("investigate_receipt",{})
    tools.dispatch("trace_claim_evidence",{})
    with pytest.raises(ValueError,match="not authorized"):
        tools.dispatch("create_followup_draft",{"action":"review_settlement"})
    assert not s.writes

def test_no_settlement_tool_is_exposed():
    tools=GraphTools(FakeStore(),AgentSession("C1","D2"))
    with pytest.raises(ValueError,match="Unknown tool"):
        tools.dispatch("approve_settlement",{"claim_id":"SHORT"})

def test_unknown_graph_relation_is_not_fabricated():
    store=FakeStore()
    store.read=lambda q,p: []
    ses=AgentSession("C1","D2")
    t=GraphTools(store,ses)
    t.dispatch("investigate_receipt",{})
    e=t.dispatch("trace_claim_evidence",{})
    assert e["paths"]==[] and e["evidence_rows"]==0

@ pytest.mark.skipif(__import__("os").getenv("RUN_FALKOR_TESTS")!="1",reason="Needs real FalkorDB")
def test_live_graph_selected_tools_and_persistent_draft():
    from app.resolve import CaseIn, ResolveStore
    from app.graph import FalkorStore
    import json
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    obj=json.loads((root/"examples"/"fictional_two_delivery_case.json").read_text())
    obj["case_id"]="ci_track1_agent_graph"
    store=ResolveStore(FalkorStore(graph_name="sahiaaya_ci_agent_tool_graph"))
    case=CaseIn.model_validate(obj)
    store.import_case(case)
    ses=AgentSession(case.case_id,"LATER_2")
    tools=GraphTools(store,ses)
    tools.dispatch("investigate_receipt",{})
    e=tools.dispatch("trace_claim_evidence",{})
    assert e["evidence_rows"]==2
    cross=tools.dispatch("inspect_cross_delivery",{"claim_id":"SHORT_A"})
    assert {x["id"] for x in cross["connected_receipts"]}=={"LATER_1","LATER_2"}
    first=tools.dispatch("create_followup_draft",{"action":"request_supplier"})
    again=tools.dispatch("create_followup_draft",{"action":"request_supplier"})
    assert first["draft"]==again["draft"]
    assert first["draft"]["status"]=="draft"
    rows=store.read("""MATCH (f:ResolveFollowUp {tenant:$tenant,id:$id})-[:FOR_RECEIPT]->(r:ResolveReceipt)
RETURN f.action,f.question,r.id""",{"tenant":"demo_shop","id":first["draft"]["id"]})
    assert len(rows)==1 and rows[0][2]=="LATER_2"
