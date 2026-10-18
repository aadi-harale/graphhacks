"""Public live ledger demo for the Vercel preview, backed by FalkorDB Cloud.

Deliberately narrow: it can only load the two fixed synthetic ledger demos, run
LedgerReconciler (algo.maxFlow) on them, and approve a forced allocation on a
case it created. Nothing else from the local app (case intake, agent, resets) is
exposed. Demo cases live in their own graph and are deleted after 30 minutes.
"""
from __future__ import annotations

import json
import os
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.demo_data import TENANT
from app.graph import FalkorStore
from app.ledger import LedgerReconciler
from app.resolve import CaseIn, ResolveStore

ROOT = Path(__file__).resolve().parents[1]
GRAPH = os.getenv("SAHIAAYA_PUBLIC_GRAPH", "sahiaaya_public")
PREFIX = "pubdemo_"
TTL_MS = 30 * 60 * 1000
FIXTURES = {"forced": "ledger_forced_case.json", "ambiguous": "ledger_ambiguous_case.json"}

app = FastAPI(title="SahiAaya public ledger demo", docs_url=None, redoc_url=None, openapi_url=None)
_store = None


def store() -> ResolveStore:
    global _store
    if _store is None:
        if not os.getenv("FALKOR_HOST"):
            raise RuntimeError("FALKOR_HOST is not configured for this deployment")
        _store = ResolveStore(FalkorStore(graph_name=GRAPH))
    return _store


def cleanup(s: ResolveStore) -> None:
    """Delete public demo cases older than 30 minutes (bounded per call)."""
    cutoff = int(time.time() * 1000) - TTL_MS
    s.write("""MATCH (c:ResolveCase {tenant:$tenant})
WHERE c.id STARTS WITH $prefix AND coalesce(c.public_created, 0) < $cutoff
WITH c LIMIT 20
OPTIONAL MATCH (c)-[:HAS_RECEIPT|HAS_OBLIGATION]->(n)
OPTIONAL MATCH (n)-[:SUPPORTED_BY]->(d)
OPTIONAL MATCH (x)-[:ABOUT|FROM|FOR_RECEIPT]->(n)
OPTIONAL MATCH (ap)-[:CONFIRMS]->(x)
WITH c, collect(DISTINCT n) + collect(DISTINCT d) + collect(DISTINCT x) + collect(DISTINCT ap) AS nodes
FOREACH (z IN nodes | DETACH DELETE z)
WITH c
OPTIONAL MATCH (src:LedgerSource {tenant:$tenant, case:c.id})
OPTIONAL MATCH (snk:LedgerSink {tenant:$tenant, case:c.id})
DETACH DELETE src, snk, c""", {"tenant": TENANT, "prefix": PREFIX, "cutoff": cutoff})


def _fallback() -> bool:
    # Production must use algo.maxFlow; the Python fallback is only for local tests.
    return os.getenv("SAHIAAYA_PUBLIC_ALLOW_FALLBACK") == "1"


def public_case(case_id: str) -> str:
    if not case_id.startswith(PREFIX) or len(case_id) > 40:
        raise HTTPException(status_code=404, detail="Not a public demo case")
    return case_id


@app.get("/api/public/health")
def health():
    try:
        store().read("RETURN 1", {})
        return {"ok": True, "backend": "FALKORDB_CLOUD", "scope": "public ledger demo only"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Graph unavailable: {type(exc).__name__}")


class DemoIn(BaseModel):
    which: str = Field(pattern=r"^(forced|ambiguous)$")


@app.post("/api/public/ledger-demo")
def create_demo(inp: DemoIn):
    try:
        s = store()
        cleanup(s)
        data = json.loads((ROOT / "examples" / FIXTURES[inp.which]).read_text(encoding="utf-8"))
        data["case_id"] = f"{PREFIX}{inp.which}_{secrets.token_hex(5)}"
        s.import_case(CaseIn.model_validate(data))
        s.write("MATCH (c:ResolveCase {tenant:$tenant,id:$case}) SET c.public_created=$now RETURN c.id",
                {"tenant": TENANT, "case": data["case_id"], "now": int(time.time() * 1000)})
        return LedgerReconciler(s, allow_fallback=_fallback()).reconcile(data["case_id"])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Live reconciliation failed: {type(exc).__name__}")


class ApproveIn(BaseModel):
    receipt_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{2,32}$")
    claim_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{2,32}$")
    quantity: int = Field(gt=0, le=1000)
    receipt_version: int = Field(ge=0)
    claim_version: int = Field(ge=0)


@app.post("/api/public/ledger-demo/{case_id}/approve")
def approve(case_id: str, inp: ApproveIn):
    public_case(case_id)
    try:
        return LedgerReconciler(store(), allow_fallback=_fallback()).approve_forced(
            case_id, inp.receipt_id, inp.claim_id, inp.quantity, inp.receipt_version, inp.claim_version)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except KeyError:
        raise HTTPException(status_code=404, detail="Demo case expired or not found")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Approval failed: {type(exc).__name__}")
