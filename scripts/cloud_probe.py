"""Diagnose FalkorDB Cloud reachability without printing host or credentials.

Tries encrypted connections only (strict certificate check, then relaxed), and
reports which works, whether algo.maxFlow is registered, and a write/read probe.
Output lines are GitHub annotations so results are readable without job logs.
"""
import os
import ssl
import uuid
import redis


def note(title, msg, level="notice"):
    print(f"::{level} title={title}::{msg}")


def connect(strict: bool):
    return redis.Redis(host=os.environ["FALKOR_HOST"], port=int(os.environ["FALKOR_PORT"]),
                       username=os.getenv("FALKOR_USERNAME") or None, password=os.environ["FALKOR_PASSWORD"],
                       ssl=True, ssl_cert_reqs="required" if strict else "none",
                       ssl_check_hostname=strict, socket_connect_timeout=8, socket_timeout=20)


def main():
    missing = [k for k in ("FALKOR_HOST", "FALKOR_PORT", "FALKOR_PASSWORD") if not os.getenv(k)]
    note("Secrets", f"missing={missing} username_set={bool(os.getenv('FALKOR_USERNAME'))} "
         f"port_is_number={os.getenv('FALKOR_PORT','').isdigit()}")
    if missing:
        return
    for strict in (True, False):
        mode = "TLS strict" if strict else "TLS relaxed-cert"
        try:
            c = connect(strict)
            c.ping()
            note("Connect", f"{mode}: OK")
        except Exception as exc:
            kind = type(exc).__name__
            if isinstance(exc, ssl.SSLError):
                kind += " (TLS)"
            note("Connect", f"{mode}: FAIL {kind}", "warning")
            continue
        try:
            names = [r[0].decode() if isinstance(r[0], bytes) else r[0] for r in
                     c.execute_command("GRAPH.QUERY", "probe", "CALL dbms.procedures() YIELD name RETURN name", "--compact")[1]]
        except Exception as exc:
            names = [f"error {type(exc).__name__}"]
        algos = sorted(str(n) for n in names if "algo" in str(n))
        note("Algorithms", f"{algos}")
        pid = uuid.uuid4().hex
        try:
            c.execute_command("GRAPH.QUERY", "graphhacks_probe", f"CREATE (:Probe {{id:'{pid}'}}) RETURN 1")
            c.execute_command("GRAPH.QUERY", "graphhacks_probe", f"MATCH (p:Probe {{id:'{pid}'}}) DELETE p")
            note("Write", "create + delete OK")
        except Exception as exc:
            note("Write", f"FAIL {type(exc).__name__}", "warning")
        return
    note("Result", "No encrypted connection worked", "warning")


if __name__ == "__main__":
    main()


def plain_reachability():
    """Open a TCP socket and send an unauthenticated PING. No credentials are sent."""
    import socket
    try:
        s = socket.create_connection((os.environ["FALKOR_HOST"], int(os.environ["FALKOR_PORT"])), timeout=8)
        note("TCP", "port reachable (TCP connect OK)")
        s.settimeout(8)
        s.sendall(b"PING\r\n")
        reply = s.recv(200).decode(errors="replace").strip()
        s.close()
        # Typical: '-NOAUTH Authentication required.' => plaintext Redis protocol, auth enabled.
        note("Plain PING", f"server replied without TLS: {reply[:60]!r}")
    except Exception as exc:
        note("TCP", f"FAIL {type(exc).__name__}", "warning")


if __name__ == "__main__" and os.getenv("FALKOR_HOST"):
    plain_reachability()
