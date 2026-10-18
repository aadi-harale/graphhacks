"""Track 01 MCP host: bounded FalkorDB reads and one guarded draft action.

Install: pip install -r requirements-mcp.txt
Run:     python -m app.track1_mcp   (stdio)
The local agent advertises the MCP tool catalog to its model, then uses
a real MCP stdio ClientSession for every graph tool selected by the model.
The only write tool creates a fictional internal follow-up draft; no real
supplier message or allocation can be initiated by the MCP agent.
"""
import os
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

@mcp.tool()
def reconcile_ledger(case_id: str) -> dict:
    """Run FalkorDB algo.maxFlow over every open delivery and claim in the case.
    Returns units settleable, units forced in every maximum allocation (the only
    ones that may be proposed), ambiguous units, and what is still owed."""
    return graph_tools(case_id,"unused").reconcile_ledger()

@mcp.tool()
def create_followup_draft(case_id: str, receipt_id: str, action: str) -> dict:
    """Persist only an internal graph-linked clarification/review draft.
    The policy checks the actual graph state. Nothing gets sent to suppliers.
    """
    if os.getenv("ALLOW_DEMO_MUTATIONS")!="1":
        raise ValueError("Synthetic write tools disabled")
    t=graph_tools(case_id,receipt_id)
    t.investigate_receipt()
    t.trace_claim_evidence()
    return t.create_followup_draft(action)

if __name__=="__main__":
    mcp.run()
