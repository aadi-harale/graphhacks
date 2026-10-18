"""Record the two ledger demos on a live FalkorDB for the public preview's replay.

The Vercel preview has no database. Instead of faking results in JavaScript, it
replays app/static/ledger_replay.json: the exact reports this script got from
LedgerReconciler on a live graph. CI re-records on falkordb:latest and fails if the
committed replay no longer matches (tests/test_ledger.py).

Usage: python -m scripts.record_ledger_replay [--out app/static/ledger_replay.json]
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def record(graph_name: str = "sahiaaya_replay") -> dict:
    from app.graph import FalkorStore
    from app.resolve import CaseIn, ResolveStore
    from app.ledger import LedgerReconciler

    fs = FalkorStore(graph_name=graph_name)
    try:
        fs.g.delete()
    except Exception:
        pass
    store = ResolveStore(FalkorStore(graph_name=graph_name))
    rec = LedgerReconciler(store, allow_fallback=True)

    def load(name):
        data = CaseIn.model_validate(json.loads((ROOT / "examples" / name).read_text(encoding="utf-8")))
        store.import_case(data)
        return data.case_id

    forced = load("ledger_forced_case.json")
    before = rec.reconcile(forced)
    first = next(p for p in before["proposals"] if p["receipt_id"] == "DROP_1")
    after = rec.approve_forced(forced, first["receipt_id"], first["claim_id"], first["forced_units"],
                               first["receipt_version"], first["claim_version"])
    ambiguous = rec.reconcile(load("ledger_ambiguous_case.json"))
    return {"engine": before["engine"],
            "steps": {"forced": before, "forced_after_approving_DROP_1": after, "ambiguous": ambiguous}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    out = record()
    out["recorded_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out["label"] = ("Recorded from a live FalkorDB run. This page has no database; "
                    "run the Docker app to execute it yourself.")
    text = json.dumps(out, separators=(",", ":"), sort_keys=True)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
