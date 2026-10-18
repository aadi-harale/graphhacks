"""Public Vercel API: only the two fixed demos, guarded approval, cleanup of old cases."""
import os
import pytest

live = pytest.mark.skipif(os.getenv("RUN_FALKOR_TESTS") != "1", reason="Requires live FalkorDB")


@pytest.fixture()
def client(monkeypatch):
    from fastapi.testclient import TestClient
    import api.index as public
    monkeypatch.setattr(public, "GRAPH", "sahiaaya_ci_public")
    monkeypatch.setattr(public, "_store", None)
    if os.getenv("SAHIAAYA_REQUIRE_GRAPH_MAXFLOW") != "1":
        monkeypatch.setenv("SAHIAAYA_PUBLIC_ALLOW_FALLBACK", "1")
    return TestClient(public.app)


def test_only_known_demos_are_accepted():
    from fastapi.testclient import TestClient
    import api.index as public
    c = TestClient(public.app)
    assert c.post("/api/public/ledger-demo", json={"which": "anything"}).status_code == 422
    assert c.post("/api/public/ledger-demo/shop_alpha/approve", json={
        "receipt_id": "DROP_1", "claim_id": "SHORT_JUN", "quantity": 2,
        "receipt_version": 0, "claim_version": 0}).status_code == 404
    # Nothing from the local app is exposed here.
    assert c.post("/api/resolve/cases", json={}).status_code == 404
    assert c.get("/api/health").status_code == 404


@live
def test_forced_demo_runs_and_approves(client):
    assert client.get("/api/public/health").json()["ok"]
    r = client.post("/api/public/ledger-demo", json={"which": "forced"}).json()
    assert r["case_id"].startswith("pubdemo_forced_") and r["forced_units"] == 4
    if os.getenv("SAHIAAYA_REQUIRE_GRAPH_MAXFLOW") == "1":
        assert r["engine"] == "falkordb.algo.maxFlow"
    p = next(x for x in r["proposals"] if x["receipt_id"] == "DROP_1")
    after = client.post(f"/api/public/ledger-demo/{r['case_id']}/approve", json={
        "receipt_id": p["receipt_id"], "claim_id": p["claim_id"], "quantity": p["forced_units"],
        "receipt_version": p["receipt_version"], "claim_version": p["claim_version"]}).json()
    assert {o["id"]: o["outstanding_qty"] for o in after["obligations"]}["DIWALI_SCHEME"] == 0


@live
def test_ambiguous_demo_asks_and_old_cases_are_cleaned(client):
    import time
    import api.index as public
    r = client.post("/api/public/ledger-demo", json={"which": "ambiguous"}).json()
    assert r["status"] == "ASK_SUPPLIER" and r["forced_units"] == 0
    s = public.store()
    s.write("MATCH (c:ResolveCase {id:$id}) SET c.public_created=0 RETURN c.id", {"id": r["case_id"]})
    public.cleanup(s)
    assert not s.read("MATCH (c:ResolveCase {id:$id}) RETURN c.id", {"id": r["case_id"]})
    assert not s.read("MATCH (n:LedgerSource {case:$id}) RETURN n", {"id": r["case_id"]})
