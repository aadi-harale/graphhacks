"""Fair SQLite control: same evidence and same deterministic decision policy.

This is intentionally *not* a weak invoice-only strawman.
"""
import sqlite3
from .models import Context, Obligation, Receipt, Statement

def sqlite_roundtrip(ctx: Context) -> Context:
    db=sqlite3.connect(":memory:")
    db.executescript("""
CREATE TABLE receipt(id TEXT,supplier_id TEXT,sku TEXT,original_qty INT,available_qty INT,
                     confirmed INT,proof_ref TEXT,version INT,unit_known INT);
CREATE TABLE obligation(id TEXT,supplier_id TEXT,sku TEXT,kind TEXT,original_qty INT,
                        outstanding_qty INT,version INT,proof_ref TEXT);
CREATE TABLE statement(id TEXT,receipt_id TEXT,target_id TEXT,proof_ref TEXT,active INT);
""")
    r=ctx.receipt
    db.execute("INSERT INTO receipt VALUES (?,?,?,?,?,?,?,?,?)",
               (r.id,r.supplier_id,r.sku,r.original_qty,r.available_qty,
                r.retailer_confirmed,r.proof_ref,r.version,r.unit_known))
    for o in ctx.obligations:
        db.execute("INSERT INTO obligation VALUES (?,?,?,?,?,?,?,?)",
                   (o.id,r.supplier_id,o.sku,o.kind,o.original_qty,o.outstanding_qty,
                    o.version,o.proof_ref))
    for s in ctx.statements:
        db.execute("INSERT INTO statement VALUES (?,?,?,?,?)",
                   (s.id,r.id,s.target_id,s.proof_ref,s.active))
    rr=db.execute("SELECT * FROM receipt WHERE id=?",(r.id,)).fetchone()
    oo=db.execute("""SELECT o.id,o.sku,o.kind,o.original_qty,o.outstanding_qty,o.version,o.proof_ref
 FROM obligation o JOIN receipt r ON r.supplier_id=o.supplier_id AND r.sku=o.sku
 WHERE r.id=? AND o.outstanding_qty>0 ORDER BY o.id""",(r.id,)).fetchall()
    ss=db.execute("SELECT id,target_id,proof_ref,active FROM statement WHERE receipt_id=? ORDER BY id",
                  (r.id,)).fetchall()
    db.close()
    return Context(Receipt(*rr),tuple(Obligation(*o) for o in oo),
                   tuple(Statement(*s) for s in ss),dict(ctx.promises),
                   dict(ctx.paths),("sqlite.joined_context",))
