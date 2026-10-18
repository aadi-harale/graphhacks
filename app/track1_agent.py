"""Track 01 graph investigation agent.

The model selects *bounded* tools; FalkorDB returns the facts; deterministic
business rules enforce all outcomes. This module NEVER sends supplier messages
or approves settlements. The only write is a local draft follow-up.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import json
import os
from typing import Any
from .demo_data import TENANT

TOOL_SCHEMAS = [
  {"type":"function","function":{"name":"list_case_receipts","description":"Find all receipts on this synthetic case, including earlier deliveries.","parameters":{"type":"object","properties":{},"additionalProperties":False}}},
  {"type":"function","function":{"name":"investigate_receipt","description":"Retrieve FalkorDB-connected obligations and the authoritative safety decision for the selected receipt.","parameters":{"type":"object","properties":{},"additionalProperties":False}}},
  {"type":"function","function":{"name":"trace_claim_evidence","description":"Follow the receipt -> candidate obligation -> source document links and supplier statements. Do not invent links.","parameters":{"type":"object","properties":{},"additionalProperties":False}}},
  {"type":"function","function":{"name":"inspect_cross_delivery","description":"Traverse all other receipts connected to this claim, including already allocated quantities.","parameters":{"type":"object","properties":{"claim_id":{"type":"string"}},"required":["claim_id"],"additionalProperties":False}}},
  {"type":"function","function":{"name":"reconcile_ledger","description":"Reconcile the WHOLE supplier ledger with FalkorDB algo.maxFlow: which deliveries are forced onto which claims, which are ambiguous, and what is still owed. Use when several deliveries or claims are open.","parameters":{"type":"object","properties":{},"additionalProperties":False}}},
  {"type":"function","function":{"name":"create_followup_draft","description":"Create a bounded internal next-action draft linked to the receipt; NEVER sends to supplier or settles a claim.","parameters":{"type":"object","properties":{"action":{"type":"string","enum":["request_supplier","request_retailer","review_settlement","request_terms"]}},"required":["action"],"additionalProperties":False}}},
]

@dataclass
class AgentSession:
    case_id: str
    receipt_id: str
    inspected: bool = False
    evidence_traced: bool = False
    decision: dict | None = None
    evidence_paths: list = field(default_factory=list)
    trace: list = field(default_factory=list)
    draft: dict | None = None
    ledger: dict | None = None


class GraphTools:
    def __init__(self, resolve_store, session: AgentSession):
        self.store=resolve_store
        self.session=session

    def dispatch(self, name: str, args: dict) -> dict:
        allowed={x["function"]["name"] for x in TOOL_SCHEMAS}
        if name not in allowed:
            raise ValueError("Unknown tool")
        args=args or {}
        required=next(x["function"]["parameters"] for x in TOOL_SCHEMAS if x["function"]["name"]==name)
        if set(args)-set(required["properties"]):
            raise ValueError("Unsupported tool arguments")
        if set(required.get("required",[]))-set(args):
            raise ValueError("Missing required tool arguments")
        func=getattr(self,name)
        result=func(**args)
        self.session.trace.append({"tool":name,"args":args,"result_kind":result.get("kind","information"),
                                   "evidence_rows":result.get("evidence_rows",0)})
        return result

    def list_case_receipts(self) -> dict:
        return {"kind":"graph_result","receipts":self.store.case_receipts(self.session.case_id)}

    def investigate_receipt(self) -> dict:
        s=self.store.investigate(self.session.case_id,self.session.receipt_id)
        self.session.inspected=True
        self.session.decision=s["decision"]
        return {"kind":"authoritative_decision","receipt_id":s["receipt_id"],
                "receipt":s["receipt"],"candidates":s["candidates"],
                "excluded_claims":s["excluded_claims"],"statements":s["statements"],
                "decision":s["decision"],"graph_trace":s["graph_trace"]}

    def trace_claim_evidence(self) -> dict:
        if not self.session.inspected:raise ValueError("Investigate receipt first")
        p={"tenant":TENANT,"case":self.session.case_id,"receipt":self.session.receipt_id}
        rows=self.store.read("""MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt {id:$receipt})
MATCH (r)-[:POTENTIALLY_FULFILLS]->(o:ResolveObligation)-[:SUPPORTED_BY]->(d:ResolveDocument)
RETURN r.id,o.id,o.kind,d.ref,o.eligible ORDER BY o.id""",p)
        supplier=self.store.read("""MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt {id:$receipt})
MATCH (s:ResolveStatement {active:true})-[:ABOUT]->(r)
RETURN s.target_id,s.reference ORDER BY s.target_id""",p)
        self.session.evidence_traced=True
        self.session.evidence_paths=[{"receipt":x[0],"obligation":x[1],"document":x[3]} for x in rows]
        return {"kind":"graph_paths","evidence_rows":len(rows),
                "paths":[{"receipt":x[0],"obligation":x[1],"type":x[2],
                          "document":x[3],"eligible":x[4]} for x in rows],
                "supplier_statements":[{"claim":x[0],"reference":x[1]} for x in supplier]}

    def inspect_cross_delivery(self,claim_id: str) -> dict:
        if not self.session.inspected:raise ValueError("Investigate receipt first")
        p={"tenant":TENANT,"case":self.session.case_id,"claim":claim_id}
        rows=self.store.read("""MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_OBLIGATION]->(o:ResolveObligation {id:$claim})
MATCH (c)-[:HAS_RECEIPT]->(r:ResolveReceipt)-[:POTENTIALLY_FULFILLS]->(o)
OPTIONAL MATCH (a:ResolveAllocation)-[:FROM]->(r)
OPTIONAL MATCH (a)-[:SETTLES]->(o)
RETURN r.id,r.received_on,r.qty,r.available,coalesce(sum(a.qty),0)
ORDER BY r.received_on,r.id""",p)
        return {"kind":"graph_paths","claim_id":claim_id,"evidence_rows":len(rows),
                "connected_receipts":[{"id":r[0],"date":r[1],"received":r[2],
                                       "unallocated":r[3],"used_for_claim":r[4]} for r in rows]}

    def reconcile_ledger(self) -> dict:
        from .ledger import LedgerReconciler
        r=LedgerReconciler(self.store).reconcile(self.session.case_id)
        self.session.ledger=r
        return {"kind":"graph_algorithm","engine":r["engine"],"status":r["status"],
                "evidence_rows":len(r["proposals"])+len(r["ambiguous"]),
                "max_settleable_units":r["max_settleable_units"],"forced_units":r["forced_units"],
                "ambiguous_units":r["ambiguous_units"],"proposals":r["proposals"],
                "ambiguous":r["ambiguous"],"obligations":r["obligations"],
                "blocked_receipts":r["blocked_receipts"],"supplier_question":r["supplier_question"],
                "note":"Forced proposals still need the retailer's approval. Nothing was settled."}

    def create_followup_draft(self,action: str) -> dict:
        if not self.session.inspected or not self.session.evidence_traced:
            raise ValueError("Inspect receipt and trace evidence before drafting an action")
        current=self.store.investigate(self.session.case_id,self.session.receipt_id)
        decision=current["decision"]
        mapping={"ASK_SUPPLIER":"request_supplier","DISPUTE":"request_supplier",
                 "ASK_RETAILER":"request_retailer","UNKNOWN_UNIT":"request_retailer",
                 "NEEDS_REVIEW":"request_terms","REVIEW_SETTLEMENT":"review_settlement"}
        safe=mapping.get(decision["status"])
        if safe is None or action!=safe:
            raise ValueError("Action not authorized by current graph evidence")
        # The question is fixed by the checked policy, not model-generated prose.
        version=current["receipt"]["version"]
        raw=f"{self.session.case_id}|{self.session.receipt_id}|{version}|{action}"
        draft_id="followup-"+hashlib.sha256(raw.encode()).hexdigest()[:24]
        p={"tenant":TENANT,"case":self.session.case_id,"receipt":self.session.receipt_id,
           "id":draft_id,"version":version,"action":action,
           "question":decision["question"]}
        rows=self.store.write("""MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt {id:$receipt,version:$version})
MERGE (f:ResolveFollowUp {tenant:$tenant,id:$id})
ON CREATE SET f.action=$action,f.question=$question,f.status='draft',f.source_version=$version
MERGE (f)-[:FOR_RECEIPT]->(r)
RETURN f.id,f.question,f.status""",p)
        if not rows:raise ValueError("Receipt changed while drafting")
        self.session.draft={"id":rows[0][0],"question":rows[0][1],
                            "status":rows[0][2],"action":action}
        return {"kind":"internal_draft","draft":self.session.draft,
                "note":"Draft only. Not sent, not approved, no allocation."}


SYSTEM_PROMPT = """You are SahiAaya's evidence investigator for a fictional retailer. Your job is to use graph tools to investigate a given receipt across connected obligations and earlier deliveries.
Use investigate_receipt and trace_claim_evidence before creating any action. Call inspect_cross_delivery when claims compete or previous deliveries may matter. Call reconcile_ledger to see the whole supplier ledger: it reports which deliveries the graph forces onto which claims and which remain ambiguous. Only forced units may be described as settleable, and only after the retailer approves. Never invent supplier facts, source references or Cypher. NEVER imply a supplier was contacted or a settlement was completed. Create at most one safe internal followup draft when evidence permits. The deterministic graph policy, not your prose, decides whether settlement can be proposed. If facts are missing, state what is unknown. Keep final answer short and merchant-friendly."""

def run_agent(case_id: str, receipt_id: str, query: str, store, client=None,
              model: str | None=None, max_rounds: int=7) -> dict:
    """Tool-choice is performed by the model. Requires a real configured model client.
    Tests inject a fake client but cannot establish model quality or adoption.
    """
    if client is None:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("Set OPENAI_API_KEY to enable real agent tool selection")
        from openai import OpenAI
        client=OpenAI()
    name=model or os.getenv("SAHIAAYA_AGENT_MODEL","gpt-4o-mini")
    sess=AgentSession(case_id,receipt_id)
    tools=GraphTools(store,sess)
    messages=[{"role":"system","content":SYSTEM_PROMPT},
              {"role":"user","content":f"Case {case_id}, receipt {receipt_id}. {query[:280]}"}]
    for _ in range(max_rounds):
        answer=client.chat.completions.create(model=name,messages=messages,
                            tools=TOOL_SCHEMAS,tool_choice="auto",temperature=0)
        msg=answer.choices[0].message
        calls=msg.tool_calls or []
        if not calls:
            if not sess.inspected:
                raise ValueError("Agent did not investigate the graph")
            return {"case_id":case_id,"receipt_id":receipt_id,
                    "model_summary":msg.content or "",
                    "authoritative_decision":sess.decision,
                    "draft":sess.draft,"tool_trace":sess.trace,
                    "evidence_paths":sess.evidence_paths,"engine":"model_selected_graph_tools",
                    "disclaimer":"Synthetic local graph; drafts are not sent and no settlement is automatic."}
        messages.append({"role":"assistant","content":msg.content,
                         "tool_calls":[{"id":c.id,"type":"function",
                           "function":{"name":c.function.name,"arguments":c.function.arguments}} for c in calls]})
        for c in calls:
            try:
                params=json.loads(c.function.arguments or "{}")
                if not isinstance(params,dict):raise ValueError("Expected a JSON object")
                result=tools.dispatch(c.function.name,params)
            except (ValueError,TypeError,KeyError) as exc:
                result={"kind":"blocked","error":str(exc)}
                sess.trace.append({"tool":c.function.name,"result_kind":"blocked","reason":str(exc)})
            messages.append({"role":"tool","tool_call_id":c.id,"content":json.dumps(result,default=str)})
    raise RuntimeError("Agent exceeded bounded tool selection rounds")
