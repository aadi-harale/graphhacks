"""FalkorDB provenance adapter. No synthetic fallback on graph errors."""
from __future__ import annotations
import os
import time
from .models import Context, Receipt, Obligation, Statement
from .demo_data import scenario_context, TENANT, SUPPLIER, SKU

Q_RECEIPT = """MATCH (r:Receipt {tenant:$tenant,id:$receipt_id})-[:FROM_SUPPLIER]->(:Supplier)
MATCH (r)-[:FOR_SKU]->(:SKU)
RETURN r.id,r.supplier_id,r.sku,r.original_qty,r.available_qty,r.confirmed,r.proof_ref,r.version,r.unit_known"""

Q_OBLIGATIONS = """MATCH (r:Receipt {tenant:$tenant,id:$receipt_id})-[:FROM_SUPPLIER]->(s:Supplier)
MATCH (r)-[:FOR_SKU]->(sku:SKU)
MATCH (o:Obligation {tenant:$tenant})-[:OWED_BY]->(s)
MATCH (o)-[:FOR_SKU]->(sku)
WHERE o.outstanding_qty > 0
RETURN o.id,o.sku,o.kind,o.original_qty,o.outstanding_qty,o.version,o.proof_ref ORDER BY o.id"""

Q_STATEMENTS = """MATCH (st:Statement {tenant:$tenant})-[:ABOUT_RECEIPT]->(:Receipt {tenant:$tenant,id:$receipt_id})
MATCH (st)-[:SUPPORTED_BY]->(d:Document {tenant:$tenant})
RETURN st.id,st.target_id,d.ref,st.active ORDER BY st.id"""

Q_SOURCES = """MATCH (o:Obligation {tenant:$tenant,id:$obligation_id})-[:AROSE_FROM]->(src:SourceRecord)-[:SUPPORTED_BY]->(d:Document)
RETURN src.id,d.ref"""

Q_PROMISES = """MATCH (p:Promise {tenant:$tenant})-[:PROMISED_FOR]->(:Obligation {tenant:$tenant,id:$obligation_id})
MATCH (p)-[:SUPPORTED_BY]->(d:Document)
RETURN p.id,d.ref ORDER BY p.id"""

# This bounded graph mutation is only callable after the API repeats the evidence
# decision, verifies current versions, and obtains an explicit demo retailer review.
Q_SETTLE = """MATCH (r:Receipt {tenant:$tenant,id:$receipt_id})
MATCH (o:Obligation {tenant:$tenant,id:$obligation_id})
MATCH (st:Statement {tenant:$tenant,active:true,target_id:$obligation_id})-[:ABOUT_RECEIPT]->(r)
MATCH (st)-[:SUPPORTED_BY]->(d:Document {tenant:$tenant})
WHERE r.version=$receipt_version AND o.version=$obligation_version
  AND r.available_qty >= $quantity AND o.outstanding_qty >= $quantity
  AND r.confirmed=true AND r.unit_known=true
  AND r.supplier_id=o.supplier_id AND r.sku=o.sku AND d.ref <> ''
WITH r,o,st,d
OPTIONAL MATCH (other:Statement {tenant:$tenant,active:true})-[:ABOUT_RECEIPT]->(r)
WHERE other.target_id <> $obligation_id
WITH r,o,st,d,count(other) AS competing_active_statements
WHERE competing_active_statements = 0
WITH DISTINCT r,o
CREATE (a:Allocation {tenant:$tenant,id:$allocation_id,quantity:$quantity,proof_ref:$proof_ref})
CREATE (a)-[:USES_RECEIPT]->(r)
CREATE (a)-[:SETTLES]->(o)
CREATE (ap:RetailerApproval {tenant:$tenant,id:$approval_id,actor:'retailer_demo',
 receipt_version:$receipt_version,obligation_version:$obligation_version})
CREATE (ap)-[:APPROVES]->(a)
SET r.available_qty=r.available_qty-$quantity,r.version=r.version+1,
    o.outstanding_qty=o.outstanding_qty-$quantity,o.version=o.version+1
RETURN a.id"""

class FalkorStore:
    def __init__(self, host=None, port=None, graph_name="sahiaaya_proof"):
        try:
            from falkordb import FalkorDB
        except ImportError as exc:
            raise RuntimeError("Install the FalkorDB Python client from requirements.txt") from exc
        self.db=FalkorDB(host=host or os.getenv("FALKOR_HOST","localhost"),
                         port=port or int(os.getenv("FALKOR_PORT","6379")))
        self.graph_name=graph_name
        self.g=self.db.select_graph(graph_name)
        error=None
        for _ in range(12):
            try:
                self.g.query("RETURN 1")
                break
            except Exception as exc:
                error=exc
                time.sleep(0.5)
        else:
            raise RuntimeError(f"FalkorDB unavailable: {error}")

    def read(self,q,params):
        return self.g.ro_query(q,params).result_set

    def write(self,q,params):
        return self.g.query(q,params).result_set

    def fetch(self,receipt_id,tenant=TENANT):
        p={"tenant":tenant,"receipt_id":receipt_id}
        rows=self.read(Q_RECEIPT,p)
        if len(rows)!=1:
            raise KeyError(receipt_id)
        r=Receipt(*rows[0])
        obligations=tuple(Obligation(*row) for row in self.read(Q_OBLIGATIONS,p))
        statements=tuple(Statement(*row) for row in self.read(Q_STATEMENTS,p))
        promises={}
        paths={}
        for o in obligations:
            p2={"tenant":tenant,"obligation_id":o.id}
            source=self.read(Q_SOURCES,p2)
            promise=self.read(Q_PROMISES,p2)
            promises[o.id]=tuple(f"{row[0]}:{row[1]}" for row in promise)
            src=(f"HistoricalSource:{source[0][0]}",f"Document:{source[0][1]}") if source else ("Source:UNKNOWN",)
            paths[o.id]=(f"Receipt:{r.id}",f"Supplier:{r.supplier_id}",f"SKU:{r.sku}",
                         f"Obligation:{o.id}",*src,*promises[o.id])
        return Context(r,obligations,statements,promises,paths,
                       ("falkordb.Q_RECEIPT","falkordb.Q_OBLIGATIONS","falkordb.Q_STATEMENTS",
                        "falkordb.Q_SOURCES","falkordb.Q_PROMISES"))

    def clarify(self,receipt_id,obligation_id,reference,tenant=TENANT):
        ctx=self.fetch(receipt_id,tenant)
        if obligation_id not in {o.id for o in ctx.obligations}:
            raise ValueError("Not an eligible open obligation")
        if not reference or not reference.strip():
            raise ValueError("Supplier evidence reference required")
        sid=f"clarify-{receipt_id}-{ctx.receipt.version}-{obligation_id}"
        p={"tenant":tenant,"receipt_id":receipt_id,"obligation_id":obligation_id,
           "expected_version":ctx.receipt.version,"sid":sid,"did":"doc-"+sid,"ref":reference}
        rows=self.write("""MATCH (r:Receipt {tenant:$tenant,id:$receipt_id})
MATCH (o:Obligation {tenant:$tenant,id:$obligation_id})
WHERE r.version=$expected_version AND r.supplier_id=o.supplier_id
  AND r.sku=o.sku AND r.available_qty>0 AND o.outstanding_qty>0
OPTIONAL MATCH (old:Statement {tenant:$tenant,active:true})-[:ABOUT_RECEIPT]->(r)
WITH r,collect(old) AS previous
FOREACH (s IN previous | SET s.active=false)
CREATE (d:Document {tenant:$tenant,id:$did,ref:$ref,kind:'synthetic_supplier_note'})
CREATE (s:Statement {tenant:$tenant,id:$sid,target_id:$obligation_id,active:true})
CREATE (s)-[:ABOUT_RECEIPT]->(r)
CREATE (s)-[:SUPPORTED_BY]->(d)
SET r.version=r.version+1
RETURN s.id""",p)
        if not rows:
            raise ValueError("Receipt or eligibility changed: refresh")
        return rows[0][0]

    def commit(self,receipt_id,obligation_id,quantity,receipt_version,
               obligation_version,allocation_id,proof_ref,tenant=TENANT):
        if quantity<=0 or not proof_ref.strip():
            raise ValueError("Positive quantity and review evidence required")
        p={"tenant":tenant,"receipt_id":receipt_id,"obligation_id":obligation_id,
           "quantity":quantity,"receipt_version":receipt_version,
           "obligation_version":obligation_version,
           "allocation_id":allocation_id,"approval_id":"approval-"+allocation_id,
           "proof_ref":proof_ref}
        return bool(self.write(Q_SETTLE,p))

    def history(self,receipt_id,tenant=TENANT):
        rows=self.read("""MATCH (a:Allocation {tenant:$tenant})-[:USES_RECEIPT]->(:Receipt {tenant:$tenant,id:$receipt_id})
MATCH (a)-[:SETTLES]->(o:Obligation {tenant:$tenant})
MATCH (ap:RetailerApproval {tenant:$tenant})-[:APPROVES]->(a)
RETURN a.id,o.id,a.quantity,a.proof_ref,ap.actor ORDER BY a.id""",
                       {"tenant":tenant,"receipt_id":receipt_id})
        return [{"allocation_id":x[0],"obligation_id":x[1],
                 "quantity":x[2],"review_reference":x[3],"approved_by":x[4]} for x in rows]

    def seed(self,scenario="ambiguous"):
        """DESTRUCTIVE: only the isolated, synthetic demo graph may be reset."""
        if not self.graph_name.startswith("sahiaaya_"):
            raise RuntimeError("Refusing to reset a non-demo graph")
        ctx=scenario_context(scenario)
        try:
            self.g.delete()
        except Exception:
            pass
        self.g=self.db.select_graph(self.graph_name)
        p={"tenant":TENANT,"supplier":SUPPLIER,"sku":SKU}
        self.write("""CREATE (s:Supplier {tenant:$tenant,id:$supplier})
CREATE (k:SKU {tenant:$tenant,id:$sku}) RETURN s.id,k.id""",p)
        r=ctx.receipt
        self.write("""MATCH (s:Supplier {tenant:$tenant,id:$supplier}),(k:SKU {tenant:$tenant,id:$sku})
CREATE (r:Receipt {tenant:$tenant,id:$rid,supplier_id:$supplier,sku:$sku,
 original_qty:$original,available_qty:$available,confirmed:$confirmed,
 proof_ref:$ref,version:$version,unit_known:$known})
CREATE (r)-[:FROM_SUPPLIER]->(s)
CREATE (r)-[:FOR_SKU]->(k)
RETURN r.id""",dict(p,rid=r.id,original=r.original_qty,available=r.available_qty,
                  confirmed=r.retailer_confirmed,ref=r.proof_ref,version=r.version,
                  known=r.unit_known))
        for o in ctx.obligations:
            op=dict(p,oid=o.id,kind=o.kind,original=o.original_qty,
                    remaining=o.outstanding_qty,version=o.version,ref=o.proof_ref)
            self.write("""MATCH (s:Supplier {tenant:$tenant,id:$supplier}),(k:SKU {tenant:$tenant,id:$sku})
CREATE (o:Obligation {tenant:$tenant,id:$oid,supplier_id:$supplier,sku:$sku,
 kind:$kind,original_qty:$original,outstanding_qty:$remaining,version:$version,proof_ref:$ref})
CREATE (o)-[:OWED_BY]->(s)
CREATE (o)-[:FOR_SKU]->(k)
CREATE (src:SourceRecord {tenant:$tenant,id:$source_id,kind:$kind})
CREATE (doc:Document {tenant:$tenant,id:$document_id,ref:$ref})
CREATE (o)-[:AROSE_FROM]->(src)
CREATE (src)-[:SUPPORTED_BY]->(doc)
RETURN o.id""",dict(op,source_id="history-"+o.id,document_id="doc-history-"+o.id))
            for i,ref in enumerate(ctx.promises.get(o.id,())):
                self.write("""MATCH (o:Obligation {tenant:$tenant,id:$oid})
CREATE (p:Promise {tenant:$tenant,id:$pid})
CREATE (d:Document {tenant:$tenant,id:$did,ref:$ref})
CREATE (p)-[:PROMISED_FOR]->(o)
CREATE (p)-[:SUPPORTED_BY]->(d)
RETURN p.id""",{"tenant":TENANT,"oid":o.id,"pid":f"promise-{o.id}-{i}",
                              "did":f"doc-promise-{o.id}-{i}","ref":ref})
        for s in ctx.statements:
            self.write("""MATCH (r:Receipt {tenant:$tenant,id:$rid})
CREATE (s:Statement {tenant:$tenant,id:$sid,target_id:$target,active:$active})
CREATE (d:Document {tenant:$tenant,id:$did,ref:$ref})
CREATE (s)-[:ABOUT_RECEIPT]->(r)
CREATE (s)-[:SUPPORTED_BY]->(d)
RETURN s.id""",{"tenant":TENANT,"rid":r.id,"sid":s.id,"target":s.target_id,
                            "active":s.active,"did":"doc-"+s.id,"ref":s.proof_ref})
        return ctx
