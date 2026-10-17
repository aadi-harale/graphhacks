"""Optional Track 01 MCP host: bounded read-only FalkorDB investigations.

Install: pip install -r requirements-mcp.txt
Run:     python -m app.track1_mcp   (stdio)
A model hosted in an MCP-capable client can choose these graph tools.
The local web app's agent uses the same underlying typed tools via function
calling; it does not yet use MCP as its transport. No write tools are exposed.
"""
from mcp.server import MCPServer
from .graph import FalkorStore
from .resolve import ResolveStore
from .track1_agent import AgentSession, GraphTools

mcp=MCPServer("SahiAaya Graph Investigator")

def graph_tools(case_id: str, receipt_id: str):
    store=ResolveStore(FalkorStore(graph_name="sahiaaya_resolve"))
    return GraphTools(store,AgentSession(case_id,receipt_id))

@mcp.tool()
def list_case_receipts(case_id: str) -> dict:
    """List receipt IDs and dates in one fictional supplier case."""
    return graph_tools(case_id,"unused").list_case_receipts()

@mcp.tool()
def investigate_receipt(case_id: str, receipt_id: str) -> dict:
    """Fetch the connected claims and canonical evidence-based next action."""
    return graph_tools(case_id,receipt_id).investigate_receipt()

@mcp.tool()
def trace_claim_evidence(case_id: str, receipt_id: str) -> dict:
    """Return read-only paths: receipt → eligible claim → source document."""
    t=graph_tools(case_id,receipt_id)
    t.investigate_receipt()
    return t.trace_claim_evidence()

@mcp.tool()
def inspect_cross_delivery(case_id: str, receipt_id: str, claim_id: str) -> dict:
    """Follow one obligation across all linked deliveries and prior allocations."""
    t=graph_tools(case_id,receipt_id)
    t.investigate_receipt()
    return t.inspect_cross_delivery(claim_id)

if __name__=="__main__":
    mcp.run()
