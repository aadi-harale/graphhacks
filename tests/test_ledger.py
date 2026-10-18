"""Whole-ledger reconciliation: max-flow mathematics, forced-unit safety, and the live graph.

Pure tests run everywhere. Live tests need RUN_FALKOR_TESTS=1. On a FalkorDB build that
registers algo.maxFlow (falkordb/falkordb:latest in CI), SAHIAAYA_REQUIRE_GRAPH_MAXFLOW=1
makes the suite fail if the engine silently fell back to Python.
"""
import json
import os
import random
from pathlib import Path

import pytest

from app.flow import forced_units, greedy_fifo, max_flow
from app.resolve import CaseIn

ROOT = Path(__file__).resolve().parents[1]
live = pytest.mark.skipif(os.getenv("RUN_FALKOR_TESTS") != "1", reason="Requires live FalkorDB")


def case(name, case_id=None):
    data = json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))
    if case_id:
        data["case_id"] = case_id
    return CaseIn.model_validate(data)


# ---------- pure mathematics ----------

def demo_network():
    supply = {"DROP_1": 2, "DROP_2": 2}
    demand = {"SHORT_JUN": 2, "DIWALI_SCHEME": 2}
    edges = {("DROP_1", "SHORT_JUN"): 99, ("DROP_1", "DIWALI_SCHEME"): 99, ("DROP_2", "SHORT_JUN"): 99}
    return supply, demand, edges


def test_greedy_leaves_units_unexplained_where_flow_settles_all():
    supply, demand, edges = demo_network()
    greedy = greedy_fifo([("DROP_1", "2026-10-05", 2), ("DROP_2", "2026-10-09", 2)],
                         [("SHORT_JUN", "2026-10-01", 2), ("DIWALI_SCHEME", "2026-10-02", 2)],
                         set(edges))
    assert sum(greedy.values()) == 2  # DROP_1 -> shortage, DROP_2 stranded
    total, flows, forced = forced_units(supply, demand, edges)
    assert total == 4
    assert forced == {("DROP_1", "DIWALI_SCHEME"): 2, ("DROP_2", "SHORT_JUN"): 2}


def test_symmetric_choices_force_nothing():
    supply = {"A": 2, "B": 2}
    demand = {"X": 2, "Y": 2}
    edges = {(r, o): 99 for r in supply for o in demand}
    total, _, forced = forced_units(supply, demand, edges)
    assert total == 4 and sum(forced.values()) == 0


def test_forced_bound_holds_in_every_maximum_allocation():
    """Brute force: every max flow carries at least the forced units on each edge."""
    rng = random.Random(7)
    for _ in range(150):
        rs = [f"R{i}" for i in range(rng.randint(1, 3))]
        os_ = [f"O{i}" for i in range(rng.randint(1, 3))]
        supply = {r: rng.randint(1, 3) for r in rs}
        demand = {o: rng.randint(1, 3) for o in os_}
        edges = {(r, o): 99 for r in rs for o in os_ if rng.random() < 0.6}
        total, _, forced = forced_units(supply, demand, edges)
        keys = list(edges)

        def allocations(i, used_r, used_o, acc):
            if i == len(keys):
                yield dict(acc)
                return
            r, o = keys[i]
            for n in range(0, min(supply[r] - used_r.get(r, 0), demand[o] - used_o.get(o, 0)) + 1):
                acc[(r, o)] = n
                used_r[r] = used_r.get(r, 0) + n
                used_o[o] = used_o.get(o, 0) + n
                yield from allocations(i + 1, used_r, used_o, acc)
                used_r[r] -= n
                used_o[o] -= n
            acc.pop((r, o), None)

        best = [a for a in allocations(0, {}, {}, {}) if sum(a.values()) == total]
        assert best
        for e, f in forced.items():
            assert min(a.get(e, 0) for a in best) == f


def test_max_flow_respects_capacity_zero_edges():
    supply, demand, edges = demo_network()
    edges[("DROP_1", "SHORT_JUN")] = 0
    total, flows = max_flow(supply, demand, edges)
    assert total == 4 and ("DROP_1", "SHORT_JUN") not in flows


def test_scheme_delivery_window_is_validated():
    data = json.loads((ROOT / "examples" / "ledger_forced_case.json").read_text(encoding="utf-8"))
    data["obligations"][1]["scheme_terms"]["deliver_by"] = "2026-09-01"
    with pytest.raises(ValueError, match="delivery window"):
        CaseIn.model_validate(data)


# ---------- live graph ----------

def fresh_store(name):
    from app.graph import FalkorStore
    from app.resolve import ResolveStore
    fs = FalkorStore(graph_name=name)
    try:
        fs.g.delete()
    except Exception:
        pass
    return ResolveStore(FalkorStore(graph_name=name))


def check_engine(report):
    if os.getenv("SAHIAAYA_REQUIRE_GRAPH_MAXFLOW") == "1":
        assert report["engine"] == "falkordb.algo.maxFlow"


@live
def test_graph_forces_all_four_units_and_explains_each():
    from app.ledger import LedgerReconciler
    s = fresh_store("sahiaaya_ci_ledger_forced")
    data = case("ledger_forced_case.json")
    s.import_case(data)
    r = LedgerReconciler(s).reconcile(data.case_id)
    check_engine(r)
    assert r["status"] == "REVIEW_FORCED_SETTLEMENT"
    assert r["max_settleable_units"] == 4 and r["forced_units"] == 4 and r["ambiguous_units"] == 0
    got = {(p["receipt_id"], p["claim_id"]): p["forced_units"] for p in r["proposals"]}
    assert got == {("DROP_1", "DIWALI_SCHEME"): 2, ("DROP_2", "SHORT_JUN"): 2}
    for p in r["proposals"]:
        assert p["evidence_path"][-1].startswith("Document:fictional_")


@live
def test_graph_refuses_to_guess_when_choices_are_symmetric():
    from app.ledger import LedgerReconciler
    s = fresh_store("sahiaaya_ci_ledger_ambiguous")
    data = case("ledger_ambiguous_case.json")
    s.import_case(data)
    r = LedgerReconciler(s).reconcile(data.case_id)
    check_engine(r)
    assert r["status"] == "ASK_SUPPLIER" and r["forced_units"] == 0 and r["proposals"] == []
    assert "DROP_1 could be for" in r["supplier_question"]


@live
def test_supplier_attribution_changes_the_graph_answer():
    from app.ledger import LedgerReconciler
    s = fresh_store("sahiaaya_ci_ledger_attributed")
    data = case("ledger_ambiguous_case.json")
    s.import_case(data)
    state = s.investigate(data.case_id, "DROP_1")
    s.attribute(data.case_id, "DROP_1", "SHORT_JUN", "fictional_supplier_note_17", state["receipt"]["version"])
    r = LedgerReconciler(s).reconcile(data.case_id)
    got = {(p["receipt_id"], p["claim_id"]): p["forced_units"] for p in r["proposals"]}
    assert got == {("DROP_1", "SHORT_JUN"): 2, ("DROP_2", "DIWALI_SCHEME"): 2}


@live
def test_conflicting_statements_remove_the_receipt_from_the_flow():
    from app.ledger import LedgerReconciler
    s = fresh_store("sahiaaya_ci_ledger_conflict")
    data = case("ledger_forced_case.json")
    s.import_case(data)
    # Two simultaneous, contradictory supplier statements about DROP_1.
    s.write("""MATCH (c:ResolveCase {id:$case})-[:HAS_RECEIPT]->(r:ResolveReceipt {id:'DROP_1'})
CREATE (:ResolveStatement {id:'s1',target_id:'SHORT_JUN',reference:'note_a',active:true})-[:ABOUT]->(r)
CREATE (:ResolveStatement {id:'s2',target_id:'DIWALI_SCHEME',reference:'note_b',active:true})-[:ABOUT]->(r)
RETURN r.id""", {"case": data.case_id})
    r = LedgerReconciler(s).reconcile(data.case_id)
    assert r["status"] == "DISPUTE"
    assert all(p["receipt_id"] != "DROP_1" for p in r["proposals"])
    with pytest.raises(ValueError):
        LedgerReconciler(s).approve_forced(data.case_id, "DROP_2", "SHORT_JUN", 2, 0, 0)


@live
def test_forced_approval_is_guarded_and_idempotent():
    from app.ledger import LedgerReconciler
    s = fresh_store("sahiaaya_ci_ledger_approve")
    data = case("ledger_forced_case.json")
    s.import_case(data)
    L = LedgerReconciler(s)
    r = L.reconcile(data.case_id)
    p = next(x for x in r["proposals"] if x["receipt_id"] == "DROP_1")
    with pytest.raises(ValueError):  # more than forced
        L.approve_forced(data.case_id, "DROP_1", "DIWALI_SCHEME", 3, p["receipt_version"], p["claim_version"])
    with pytest.raises(ValueError):  # not forced onto that claim
        L.approve_forced(data.case_id, "DROP_1", "SHORT_JUN", 2, p["receipt_version"], p["claim_version"])
    after = L.approve_forced(data.case_id, "DROP_1", "DIWALI_SCHEME", 2, p["receipt_version"], p["claim_version"])
    owed = {o["id"]: o["outstanding_qty"] for o in after["obligations"]}
    assert owed == {"SHORT_JUN": 2, "DIWALI_SCHEME": 0}
    with pytest.raises(ValueError):  # replay with stale versions
        L.approve_forced(data.case_id, "DROP_1", "DIWALI_SCHEME", 2, p["receipt_version"], p["claim_version"])


@live
def test_reconcile_tool_runs_over_real_mcp_transport():
    """Injected tool choices (not a real model) through the real MCP stdio host."""
    import asyncio
    from tests.test_track1_counterfactual import ToolChoiceClient
    from app.track1_mcp_loop import run_agent_mcp
    from app.resolve import ResolveStore
    from app.graph import FalkorStore
    s = ResolveStore(FalkorStore(graph_name="sahiaaya_resolve"))
    data = case("ledger_forced_case.json", case_id="ci_ledger_mcp_forced")
    s.import_case(data)
    out = asyncio.run(run_agent_mcp(data.case_id, "DROP_1", "Is anything still owed?",
                                    client=ToolChoiceClient(["investigate_receipt", "trace_claim_evidence",
                                                             "reconcile_ledger"])))
    assert out["model_execution"] == "injected_client"
    assert [t["tool"] for t in out["tool_trace"]] == ["investigate_receipt", "trace_claim_evidence", "reconcile_ledger"]
    assert out["ledger"]["forced_units"] == 4 and out["ledger"]["status"] == "REVIEW_FORCED_SETTLEMENT"
