"""Pure max-flow helpers shared by the graph fallback, the SQL comparator and the benchmark.

The live engine uses FalkorDB's ``algo.maxFlow``. This module exists so that:
1. a FalkorDB build without that procedure still works, clearly labelled as a fallback;
2. an *equally informed* SQLite comparator can run the same mathematics;
3. the benchmark has a reference implementation to check the graph against.
"""
from __future__ import annotations
from collections import deque

SRC = "__source__"
SNK = "__sink__"


def max_flow(supply: dict, demand: dict, edges: dict) -> tuple[int, dict]:
    """Edmonds–Karp on a bipartite network.

    supply: receipt -> units available; demand: obligation -> units owed;
    edges: (receipt, obligation) -> capacity. Returns (value, {(r, o): units}).
    """
    cap: dict = {}
    adj: dict = {}

    def add(u, v, c):
        cap[(u, v)] = cap.get((u, v), 0) + c
        cap.setdefault((v, u), 0)
        adj.setdefault(u, set()).add(v)
        adj.setdefault(v, set()).add(u)

    for r, c in supply.items():
        if c > 0:
            add(SRC, ("r", r), c)
    for o, c in demand.items():
        if c > 0:
            add(("o", o), SNK, c)
    for (r, o), c in edges.items():
        if c > 0:
            add(("r", r), ("o", o), c)

    total = 0
    while True:
        parent = {SRC: None}
        q = deque([SRC])
        while q and SNK not in parent:
            u = q.popleft()
            for v in sorted(adj.get(u, ()), key=repr):  # deterministic order
                if v not in parent and cap[(u, v)] > 0:
                    parent[v] = u
                    q.append(v)
        if SNK not in parent:
            break
        bottleneck, v = None, SNK
        while parent[v] is not None:
            u = parent[v]
            bottleneck = cap[(u, v)] if bottleneck is None else min(bottleneck, cap[(u, v)])
            v = u
        v = SNK
        while parent[v] is not None:
            u = parent[v]
            cap[(u, v)] -= bottleneck
            cap[(v, u)] += bottleneck
            v = u
        total += bottleneck

    flows = {}
    for (r, o), c in edges.items():
        if c > 0:
            used = c - cap[(("r", r), ("o", o))]
            if used > 0:
                flows[(r, o)] = used
    return total, flows


def forced_units(supply: dict, demand: dict, edges: dict) -> tuple[int, dict, dict]:
    """Max flow plus the units each edge carries in EVERY maximum allocation.

    For edge e: forced(e) = F - F(with e blocked). Any maximum flow f has
    f(e) >= forced(e), and some maximum flow achieves exactly forced(e), so the
    bound is tight and all bounds hold together in every maximum allocation.
    """
    total, flows = max_flow(supply, demand, edges)
    forced = {}
    for e in flows:
        blocked = dict(edges)
        blocked[e] = 0
        forced[e] = total - max_flow(supply, demand, blocked)[0]
    return total, flows, forced


def greedy_fifo(receipts: list, obligations: list, eligible: set, attributed: dict | None = None):
    """The per-row rule most stock systems follow: oldest delivery first, oldest
    eligible obligation first, honouring an explicit supplier attribution.

    receipts: [(id, date, qty)]; obligations: [(id, created, qty)];
    eligible: {(receipt, obligation)}; attributed: receipt -> obligation.
    Returns {(r, o): units}.
    """
    attributed = attributed or {}
    remaining = {o: q for o, _, q in obligations}
    order = [o for o, _, _ in sorted(obligations, key=lambda x: (x[1], x[0]))]
    out = {}
    for r, _, qty in sorted(receipts, key=lambda x: (x[1], x[0])):
        left = qty
        targets = [attributed[r]] if r in attributed else order
        for o in targets:
            if left == 0:
                break
            if (r, o) in eligible and remaining[o] > 0:
                n = min(left, remaining[o])
                out[(r, o)] = out.get((r, o), 0) + n
                remaining[o] -= n
                left -= n
    return out
