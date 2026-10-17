"""Real-model Track 01 acceptance gate; NEVER run this without a local API key.

Usage (Windows PowerShell, from local Docker project):
  $env:OPENAI_API_KEY = '<your key, never committed>'
  docker compose up -d --build
  docker compose exec app python -m scripts.live_model_gate --accept-api-cost

This is intentionally different from tests using fake model choices. We create
new randomized synthetic histories in FalkorDB, call the configured model, and
save exact model-selected MCP calls, bounded results, paths and final verdicts.

No key, no model call. All data is fictional, no supplier messaging.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import secrets
from datetime import datetime, timezone

from app.resolve import CaseIn, ResolveStore
from app.graph import FalkorStore
from app.track1_mcp_loop import run_agent_mcp
from app.demo_data import TENANT

SCENARIOS=("unattributed","supported","conflicting","ineligible","already_allocated","unknown_unit")
EXPECTED={
    "unattributed":"ASK_SUPPLIER",
    "supported":"REVIEW_SETTLEMENT",
    "conflicting":"DISPUTE",
    "ineligible":"NEEDS_REVIEW",
    "already_allocated":"ALREADY_ALLOCATED",
    "unknown_unit":"UNKNOWN_UNIT",
}
DEFAULT_QUESTION=(
    "Our supplier delivered the latest box. What previous promise, if any, can "
    "this receipt legitimately settle? Inspect connected evidence and prior "
    "deliveries, describe remaining uncertainty, and create a safe internal "
    "follow-up draft only if the evidence warrants one. Never settle automatically."
)

def unique_case(kind: str):
    random_id=secrets.token_hex(4)
    case_id=f"live_{kind}_{random_id}"
    obligations=[
      {"id":"OLD_SHORT","kind":"shortage","qty":3,"created_on":"2026-09-26",
       "document_ref":f"fictional_invoice_{random_id}"},
      {"id":"OLD_PROMO","kind":"promotion","qty":2,"created_on":"2026-09-27",
       "earned_on":"2026-09-27",
       "document_ref":f"fictional_scheme_{random_id}",
       "scheme_terms":{"valid_from":"2026-09-01","valid_to":"2026-10-20",
                       "min_purchase":10,"purchase_qty":12}}
    ]
    receipts=[
       {"id":"EARLIER_BOX","received_on":"2026-10-02","qty":1,"unit":"piece",
        "retailer_confirmed":True,"document_ref":f"fictional_delivery_early_{random_id}"},
       {"id":"LATEST_BOX","received_on":"2026-10-13","qty":2,"unit":"piece",
        "retailer_confirmed":True,"document_ref":f"fictional_delivery_late_{random_id}"},
    ]
    if kind=="ineligible":
        obligations=[obligations[1]]
        obligations[0]["scheme_terms"]["valid_to"]="2026-09-20"
    elif kind=="already_allocated":
        obligations=[obligations[0]]
    elif kind=="unknown_unit":
        receipts[-1]["unit"]="carton"
    return CaseIn.model_validate({
       "synthetic_only":True,"case_id":case_id,
       "supplier_id":"fictional_supplier_"+random_id,
       "sku":"SOAP_"+random_id.upper(),"unit":"piece",
       "obligations":obligations,"receipts":receipts})

def seed_condition(store,kind,case):
    store.import_case(case)
    if kind in ("supported","conflicting"):
        store.attribute(case.case_id,"LATEST_BOX","OLD_PROMO",
                        "fictional_supplier_promotion_ref",0)
        if kind=="conflicting":
            store.write("""MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt {id:'LATEST_BOX'})
CREATE (s:ResolveStatement {id:$id,target_id:'OLD_SHORT',reference:'fictional_opposing_supplier_ref',active:true})
CREATE (s)-[:ABOUT]->(r) RETURN s.id""",
              {"tenant":TENANT,"case":case.case_id,
               "id":"statement_conflict_"+case.case_id})
    if kind=="already_allocated":
        store.attribute(case.case_id,"LATEST_BOX","OLD_SHORT",
                        "fictional_supplier_replacement_ref",0)
        store.approve(case.case_id,"LATEST_BOX","OLD_SHORT",2,1,0)

async def run_one(store,kind,model,output_dir):
    case=unique_case(kind)
    seed_condition(store,kind,case)
    before=store.investigate(case.case_id,"LATEST_BOX")
    expected=EXPECTED[kind]
    result={"case_id":case.case_id,"scenario":kind,
            "test_kind":"REAL_MODEL_API_NOT_MOCKED",
            "model":model or os.getenv("SAHIAAYA_AGENT_MODEL","gpt-4o-mini"),
            "input_fixture":case.model_dump(mode="json"),
            "expected_policy_status":expected,
            "initial_graph_state":before,
            "started_utc":datetime.now(timezone.utc).isoformat()}
    try:
        agent=await run_agent_mcp(case.case_id,"LATEST_BOX",DEFAULT_QUESTION,
                                  model=model,max_rounds=9)
        after=store.investigate(case.case_id,"LATEST_BOX")
        result["agent_result"]=agent
        result["final_graph_state"]=after
        statuses_match=agent["authoritative_decision"]["status"]==expected
        true_transport=agent.get("model_execution")=="configured_api_client" and (
          agent.get("engine")=="model_selected_mcp_graph_tools") and (
          all(x.get("transport")=="mcp_stdio" for x in agent["tool_trace"]))
        results_captured=any(x.get("result_kind")!="blocked" and "result" in x
                             for x in agent["tool_trace"])
        source_traced=any(x["tool"]=="trace_claim_evidence" and "result" in x
                          for x in agent["tool_trace"])
        draft_safe=(agent["draft"] is None or agent["draft"]["status"]=="draft")
        state_unchanged=before["receipt"]["available_qty"]==after["receipt"]["available_qty"]
        result["checks"]={"expected_policy":statuses_match,
                          "actual_mcp":true_transport,
                          "tool_results_recorded":results_captured,
                          "source_paths_queried":source_traced,
                          "no_automatic_settlement":state_unchanged,
                          "draft_stays_internal":draft_safe}
        result["passed"]=all(result["checks"].values())
    except Exception as exc:
        result["error"]=f"{type(exc).__name__}: {exc}"
        result["passed"]=False
    result["finished_utc"]=datetime.now(timezone.utc).isoformat()
    output_dir.mkdir(parents=True,exist_ok=True)
    destination=output_dir/(case.case_id+".json")
    destination.write_text(json.dumps(result,indent=2,default=str,ensure_ascii=False))
    print(kind, "PASS" if result["passed"] else "FAIL",
          "status",result.get("agent_result",{}).get("authoritative_decision",{}).get("status","n/a"),
          "trace",str(destination))
    return result

async def main():
    parser=argparse.ArgumentParser(description="REAL paid model + MCP + FalkorDB acceptance gate")
    parser.add_argument("--accept-api-cost",action="store_true",
                        help="Explicit confirmation that model API calls may incur charges")
    parser.add_argument("--only",nargs="*",choices=SCENARIOS,default=list(SCENARIOS))
    parser.add_argument("--model",default=None)
    parser.add_argument("--out",default="artifacts/real_model")
    args=parser.parse_args()
    if not args.accept_api_cost:
        parser.error("Explicit --accept-api-cost is required; no API request was sent")
    if not os.getenv("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY is not configured; no live-model run was performed")
    output=Path(args.out)
    store=ResolveStore(FalkorStore(graph_name="sahiaaya_resolve"))
    results=[]
    for scenario in args.only:
        results.append(await run_one(store,scenario,args.model,output))
    sequences=[
      tuple(t["tool"] for t in r.get("agent_result",{}).get("tool_trace",[]) if t.get("result_kind")!="blocked")
      for r in results if r["passed"]]
    paths_vary=len(set(sequences))>1 if len(sequences)>1 else None
    summary={"execution_kind":"REAL_MODEL_API_NOT_MOCKED",
             "total":len(results),
             "passed":sum(r["passed"] for r in results),
             "all_passed":all(r["passed"] for r in results),
             "different_tool_sequences_observed":paths_vary,
             "statuses":{r["scenario"]:r.get("agent_result",{}).get("authoritative_decision",{}).get("status")
                         for r in results},
             "tool_sequences":{r["scenario"]:[t["tool"] for t in r.get("agent_result",{}).get("tool_trace",[])
                                           if t.get("result_kind")!="blocked"] for r in results},
             "no_real_supplier_contact":True}
    output.mkdir(parents=True,exist_ok=True)
    (output/"summary.json").write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
    if not summary["all_passed"] or (paths_vary is False):
        raise SystemExit(1)

if __name__=="__main__":
    asyncio.run(main())
