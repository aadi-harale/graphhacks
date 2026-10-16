from app.agent import investigate
from app.baseline import sqlite_roundtrip
from app.demo_data import scenario_context

def test_full_sql_baseline_matches_counterfactual_decisions():
    for name in ("ambiguous","shortage_confirmed","promotion_confirmed",
                 "conflict","unknown_pack","not_received","wrong_target","single","no_open"):
        ctx=scenario_context(name)
        expected=investigate(ctx)
        observed=investigate(sqlite_roundtrip(ctx))
        assert observed.status==expected.status
        assert observed.suggested_obligation==expected.suggested_obligation

def test_sql_baseline_is_not_billed_as_falkordb():
    ctx=sqlite_roundtrip(scenario_context("ambiguous"))
    assert ctx.tool_trace==("sqlite.joined_context",)
