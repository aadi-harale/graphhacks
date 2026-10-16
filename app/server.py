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
