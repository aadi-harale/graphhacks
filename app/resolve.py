"""Read-only-scope synthetic case intake and evidence-gated resolution.

This is a separate, multi-receipt contract on the same local FalkorDB backend.
It never contacts suppliers, processes payments, or accepts production credentials.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from .demo_data import TENANT

class Terms(BaseModel):
    valid_from: date
    valid_to: date
    min_purchase: int = Field(ge=1, le=100000)
    purchase_qty: int = Field(ge=0, le=100000)

class ClaimIn(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{2,32}$")
    kind: Literal["shortage", "promotion"]
    qty: int = Field(ge=1, le=10000)
    created_on: date
    document_ref: str = Field(min_length=4, max_length=160)
    earned_on: date | None = None
    scheme_terms: Terms | None = None

class ReceiptIn(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{2,32}$")
    received_on: date
    qty: int = Field(ge=1, le=10000)
    unit: str = Field(pattern=r"^[a-zA-Z0-9_-]{2,24}$")
    retailer_confirmed: bool = True
    document_ref: str = Field(min_length=4, max_length=160)

class CaseIn(BaseModel):
    synthetic_only: Literal[True]
    case_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{3,40}$")
    supplier_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{3,40}$")
    sku: str = Field(pattern=r"^[a-zA-Z0-9_-]{2,40}$")
    unit: str = Field(pattern=r"^[a-zA-Z0-9_-]{2,24}$")
    obligations: list[ClaimIn] = Field(min_length=1, max_length=20)
    receipts: list[ReceiptIn] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def check(self):
        if len({o.id for o in self.obligations}) != len(self.obligations):
            raise ValueError("Duplicate obligation ID")
        if len({r.id for r in self.receipts}) != len(self.receipts):
            raise ValueError("Duplicate receipt ID")
        for o in self.obligations:
            if o.kind == "promotion" and (not o.scheme_terms or not o.earned_on):
                raise ValueError("Promotion needs dated, documented scheme terms")
            if o.scheme_terms and o.scheme_terms.valid_from > o.scheme_terms.valid_to:
                raise ValueError("Invalid promotion date range")
        return self

def scheme_eligible(claim: ClaimIn):
    if claim.kind != "promotion":
        return True
    t = claim.scheme_terms
    return bool(t and claim.earned_on and
                t.valid_from <= claim.earned_on <= t.valid_to and
                t.purchase_qty >= t.min_purchase)

def fingerprint(case: CaseIn):
    canonical = json.dumps(case.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

# Every candidate comes from the graph relationship, not a Python-synthesized set.
Q_RECEIPT = """MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt {id:$receipt})
RETURN r.id,r.received_on,r.qty,r.available,r.unit,r.confirmed,r.version,r.document_ref,c.supplier_id,c.sku,c.unit"""
Q_CANDIDATES = """MATCH (:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt {id:$receipt})
MATCH (r)-[:POTENTIALLY_FULFILLS]->(o:ResolveObligation)
MATCH (o)-[:SUPPORTED_BY]->(doc:ResolveDocument)
RETURN o.id,o.kind,o.original,o.remaining,o.version,o.eligible,doc.ref ORDER BY o.id"""
Q_STATEMENTS = """MATCH (:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt {id:$receipt})
MATCH (s:ResolveStatement {active:true})-[:ABOUT]->(r)
RETURN s.id,s.target_id,s.reference ORDER BY s.id"""
Q_HISTORY = """MATCH (:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt {id:$receipt})
MATCH (a:ResolveAllocation)-[:FROM]->(r)
MATCH (a)-[:SETTLES]->(o:ResolveObligation)
RETURN a.id,o.id,a.qty,a.proof ORDER BY a.id"""

Q_APPROVE = """MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt {id:$receipt})
MATCH (r)-[:POTENTIALLY_FULFILLS]->(o:ResolveObligation {id:$claim})
MATCH (c)-[:HAS_OBLIGATION]->(o)
MATCH (s:ResolveStatement {active:true,target_id:$claim})-[:ABOUT]->(r)
WHERE r.version=$receipt_version AND o.version=$claim_version AND r.confirmed=true
 AND r.available >= $quantity AND o.remaining >= $quantity AND o.eligible=true
 AND $quantity > 0 AND s.reference <> ''
WITH r,o
OPTIONAL MATCH (other:ResolveStatement {active:true})-[:ABOUT]->(r)
WHERE other.target_id <> $claim
WITH r,o,count(other) AS contradictions
WHERE contradictions = 0
WITH DISTINCT r,o
CREATE (a:ResolveAllocation {id:$allocation_id,tenant:$tenant,qty:$quantity,proof:$proof})
CREATE (a)-[:FROM]->(r)
CREATE (a)-[:SETTLES]->(o)
CREATE (approval:ResolveApproval {id:$approval_id,actor:'synthetic-retailer',receipt_version:$receipt_version})
CREATE (approval)-[:CONFIRMS]->(a)
SET r.available=r.available-$quantity,r.version=r.version+1,
    o.remaining=o.remaining-$quantity,o.version=o.version+1
RETURN a.id"""

class ResolveStore:
    def __init__(self, graph_store):
        self.g = graph_store

    def read(self, cypher, params):
        return self.g.read(cypher, params)
    def write(self, cypher, params):
        return self.g.write(cypher, params)

    def import_case(self, data: CaseIn):
        p = {"tenant": TENANT, "case": data.case_id}
        found = self.read("MATCH (c:ResolveCase {tenant:$tenant,id:$case}) RETURN c.fingerprint,c.ready", p)
        digest = fingerprint(data)
        if found:
            if found[0][0] != digest or found[0][1] is not True:
                raise ValueError("Case ID already exists with different or incomplete content")
            return {"case_id": data.case_id, "imported": False, "receipts": len(data.receipts)}
        root = dict(p, digest=digest, supplier=data.supplier_id, sku=data.sku, unit=data.unit)
        try:
            self.write("""CREATE (c:ResolveCase {tenant:$tenant,id:$case,fingerprint:$digest,ready:false,
 supplier_id:$supplier,sku:$sku,unit:$unit}) RETURN c.id""", root)
            for o in data.obligations:
                terms = o.scheme_terms
                args = dict(p, id=o.id, kind=o.kind, qty=o.qty, created=str(o.created_on),
                            eligible=scheme_eligible(o), ref=o.document_ref,
                            earned=str(o.earned_on) if o.earned_on else "",
                            threshold=terms.min_purchase if terms else 0,
                            purchased=terms.purchase_qty if terms else 0)
                self.write("""MATCH (c:ResolveCase {tenant:$tenant,id:$case})
CREATE (o:ResolveObligation {id:$id,kind:$kind,original:$qty,remaining:$qty,version:0,
 created_on:$created,eligible:$eligible,earned_on:$earned,min_purchase:$threshold,
 purchase_qty:$purchased})
CREATE (doc:ResolveDocument {ref:$ref,kind:'claim-source'})
CREATE (c)-[:HAS_OBLIGATION]->(o)
CREATE (o)-[:SUPPORTED_BY]->(doc) RETURN o.id""", args)
            for r in data.receipts:
                args = dict(p, id=r.id, qty=r.qty, date=str(r.received_on), unit=r.unit,
                            confirmed=r.retailer_confirmed, ref=r.document_ref)
                self.write("""MATCH (c:ResolveCase {tenant:$tenant,id:$case})
CREATE (r:ResolveReceipt {id:$id,received_on:$date,qty:$qty,available:$qty,version:0,
 unit:$unit,confirmed:$confirmed,document_ref:$ref})
CREATE (c)-[:HAS_RECEIPT]->(r) RETURN r.id""", args)
                # Relationship creation is the graph's decision-critical discovery step.
                self.write("""MATCH (c:ResolveCase {tenant:$tenant,id:$case})-[:HAS_RECEIPT]->(r:ResolveReceipt {id:$id})
MATCH (c)-[:HAS_OBLIGATION]->(o:ResolveObligation)
WHERE o.eligible=true AND o.created_on <= r.received_on AND r.unit=c.unit
CREATE (r)-[:POTENTIALLY_FULFILLS]->(o) RETURN count(o)""", args)
            self.write("MATCH (c:ResolveCase {tenant:$tenant,id:$case}) SET c.ready=true RETURN c.id", p)
        except Exception:
            # Only delete nodes owned by this incomplete, freshly created synthetic case.
            self.write("""MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:false})
OPTIONAL MATCH (c)-[:HAS_RECEIPT|HAS_OBLIGATION]->(n)
OPTIONAL MATCH (n)-[:SUPPORTED_BY]->(doc)
WITH c,collect(DISTINCT n)+collect(DISTINCT doc) AS nodes
FOREACH (n IN nodes | DETACH DELETE n)
DETACH DELETE c""", p)
            raise
        return {"case_id": data.case_id, "imported": True, "receipts": len(data.receipts)}

    def list_cases(self):
        rows = self.read("""MATCH (c:ResolveCase {tenant:$tenant,ready:true})
RETURN c.id,c.supplier_id,c.sku ORDER BY c.id""", {"tenant": TENANT})
        return [{"case_id":x[0],"supplier_id":x[1],"sku":x[2]} for x in rows]

    def followups(self, case_id, receipt_id):
        rows=self.read("""MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt {id:$receipt})
MATCH (f:ResolveFollowUp {tenant:$tenant})-[:FOR_RECEIPT]->(r)
RETURN f.id,f.action,f.question,f.status,f.source_version ORDER BY f.id""",
            {"tenant":TENANT,"case":case_id,"receipt":receipt_id})
        return [{"id":x[0],"action":x[1],"question":x[2],"status":x[3],
                 "receipt_version":x[4]} for x in rows]

    def case_receipts(self, case_id):
        rows=self.read("""MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt)
RETURN r.id,r.received_on,r.qty ORDER BY r.received_on,r.id""", {"tenant":TENANT,"case":case_id})
        if not rows:
            raise KeyError("Case not found")
        return [{"id":x[0],"received_on":x[1],"qty":x[2]} for x in rows]

    def investigate(self, case_id: str, receipt_id: str):
        p = {"tenant": TENANT, "case": case_id, "receipt": receipt_id}
        rr = self.read(Q_RECEIPT, p)
        if len(rr) != 1:
            raise KeyError("Case or receipt not found")
        rid, date_str, qty, available, unit, confirmed, rv, receipt_doc, supplier, sku, expected_unit = rr[0]
        candidates = self.read(Q_CANDIDATES, p)
        all_claims=self.read("""MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_OBLIGATION]->(o:ResolveObligation)
MATCH (o)-[:SUPPORTED_BY]->(d:ResolveDocument)
RETURN o.id,o.kind,o.remaining,o.eligible,d.ref ORDER BY o.id""",p)

        candidate_ids={x[0] for x in candidates}
        excluded=[{"id":x[0],"kind":x[1],"outstanding_qty":x[2],
           "reason":"SCHEME_NOT_ELIGIBLE" if not x[3] else "DATE_OR_UNIT_NOT_ELIGIBLE",
           "document_ref":x[4]} for x in all_claims if x[0] not in candidate_ids]
        statements = self.read(Q_STATEMENTS, p)
        allocations = self.read(Q_HISTORY, p)
        eligible = [c for c in candidates if c[3] > 0 and c[5]]
        targets = {s[1] for s in statements}
        verdict, title, question, claim, n = "ASK_SUPPLIER","Which promise did these goods fulfil?","Supplier: identify the earlier claim and cite a reference.",None,0
        if unit != expected_unit:
            verdict,title,question = "UNKNOWN_UNIT","Pack conversion unverified","Retailer: confirm a matching product unit."
        elif not confirmed:
            verdict,title,question = "ASK_RETAILER","Confirm the physical count","Retailer: verify the actual quantity received."
        elif available == 0:
            verdict,title,question = "ALREADY_ALLOCATED","Receipt is fully allocated","No further settlement allowed."
        elif not eligible:
            verdict,title,question = "NEEDS_REVIEW","No eligible outstanding obligation","Check the documented terms and history."
        elif len(targets) > 1:
            verdict,title,question = "DISPUTE","Conflicting supplier explanations","Supplier: which statement is authoritative?"
        elif len(targets) == 1:
            target=next(iter(targets))
            match=next((x for x in eligible if x[0]==target),None)
            if match is None:
                verdict,title,question="DISPUTE","Supplier attributed an ineligible claim","Supplier: correct the claim reference."
            elif any(not s[2].strip() for s in statements):
                verdict,title,question="NEEDS_REVIEW","Missing supplier evidence reference","Supplier: provide a supporting note."
            else:
                verdict,title,question,claim,n="REVIEW_SETTLEMENT","A reviewable allocation is supported","Retailer: approve only after checking receipt and supplier reference.",target,min(available,match[3])
        return {"case_id":case_id, "receipt_id":rid, "receipt":{"id":rid,"received_on":date_str,
          "qty":qty,"available_qty":available,"unit":unit,"confirmed":confirmed,"version":rv,"document_ref":receipt_doc},
          "supplier_id":supplier,"sku":sku, "expected_unit":expected_unit,
          "candidates":[{"id":x[0],"kind":x[1],"original_qty":x[2],"outstanding_qty":x[3],
              "version":x[4],"eligible":x[5],"document_ref":x[6]} for x in candidates],
          "excluded_claims":excluded,
          "statements":[{"id":x[0],"target_id":x[1],"reference":x[2]} for x in statements],
          "allocations":[{"allocation_id":x[0],"claim_id":x[1],"qty":x[2],"proof":x[3]} for x in allocations],
          "decision":{"status":verdict,"title":title,"question":question,"suggested_claim":claim,"suggested_qty":n},
          "graph_trace":["ResolveCase","HAS_RECEIPT",rid,"POTENTIALLY_FULFILLS",
              *[x[0] for x in candidates],"SUPPORTED_BY","ResolveDocument"]}

    def attribute(self, case_id, receipt_id, claim_id, reference, expected_version):
        p={"tenant":TENANT,"case":case_id,"receipt":receipt_id,"claim":claim_id,
           "reference":reference,"version":expected_version,
           "statement_id":f"stmt-{case_id}-{receipt_id}-{expected_version}"}
        rows=self.write("""MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt {id:$receipt})
MATCH (r)-[:POTENTIALLY_FULFILLS]->(o:ResolveObligation {id:$claim})
WHERE r.version=$version AND r.available>0 AND o.remaining>0 AND o.eligible=true
OPTIONAL MATCH (old:ResolveStatement {active:true})-[:ABOUT]->(r)
WITH r,collect(old) AS olds
FOREACH (old IN olds | SET old.active=false)
CREATE (s:ResolveStatement {id:$statement_id,target_id:$claim,reference:$reference,active:true})
CREATE (s)-[:ABOUT]->(r)
SET r.version=r.version+1
RETURN s.id""",p)
        if not rows:
            raise ValueError("Invalid claim or stale receipt; refresh before attributing")
        return self.investigate(case_id, receipt_id)

    def approve(self, case_id, receipt_id, claim_id, quantity, receipt_version, claim_version):
        state=self.investigate(case_id, receipt_id)
        d=state["decision"]
        if d["status"] != "REVIEW_SETTLEMENT" or d["suggested_claim"]!=claim_id or d["suggested_qty"]!=quantity:
            raise ValueError("Current evidence does not support this allocation")
        p={"tenant":TENANT,"case":case_id,"receipt":receipt_id,"claim":claim_id,"quantity":quantity,
           "receipt_version":receipt_version,"claim_version":claim_version,
           "allocation_id":f"alloc-{case_id}-{receipt_id}-{receipt_version}",
           "approval_id":f"approval-{case_id}-{receipt_id}-{receipt_version}",
           "proof":"fictional-retailer-reviewed"}
        rows=self.write(Q_APPROVE,p)
        if not rows:
            raise ValueError("Rejected: stale version, conflicting evidence or insufficient quantity")
        return self.investigate(case_id,receipt_id)
