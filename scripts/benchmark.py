"""Benchmark: per-row FIFO settlement vs SahiAaya's graph reconciliation, scored
against a PLANTED truth (what each synthetic delivery was really for).

Methods
  greedy_fifo   oldest delivery -> oldest eligible claim; honours supplier statements.
                This is how a stock register or a per-row SQL rule settles.
  graph_forced  FalkorDB algo.maxFlow; proposes only units forced in every maximum
                allocation; everything else becomes a supplier question.
  sql_flow      An equally informed comparator: the same rows in SQLite and the same
                max-flow mathematics in Python. Reported to show the graph result is
                reproducible, not uniquely computable.

Metrics (units, summed over all cases)
  wrong     settled against a claim the delivery was not for (or settled a fresh order)
  correct   settled against the true claim
  open      delivered units left for a supplier question

Usage: python -m scripts.benchmark [--cases 60] [--seed 11] [--noise 0.0] [--live] [--out path]
--live imports every case into FalkorDB and runs LedgerReconciler (set FALKOR_HOST/PORT).
"""
from __future__ import annotations
import argparse
import json
import os
import random
import sqlite3
from datetime import date, timedelta

from app.flow import forced_units, greedy_fifo

D0 = date(2026, 10, 1)


def day(n):
    return (D0 + timedelta(days=n)).isoformat()


def generate(rng: random.Random, idx: int, noise: float):
    """One synthetic supplier ledger with planted delivery purposes."""
    obligations, receipts, truth, statements = [], [], {}, {}
    for k in range(rng.randint(2, 4)):
        created = rng.randint(0, 6)
        qty = rng.randint(1, 4)
        if rng.random() < 0.5:
            deliver_by = created + rng.randint(2, 8) if rng.random() < 0.7 else None
            terms = {"valid_from": day(0), "valid_to": day(30), "min_purchase": 10, "purchase_qty": 12}
            if deliver_by is not None:
                terms["deliver_by"] = day(deliver_by)
            obligations.append({"id": f"SCHEME_{k}", "kind": "promotion", "qty": qty, "created_on": day(created),
                                "earned_on": day(created), "document_ref": f"fictional_scheme_{idx}_{k}",
                                "scheme_terms": terms, "_deliver_by": deliver_by})
        else:
            obligations.append({"id": f"SHORT_{k}", "kind": "shortage", "qty": qty, "created_on": day(created),
                                "document_ref": f"fictional_invoice_{idx}_{k}", "_deliver_by": None})
    n = 0
    for o in obligations:
        left = o["qty"]
        for _ in range(rng.randint(0, 2)):
            if left == 0:
                break
            q = rng.randint(1, left)
            left -= q
            lo = int(o["created_on"][-2:]) - 1
            hi = o["_deliver_by"] if o["_deliver_by"] is not None else lo + 12
            rid = f"DROP_{n}"
            n += 1
            receipts.append({"id": rid, "received_on": day(rng.randint(lo, hi)), "qty": q, "unit": "piece",
                             "retailer_confirmed": True, "document_ref": f"fictional_delivery_{idx}_{rid}"})
            truth[rid] = o["id"]
            if rng.random() < 0.25:
                statements[rid] = o["id"]
    if receipts and rng.random() < noise:
        rid = f"DROP_{n}"
        n += 1
        receipts.append({"id": rid, "received_on": day(rng.randint(2, 14)), "qty": rng.randint(1, 3), "unit": "piece",
                         "retailer_confirmed": True, "document_ref": f"fictional_fresh_order_{idx}_{rid}"})
        truth[rid] = None  # a fresh order, not a settlement
    if not receipts:
        return generate(rng, idx, noise)
    case = {"synthetic_only": True, "case_id": f"bench_{idx}", "supplier_id": "fictional_bench_supplier",
            "sku": "SOAP100", "unit": "piece",
            "obligations": [{k: v for k, v in o.items() if not k.startswith("_")} for o in obligations],
            "receipts": receipts}
    return case, truth, statements


def eligible_pairs(case):
    """Same rule the graph uses to create POTENTIALLY_FULFILLS (see app/resolve.py)."""
    pairs = set()
    for r in case["receipts"]:
        for o in case["obligations"]:
            deliver_by = (o.get("scheme_terms") or {}).get("deliver_by", "")
            if o["created_on"] <= r["received_on"] and (not deliver_by or r["received_on"] <= deliver_by):
                pairs.add((r["id"], o["id"]))
    return pairs


def python_forced(case, statements):
    pairs = eligible_pairs(case)
    supply = {r["id"]: r["qty"] for r in case["receipts"]}
    demand = {o["id"]: o["qty"] for o in case["obligations"]}
    edges = {(r, o): (10**6 if (r not in statements or statements[r] == o) else 0) for r, o in pairs}
    _, _, forced = forced_units(supply, demand, edges)
    return {e: u for e, u in forced.items() if u > 0}


def sql_flow(case, statements):
    """Equally informed comparator: rows in SQLite, same flow mathematics."""
    db = sqlite3.connect(":memory:")
    db.execute("create table r(id text, d text, q int)")
    db.execute("create table o(id text, d text, q int, by text)")
    db.execute("create table s(r text, o text)")
    db.executemany("insert into r values(?,?,?)", [(r["id"], r["received_on"], r["qty"]) for r in case["receipts"]])
    db.executemany("insert into o values(?,?,?,?)", [(o["id"], o["created_on"], o["qty"],
                   (o.get("scheme_terms") or {}).get("deliver_by", "")) for o in case["obligations"]])
    db.executemany("insert into s values(?,?)", list(statements.items()))
    rows = db.execute("""select r.id, o.id, case when s.o is null or s.o = o.id then 1000000 else 0 end
      from r join o on o.d <= r.d and (o.by = '' or r.d <= o.by) left join s on s.r = r.id""").fetchall()
    supply = dict(db.execute("select id, q from r").fetchall())
    demand = dict(db.execute("select id, q from o").fetchall())
    _, _, forced = forced_units(supply, demand, {(a, b): c for a, b, c in rows})
    return {e: u for e, u in forced.items() if u > 0}


def graph_forced(case, statements, store):
    from app.resolve import CaseIn
    from app.ledger import LedgerReconciler
    data = CaseIn.model_validate(case)
    store.import_case(data)
    for rid, oid in statements.items():
        state = store.investigate(data.case_id, rid)
        store.attribute(data.case_id, rid, oid, "fictional_supplier_statement", state["receipt"]["version"])
    report = LedgerReconciler(store).reconcile(data.case_id)
    if os.getenv("SAHIAAYA_REQUIRE_GRAPH_MAXFLOW") == "1" and report["engine"] != "falkordb.algo.maxFlow":
        raise SystemExit("FalkorDB algo.maxFlow is not available; refusing to report a fallback as graph results")
    return {(p["receipt_id"], p["claim_id"]): p["forced_units"] for p in report["proposals"]}, report["engine"]


def score(alloc, case, truth):
    wrong = correct = 0
    for (r, o), u in alloc.items():
        if truth.get(r) == o:
            correct += u
        else:
            wrong += u
    delivered = sum(x["qty"] for x in case["receipts"])
    return {"wrong": wrong, "correct": correct, "open": delivered - wrong - correct}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=60)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--noise", type=float, default=0.0, help="chance a case also contains a fresh order")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    store, engine = None, "python reference (no --live)"
    if a.live:
        from app.graph import FalkorStore
        from app.resolve import ResolveStore
        fs = FalkorStore(graph_name="sahiaaya_benchmark")
        try:
            fs.g.delete()
        except Exception:
            pass
        store = ResolveStore(FalkorStore(graph_name="sahiaaya_benchmark"))

    results = {}
    for noise in sorted({0.0, a.noise}):
        rng = random.Random(a.seed)
        tot = {m: {"wrong": 0, "correct": 0, "open": 0, "cases_with_wrong": 0} for m in ("greedy_fifo", "graph_forced")}
        agree = 0
        delivered = 0
        for i in range(a.cases):
            case, truth, statements = generate(rng, i, noise)
            if a.live:
                case["case_id"] = f"bench_{int(noise*100)}_{i}"
            delivered += sum(r["qty"] for r in case["receipts"])
            pairs = eligible_pairs(case)
            greedy = greedy_fifo([(r["id"], r["received_on"], r["qty"]) for r in case["receipts"]],
                                 [(o["id"], o["created_on"], o["qty"]) for o in case["obligations"]],
                                 pairs, statements)
            if a.live:
                graph, engine = graph_forced(case, statements, store)
            else:
                graph = python_forced(case, statements)
            agree += graph == sql_flow(case, statements)
            for name, alloc in (("greedy_fifo", greedy), ("graph_forced", graph)):
                s = score(alloc, case, truth)
                for k in ("wrong", "correct", "open"):
                    tot[name][k] += s[k]
                tot[name]["cases_with_wrong"] += s["wrong"] > 0
        results[f"noise_{noise}"] = {"cases": a.cases, "delivered_units": delivered, "methods": tot,
                                     "graph_equals_equally_informed_sql_flow": f"{agree}/{a.cases}"}

    out = {"engine": engine, "seed": a.seed, "results": results,
           "note": ("Synthetic ledgers with planted delivery purposes. 'noise' = chance a case also holds a "
                    "fresh order that settles nothing. Greedy settles every unit it can; the graph settles "
                    "only forced units and turns the rest into supplier questions.")}
    print(json.dumps(out, indent=2))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)


if __name__ == "__main__":
    main()
