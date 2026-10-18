"""Fail-closed TLS-only FalkorDB Cloud smoke test; synthetic node only."""
import os
import sys
import uuid
import redis

def main():
    required = ("FALKOR_HOST", "FALKOR_PORT", "FALKOR_PASSWORD")
    if any(not os.getenv(k) for k in required):
        raise RuntimeError("Missing one or more required FalkorDB Cloud secrets")
    if os.getenv("FALKOR_SSL", "").lower() != "true":
        raise RuntimeError("Refusing to send database credentials without TLS")
    port = int(os.environ["FALKOR_PORT"])
    if not 1 <= port <= 65535:
        raise RuntimeError("Invalid Cloud port")
    client = redis.Redis(
        host=os.environ["FALKOR_HOST"],
        port=port,
        username=os.getenv("FALKOR_USERNAME") or None,
        password=os.environ["FALKOR_PASSWORD"],
        ssl=True,
        ssl_cert_reqs="required",
        socket_connect_timeout=8,
        socket_timeout=15,
        decode_responses=False,
    )
    graph = "graphhacks"
    probe_id = uuid.uuid4().hex
    # Generated random token, interpolated only after strict hex validation.
    assert len(probe_id) == 32 and all(c in "0123456789abcdef" for c in probe_id)
    created = False
    try:
        client.ping()
        print("PASS: TLS-authenticated Redis PING")
        client.execute_command("GRAPH.QUERY", graph,
            f"CREATE (:CloudConnectivityProbe {{id:'{probe_id}'}}) RETURN 1", "--compact")
        created = True
        print("PASS: synthetic graph write")
        result = client.execute_command("GRAPH.RO_QUERY", graph,
            f"MATCH (p:CloudConnectivityProbe {{id:'{probe_id}'}}) RETURN p.id", "--compact")
        # The protocol contains typed scalar wrappers; inspect result rows without
        # assuming a specific FalkorDB Python SDK object representation.
        if not isinstance(result, (list, tuple)) or len(result) < 2 or not result[1]:
            raise RuntimeError("Graph read did not return the inserted probe")
        print("PASS: synthetic graph read")
    finally:
        if created:
            client.execute_command("GRAPH.QUERY", graph,
                f"MATCH (p:CloudConnectivityProbe {{id:'{probe_id}'}}) DELETE p", "--compact")
            result = client.execute_command("GRAPH.RO_QUERY", graph,
                f"MATCH (p:CloudConnectivityProbe {{id:'{probe_id}'}}) RETURN p.id", "--compact")
            if not isinstance(result, (list, tuple)) or len(result) < 2 or result[1]:
                raise RuntimeError("Probe cleanup verification failed")
            print("PASS: probe deletion and absence verified")
        client.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Never print exception text: errors may contain host or credentials.
        from redis.exceptions import AuthenticationError, ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError, ResponseError
        import ssl
        if isinstance(exc, AuthenticationError):
            category = "AUTHENTICATION"
        elif isinstance(exc, ssl.SSLError):
            category = "TLS_HANDSHAKE_OR_CERTIFICATE"
        elif isinstance(exc, (RedisTimeoutError, TimeoutError)):
            category = "NETWORK_TIMEOUT"
        elif isinstance(exc, RedisConnectionError):
            category = "NETWORK_OR_TLS"
        elif isinstance(exc, ResponseError):
            category = "GRAPH_QUERY_OR_PERMISSIONS"
        else:
            category = "CONFIGURATION_OR_OTHER"
        print(f"FAIL CATEGORY: {category}; exception type: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
