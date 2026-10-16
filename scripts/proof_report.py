"""Run: python -m scripts.proof_report"""
from app.agent import investigate
from app.demo_data import scenario_context
from app.baseline import sqlite_roundtrip

print("SAHIAAYA / COUNTERFACTUAL EVIDENCE-GAP STUDY")
print("Same receipt quantities and outstanding claims, different source attribution.")
for name in ("ambiguous","shortage_confirmed","promotion_confirmed","conflict"):
    ctx=scenario_context(name)
    graph_policy=investigate(ctx)
    sql_policy=investigate(sqlite_roundtrip(ctx))
    assert (graph_policy.status,graph_policy.suggested_obligation)==(
        sql_policy.status,sql_policy.suggested_obligation)
    print(f"{name:21s} {graph_policy.status:20s} target={str(graph_policy.suggested_obligation):10s} SQLite=same")
print("LIMITATION: a relational model with equivalent evidence reaches the same decisions.")
print("GRAPH GATE: live FalkorDB Cypher reads and writes must pass integration tests.")
