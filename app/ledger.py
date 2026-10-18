"""Whole-ledger reconciliation computed inside FalkorDB with ``algo.maxFlow``.

The supplier relationship is modelled as a flow network that lives in the graph:

    (:LedgerSource) -[:LEDGER_FLOW {flow_cap: units still unallocated}]-> (:ResolveReceipt)
    (:ResolveReceipt) -[:LEDGER_FLOW {flow_cap}]-> (:ResolveObligation)   // mirrors POTENTIALLY_FULFILLS
    (:ResolveObligation) -[:LEDGER_FLOW {flow_cap: units still owed}]-> (:LedgerSink)

FalkorDB's algo.maxFlow takes exactly one relationship type, so the network uses a
single LEDGER_FLOW type; every receipt->obligation LEDGER_FLOW edge mirrors a
POTENTIALLY_FULFILLS eligibility edge created at intake.

``flow_cap`` is a derived field recomputed from graph facts on every reconcile; it
is never a business fact. One ``algo.maxFlow`` call returns the most units the
recorded deliveries can settle without double counting. A second pass blocks
each used edge and re-runs the flow: the drop is the number of units that edge
carries in EVERY maximum allocation ("forced"). Only forced units are ever
proposed. Anything else is ambiguous and becomes a precise supplier question.
The owner still approves every allocation; nothing here writes a settlement.
"""
from __future__ import annotations
import threading
from .demo_data import TENANT
from .flow import forced_units as py_forced

BIG = 1_000_000
REL_TYPE = "LEDGER_FLOW"
_lock = threading.Lock()

# 1. Ensure the case's source and sink exist and are wired to its receipts/obligations.
Q_WIRE = """MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})
MERGE (src:LedgerSource {tenant:$tenant,case:$case})
MERGE (snk:LedgerSink {tenant:$tenant,case:$case})
WITH c,src,snk
OPTIONAL MATCH (c)-[:HAS_RECEIPT]->(r:ResolveReceipt)
FOREACH (_ IN CASE WHEN r IS NULL THEN [] ELSE [1] END | MERGE (src)-[:LEDGER_FLOW]->(r))
WITH DISTINCT c,snk
OPTIONAL MATCH (c)-[:HAS_OBLIGATION]->(o:ResolveObligation)
FOREACH (_ IN CASE WHEN o IS NULL THEN [] ELSE [1] END | MERGE (o)-[:LEDGER_FLOW]->(snk))
WITH DISTINCT c
OPTIONAL MATCH (c)-[:HAS_RECEIPT]->(r2:ResolveReceipt)-[:POTENTIALLY_FULFILLS]->(o2:ResolveObligation)
WHERE (c)-[:HAS_OBLIGATION]->(o2)
FOREACH (_ IN CASE WHEN o2 IS NULL THEN [] ELSE [1] END | MERGE (r2)-[:LEDGER_FLOW]->(o2))
WITH DISTINCT c
RETURN c.id"""

# 2. Derive capacities from current graph facts.
#    A receipt with conflicting active supplier statements feeds nothing (dispute).
#    A receipt attributed by the supplier may only flow to that obligation.
Q_CAPS_RECEIPTS = """MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt)
MATCH (:LedgerSource {tenant:$tenant,case:$case})-[f:LEDGER_FLOW]->(r)
OPTIONAL MATCH (s:ResolveStatement {active:true})-[:ABOUT]->(r)
WITH c,r,f,collect(DISTINCT s.target_id) AS targets
SET f.flow_cap = CASE WHEN r.confirmed=true AND r.unit=c.unit AND size(targets)<=1 THEN r.available ELSE 0 END
WITH r,targets
OPTIONAL MATCH (r)-[p:LEDGER_FLOW]->(o:ResolveObligation)
FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END |
  SET p.flow_cap = CASE WHEN size(targets)=0 OR o.id IN targets THEN $big ELSE 0 END)
RETURN r.id, size(targets)"""
Q_CAPS_OBLIGATIONS = """MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_OBLIGATION]->(o:ResolveObligation)
MATCH (o)-[d:LEDGER_FLOW]->(:LedgerSink {tenant:$tenant,case:$case})
SET d.flow_cap = CASE WHEN o.eligible=true THEN o.remaining ELSE 0 END
RETURN o.id"""

# 3. The graph algorithm itself.
Q_MAXFLOW = """MATCH (src:LedgerSource {tenant:$tenant,case:$case}),(snk:LedgerSink {tenant:$tenant,case:$case})
CALL algo.maxFlow({sourceNodes:[src], targetNodes:[snk], capacityProperty:'flow_cap',
                   relationshipTypes:['LEDGER_FLOW']})
YIELD edges, edgeFlows, maxFlow
UNWIND range(0, size(edges)-1) AS i
WITH edges[i] AS e, edgeFlows[i] AS units, maxFlow
WITH startNode(e) AS a, endNode(e) AS b, units, maxFlow
WHERE a:ResolveReceipt AND b:ResolveObligation
RETURN a.id, b.id, units, maxFlow"""

Q_BLOCK_EDGE = """MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt {id:$receipt})
MATCH (c)-[:HAS_OBLIGATION]->(o:ResolveObligation {id:$claim})
MATCH (r)-[p:LEDGER_FLOW]->(o)
SET p.flow_cap=$cap RETURN p.flow_cap"""

# Read the same network back for the labelled fallback and for explanations.
Q_NETWORK = """MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt)
MATCH (:LedgerSource {tenant:$tenant,case:$case})-[f:LEDGER_FLOW]->(r)
OPTIONAL MATCH (r)-[p:LEDGER_FLOW]->(o:ResolveObligation)
RETURN r.id, r.received_on, r.qty, f.flow_cap, o.id, p.flow_cap, r.available, r.confirmed, r.version
ORDER BY r.received_on, r.id, o.id"""
Q_OBLIGATIONS = """MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_OBLIGATION]->(o:ResolveObligation)
MATCH (o)-[d:LEDGER_FLOW]->(:LedgerSink {tenant:$tenant,case:$case})
MATCH (o)-[:SUPPORTED_BY]->(doc:ResolveDocument)
RETURN o.id, o.kind, o.original, o.remaining, o.eligible, d.flow_cap, doc.ref, o.version ORDER BY o.created_on, o.id"""
Q_DISPUTED = """MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt)
MATCH (s:ResolveStatement {active:true})-[:ABOUT]->(r)
WITH r, collect(DISTINCT s.target_id) AS targets
RETURN r.id, targets"""

# Evidence path for one proposal: receipt -> obligation -> its source document.
Q_PATH = """MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt {id:$receipt})
MATCH (c)-[:HAS_OBLIGATION]->(o:ResolveObligation {id:$claim})
MATCH path=(r)-[:POTENTIALLY_FULFILLS]->(o)-[:SUPPORTED_BY]->(d:ResolveDocument)
RETURN r.document_ref, o.kind, d.ref, length(path)"""

# Guarded write for a forced allocation. The Python layer re-runs the flow and
# confirms the units are forced; this query re-checks versions, quantities,
# eligibility and that no supplier statement points the receipt elsewhere.
Q_APPROVE_FORCED = """MATCH (c:ResolveCase {tenant:$tenant,id:$case,ready:true})-[:HAS_RECEIPT]->(r:ResolveReceipt {id:$receipt})
MATCH (c)-[:HAS_OBLIGATION]->(o:ResolveObligation {id:$claim})
MATCH (r)-[:POTENTIALLY_FULFILLS]->(o)
WHERE r.version=$receipt_version AND o.version=$claim_version AND r.confirmed=true
 AND r.available >= $quantity AND o.remaining >= $quantity AND o.eligible=true AND $quantity > 0
WITH r,o
OPTIONAL MATCH (other:ResolveStatement {active:true})-[:ABOUT]->(r)
WHERE other.target_id <> $claim
WITH r,o,count(other) AS contradictions
WHERE contradictions = 0
CREATE (a:ResolveAllocation {id:$allocation_id,tenant:$tenant,qty:$quantity,proof:$proof})
CREATE (a)-[:FROM]->(r)
CREATE (a)-[:SETTLES]->(o)
CREATE (approval:ResolveApproval {id:$approval_id,actor:'synthetic-retailer',receipt_version:$receipt_version})
CREATE (approval)-[:CONFIRMS]->(a)
SET r.available=r.available-$quantity,r.version=r.version+1,
    o.remaining=o.remaining-$quantity,o.version=o.version+1
RETURN a.id"""


def _missing_procedure(exc: Exception) -> bool:
    text = str(exc)
    return "algo.maxFlow" in text and ("not registered" in text or "unknown" in text.lower())


class LedgerReconciler:
    """Reconcile one supplier case. ``store`` is a ResolveStore (read/write passthrough)."""

    def __init__(self, store, allow_fallback: bool = True):
        self.store = store
        self.allow_fallback = allow_fallback

    def _p(self, case_id, **extra):
        return dict({"tenant": TENANT, "case": case_id, "big": BIG}, **extra)

    def _graph_flow(self, case_id):
        rows = self.store.write(Q_MAXFLOW, self._p(case_id))  # CALL needs the RW endpoint on some builds
        flows = {(r, o): int(u) for r, o, u, _ in rows if int(u) > 0}
        total = int(rows[0][3]) if rows else 0
        return total, flows

    def reconcile(self, case_id: str) -> dict:
        with _lock:
            if not self.store.write(Q_WIRE, self._p(case_id)):
                raise KeyError("Case not found")
            self.store.write(Q_CAPS_RECEIPTS, self._p(case_id))
            self.store.write(Q_CAPS_OBLIGATIONS, self._p(case_id))
            network = self.store.read(Q_NETWORK, self._p(case_id))
            obligations = self.store.read(Q_OBLIGATIONS, self._p(case_id))
            disputed = {r: t for r, t in self.store.read(Q_DISPUTED, self._p(case_id)) if len(t) > 1}

            engine = "falkordb.algo.maxFlow"
            try:
                total, flows = self._graph_flow(case_id)
                forced = {}
                for (r, o), units in flows.items():
                    self.store.write(Q_BLOCK_EDGE, self._p(case_id, receipt=r, claim=o, cap=0))
                    try:
                        blocked_total, _ = self._graph_flow(case_id)
                    finally:
                        self.store.write(Q_BLOCK_EDGE, self._p(case_id, receipt=r, claim=o, cap=BIG))
                    forced[(r, o)] = total - blocked_total
                # Restore attribution-restricted capacities the block/unblock may have widened.
                self.store.write(Q_CAPS_RECEIPTS, self._p(case_id))
            except Exception as exc:
                if not (self.allow_fallback and _missing_procedure(exc)):
                    raise
                engine = "python_fallback (this FalkorDB build has no algo.maxFlow)"
                supply, edges = {}, {}
                for rid, _, _, fcap, oid, pcap, *_ in network:
                    supply[rid] = int(fcap or 0)
                    if oid is not None:
                        edges[(rid, oid)] = int(pcap or 0)
                demand = {o[0]: int(o[5] or 0) for o in obligations}
                total, flows, forced = py_forced(supply, demand, edges)

        return self._report(case_id, engine, total, flows, forced, network, obligations, disputed)

    def _report(self, case_id, engine, total, flows, forced, network, obligations, disputed):
        receipts = {}
        for rid, date, qty, fcap, _, _, available, confirmed, version in network:
            receipts[rid] = {"id": rid, "received_on": date, "qty": qty, "available": available,
                             "confirmed": bool(confirmed), "version": version,
                             "flow_capacity": int(fcap or 0)}
        settled_by = {}
        for (r, o), u in flows.items():
            settled_by[o] = settled_by.get(o, 0) + u
        proposals, ambiguous = [], []
        for (r, o), units in sorted(flows.items()):
            f = forced.get((r, o), 0)
            if f > 0:
                path = self.store.read(Q_PATH, self._p(case_id, receipt=r, claim=o))
                proposals.append({"receipt_id": r, "claim_id": o, "forced_units": f,
                                  "receipt_version": receipts[r]["version"],
                                  "claim_version": next(x[7] for x in obligations if x[0] == o),
                                  "evidence_path": [f"Receipt:{r}", "POTENTIALLY_FULFILLS",
                                                    f"Obligation:{o}", "SUPPORTED_BY",
                                                    f"Document:{path[0][2]}" if path else "Document:UNKNOWN"]})
            if units > f:
                ambiguous.append({"receipt_id": r, "claim_id": o, "units": units - f})
        owed = []
        for oid, kind, original, remaining, eligible, dcap, doc, oversion in obligations:
            owed.append({"id": oid, "kind": kind, "version": oversion, "original_qty": original, "outstanding_qty": remaining,
                         "eligible": bool(eligible), "settleable_now": settled_by.get(oid, 0),
                         "still_owed_after_best_case": max(0, int(dcap or 0) - settled_by.get(oid, 0)),
                         "document_ref": doc})
        blocked = [{"receipt_id": r, "reason": "CONFLICTING_SUPPLIER_STATEMENTS", "targets": sorted(t)}
                   for r, t in sorted(disputed.items())]
        blocked += [{"receipt_id": r["id"], "reason": "NOT_CONFIRMED_BY_RETAILER"}
                    for r in receipts.values() if not r["confirmed"] and r["id"] not in disputed]
        forced_total = sum(p["forced_units"] for p in proposals)
        if blocked and any(b["reason"] == "CONFLICTING_SUPPLIER_STATEMENTS" for b in blocked):
            status = "DISPUTE"
        elif ambiguous:
            status = "ASK_SUPPLIER"
        elif proposals:
            status = "REVIEW_FORCED_SETTLEMENT"
        else:
            status = "NOTHING_TO_SETTLE"
        question = None
        if ambiguous:
            options = {}
            for rid, _, _, _, oid, pcap, *_ in network:
                if oid is not None and int(pcap or 0) > 0:
                    options.setdefault(rid, []).append(oid)
            unclear = sorted({a["receipt_id"] for a in ambiguous})
            parts = "; ".join(f"{r} could be for {' or '.join(options.get(r, []))}" for r in unclear)
            question = (f"Supplier: {parts}. Please state which claim each delivery was for, "
                        "with an invoice or scheme reference.")
        return {"case_id": case_id, "engine": engine, "status": status,
                "max_settleable_units": total, "forced_units": forced_total,
                "ambiguous_units": sum(a["units"] for a in ambiguous),
                "total_outstanding": sum(o["outstanding_qty"] for o in owed if o["eligible"]),
                "proposals": proposals, "ambiguous": ambiguous, "obligations": owed,
                "receipts": list(receipts.values()), "blocked_receipts": blocked,
                "supplier_question": question,
                "method": ("One algo.maxFlow over LEDGER_FLOW edges Source→Receipt→Obligation→Sink; each used edge is "
                           "blocked and re-run. Units that disappear are carried by that edge in every "
                           "maximum allocation and are the only units proposed."),
                "cypher": ["Q_WIRE", "Q_CAPS_RECEIPTS", "Q_CAPS_OBLIGATIONS", "Q_MAXFLOW", "Q_BLOCK_EDGE", "Q_PATH"]}

    def approve_forced(self, case_id, receipt_id, claim_id, quantity, receipt_version, claim_version):
        report = self.reconcile(case_id)
        match = next((p for p in report["proposals"]
                      if p["receipt_id"] == receipt_id and p["claim_id"] == claim_id), None)
        if report["status"] == "DISPUTE" or match is None or quantity > match["forced_units"] or quantity < 1:
            raise ValueError("Current graph does not force this allocation")
        p = {"tenant": TENANT, "case": case_id, "receipt": receipt_id, "claim": claim_id,
             "quantity": quantity, "receipt_version": receipt_version, "claim_version": claim_version,
             "allocation_id": f"alloc-{case_id}-{receipt_id}-{claim_id}-{receipt_version}",
             "approval_id": f"approval-{case_id}-{receipt_id}-{claim_id}-{receipt_version}",
             "proof": "graph-forced:algo.maxFlow;retailer-reviewed"}
        rows = self.store.write(Q_APPROVE_FORCED, p)
        if not rows:
            raise ValueError("Rejected: stale version, conflicting statement or insufficient quantity")
        return self.reconcile(case_id)
