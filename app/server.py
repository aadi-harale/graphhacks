"""SahiAaya local-only API. Synthetic data; no authentication or real payments."""
import os
import uuid
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .agent import investigate
from .demo_data import TENANT
from .graph import FalkorStore

app=FastAPI(title="SahiAaya EvidenceGap",version="0.2.0")
_store=None

def store():
    global _store
    if _store is None:
        _store=FalkorStore()
    return _store

def state(rid="RCP-52"):
    s=store()
    ctx=s.fetch(rid,TENANT)
    return {"backend":"FALKORDB","synthetic_only":True,
            "receipt":ctx.receipt.__dict__,
            "obligations":[o.__dict__ for o in ctx.obligations],
            "statements":[x.__dict__ for x in ctx.statements],
            "allocations":s.history(rid,TENANT),
            "decision":investigate(ctx).to_dict()}

@app.get("/")
def home():
    return FileResponse(Path(__file__).parent/"static"/"index.html")

@app.get("/api/health")
def health():
    try:
        store()
        return {"ok":True,"backend":"FALKORDB","synthetic":True}
    except Exception as exc:
        raise HTTPException(status_code=503,detail=f"FalkorDB unavailable: {exc}")

@app.get("/api/investigate/{receipt_id}")
def investigate_receipt(receipt_id:str):
    try:
        return state(receipt_id)
    except KeyError:
        raise HTTPException(status_code=404,detail="Receipt not found")
    except Exception as exc:
        raise HTTPException(status_code=503,detail=f"Graph query failed: {exc}")

class ResetIn(BaseModel):
    scenario:str=Field(pattern=r"^[a-z_]{3,40}$")

@app.post("/api/demo/reset")
def reset(inp:ResetIn):
    if os.getenv("ALLOW_DEMO_RESET")!="1":
        raise HTTPException(status_code=403,detail="Local reset disabled")
    try:
        store().seed(inp.scenario)
        return state()
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503,detail=f"Reset failed: {exc}")

class SupplierIn(BaseModel):
    obligation_id:str
    reference:str=Field(min_length=4,max_length=160)

@app.post("/api/investigate/{receipt_id}/simulate-supplier-response")
def supplier_response(receipt_id:str,inp:SupplierIn):
    if os.getenv("ALLOW_DEMO_MUTATIONS")!="1":
        raise HTTPException(status_code=403,detail="Synthetic mutations disabled")
    try:
        store().clarify(receipt_id,inp.obligation_id,inp.reference)
        return state(receipt_id)
    except KeyError:
        raise HTTPException(status_code=404,detail="Receipt not found")
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503,detail=f"Graph update failed: {exc}")

class ApprovalIn(BaseModel):
    obligation_id:str
    quantity:int=Field(gt=0)
    receipt_version:int=Field(ge=0)
    obligation_version:int=Field(ge=0)

@app.post("/api/investigate/{receipt_id}/approve-demo-settlement")
def approve(receipt_id:str,inp:ApprovalIn):
    if os.getenv("ALLOW_DEMO_MUTATIONS")!="1":
        raise HTTPException(status_code=403,detail="Synthetic mutations disabled")
    try:
        s=store()
        ctx=s.fetch(receipt_id,TENANT)
        d=investigate(ctx)
        if d.status!="REVIEW_SETTLEMENT" or d.suggested_obligation!=inp.obligation_id or d.suggested_qty!=inp.quantity:
            raise HTTPException(status_code=409,detail="Not supported by the current evidence")
        o=next(x for x in ctx.obligations if x.id==inp.obligation_id)
        if ctx.receipt.version!=inp.receipt_version or o.version!=inp.obligation_version:
            raise HTTPException(status_code=409,detail="Stale approval: refresh")
        aid="allocation-"+str(uuid.uuid4())
        if not s.commit(receipt_id,o.id,inp.quantity,ctx.receipt.version,o.version,
                        aid,"retailer-demo-reviewed"):
            raise HTTPException(status_code=409,detail="Quantity/version conflict")
        result=state(receipt_id)
        result["allocation_id"]=aid
        return result
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(status_code=404,detail="Receipt not found")
    except Exception as exc:
        raise HTTPException(status_code=503,detail=f"Settlement failed: {exc}")


# SahiAaya Resolve: user-entered, fictional multi-delivery histories.
# Localhost-only Docker mode. Public Vercel stays a read-only synthetic walkthrough.
from .resolve import CaseIn, ResolveStore

_resolve_store = None

def resolve_store():
    """Keep imported case history in a separate graph from the destructive preset reset."""
    global _resolve_store
    if _resolve_store is None:
        _resolve_store = ResolveStore(FalkorStore(graph_name="sahiaaya_resolve"))
    return _resolve_store

def require_local_mutations():
    if os.getenv("ALLOW_DEMO_MUTATIONS") != "1":
        raise HTTPException(status_code=403, detail="Local synthetic-case writes are disabled")

@app.get("/api/resolve/cases")
def resolve_cases():
    try:
        return {"cases": resolve_store().list_cases(), "synthetic_only": True}
    except Exception as exc:
        raise HTTPException(status_code=503,detail=f"Case listing failed: {exc}")

@app.post("/api/resolve/cases")
def resolve_import(inp: CaseIn):
    require_local_mutations()
    try:
        return resolve_store().import_case(inp)
    except ValueError as exc:
        raise HTTPException(status_code=409,detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503,detail=f"Synthetic case import failed: {exc}")

@app.get("/api/resolve/cases/{case_id}/receipts")
def resolve_case_receipts(case_id: str):
    try:
        return {"case_id":case_id,"receipts":resolve_store().case_receipts(case_id)}
    except KeyError:
        raise HTTPException(status_code=404,detail="Synthetic case not found")
    except Exception as exc:
        raise HTTPException(status_code=503,detail=f"Case retrieval failed: {exc}")

@app.get("/api/resolve/cases/{case_id}/receipts/{receipt_id}")
def resolve_investigate(case_id: str, receipt_id: str):
    try:
        return resolve_store().investigate(case_id, receipt_id)
    except KeyError:
        raise HTTPException(status_code=404,detail="Synthetic case or receipt not found")
    except Exception as exc:
        raise HTTPException(status_code=503,detail=f"Evidence investigation failed: {exc}")

class ResolveAttributionIn(BaseModel):
    claim_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{2,32}$")
    reference: str = Field(min_length=4,max_length=160)
    expected_version: int = Field(ge=0)

@app.post("/api/resolve/cases/{case_id}/receipts/{receipt_id}/attribute")
def resolve_attribute(case_id: str, receipt_id: str, inp: ResolveAttributionIn):
    require_local_mutations()
    try:
        return resolve_store().attribute(case_id,receipt_id,inp.claim_id,inp.reference,inp.expected_version)
    except ValueError as exc:
        raise HTTPException(status_code=409,detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503,detail=f"Attribution failed: {exc}")

class ResolveApproveIn(BaseModel):
    claim_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{2,32}$")
    quantity: int = Field(gt=0)
    receipt_version: int = Field(ge=0)
    claim_version: int = Field(ge=0)

@app.post("/api/resolve/cases/{case_id}/receipts/{receipt_id}/approve")
def resolve_approve(case_id: str, receipt_id: str, inp: ResolveApproveIn):
    require_local_mutations()
    try:
        return resolve_store().approve(case_id,receipt_id,inp.claim_id,inp.quantity,
                                       inp.receipt_version,inp.claim_version)
    except ValueError as exc:
        raise HTTPException(status_code=409,detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503,detail=f"Settlement rejected: {exc}")
