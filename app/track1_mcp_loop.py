"""Model-selected tools routed through a real MCP client/server connection.

The LLM chooses a named function; a bounded MCP ClientSession invokes the
FalkorDB tool host. It cannot generate Cypher or approve real settlements.
"""
from __future__ import annotations
import asyncio
import json
import os
import sys

from .track1_agent import TOOL_SCHEMAS, SYSTEM_PROMPT, AgentSession


async def run_agent_mcp(case_id: str, receipt_id: str, query: str, store=None,
                        client=None, model: str | None=None, max_rounds: int=7):
    """Model decides tools, MCP transports calls, FalkorDB supplies evidence.

    The optional store parameter is unused; database access is exclusively
    in the MCP subprocess. Tests inject a fake model but use real MCP calls.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    if client is None:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("Set OPENAI_API_KEY to enable real model tool selection")
        from openai import OpenAI
        client=OpenAI()

    sess=AgentSession(case_id,receipt_id)
    # These are the model's actual requested tool names and arguments, paired
    # with the bounded evidence returned over MCP. No hidden reasoning is claimed.
    successful_calls=0

    name=model or os.getenv("SAHIAAYA_AGENT_MODEL","gpt-4o-mini")
    messages=[{"role":"system","content":SYSTEM_PROMPT},
              {"role":"user","content":f"Investigate fictional case {case_id}, receipt {receipt_id}. {query[:280]}"}]
    schemas={item["function"]["name"]:item["function"]["parameters"] for item in TOOL_SCHEMAS}
    # The graph tool host needs database/local-mode settings, never a model API key.
    child_env={k:v for k,v in os.environ.items() if k not in
               ("OPENAI_API_KEY","OPENAI_ORG_ID","OPENAI_PROJECT_ID")}
    server=StdioServerParameters(command=sys.executable,args=["-m","app.track1_mcp"],
                                env=child_env)
    async with stdio_client(server) as (read,write):
        async with ClientSession(read,write) as mcp:
            await mcp.initialize()
            # Discover the actual MCP-advertised catalog. The agent never sees
            # case_id/receipt_id as writable parameters; they are injected from
            # the original validated request when the selected MCP tool runs.
            advertised={t.name:t for t in (await mcp.list_tools()).tools}
            if not set(schemas).issubset(advertised):
                raise RuntimeError("MCP host missing required investigation tools")
            model_tools=[]
            for definition in TOOL_SCHEMAS:
                spec=dict(definition["function"])
                spec["description"]=advertised[spec["name"]].description or spec["description"]
                model_tools.append({"type":"function","function":spec})

            for round_index in range(max_rounds):
                response=await asyncio.to_thread(
                    client.chat.completions.create,model=name,messages=messages,
                    tools=model_tools,tool_choice="auto",temperature=0)
                msg=response.choices[0].message
                calls=msg.tool_calls or []
                if not calls:
                    if not sess.inspected or not sess.evidence_traced:
                        raise ValueError("Agent did not complete source-backed graph investigation")
                    return {"case_id":case_id,"receipt_id":receipt_id,
                            "model_summary":msg.content or "",
                            "authoritative_decision":sess.decision,
                            "draft":sess.draft,
                            "tool_trace":sess.trace,
                            "evidence_paths":sess.evidence_paths,
                            "engine":"model_selected_mcp_graph_tools",
                            "transport":"MCP stdio / ClientSession",
                            "provenance":"actual MCP responses; model tool selection" if client is not None else "unverified",
                            "model_name":name,
                            "tool_rounds":round_index+1,
                            "successful_tool_calls":successful_calls,
                            "disclaimer":"Synthetic graph; drafts are not sent and settlement needs retailer approval."}

                messages.append({"role":"assistant","content":msg.content,
                                 "tool_calls":[{"id":c.id,"type":"function",
                                                "function":{"name":c.function.name,"arguments":c.function.arguments}}
                                               for c in calls]})
                for c in calls:
                    tool=c.function.name
                    try:
                        if tool not in schemas:
                            raise ValueError("Tool not in bounded catalog")
                        params=json.loads(c.function.arguments or "{}")
                        if not isinstance(params,dict):raise ValueError("Parameters must be an object")
                        schema=schemas[tool]
                        if set(params)-set(schema["properties"]) or set(schema.get("required",[]))-set(params):
                            raise ValueError("Unexpected or missing tool parameters")
                        if tool in ("trace_claim_evidence","inspect_cross_delivery") and not sess.inspected:
                            raise ValueError("Inspect receipt first")
                        if tool=="create_followup_draft" and (not sess.inspected or not sess.evidence_traced):
                            raise ValueError("Inspect and trace evidence before drafting")
                        # IDs come from validated request, never model-controlled parameters.
                        result=await mcp.call_tool(tool,{"case_id":case_id,"receipt_id":receipt_id,**params})
                        if result.is_error:
                            raise ValueError("MCP operation rejected: "+
                                             "; ".join(getattr(c,"text","") for c in result.content)[:300])
                        content=getattr(result,"structured_content",None)
                        if content is None:
                            raw=next((getattr(c,"text",None) for c in result.content if getattr(c,"text",None)),None)
                            if raw is None:raise ValueError("MCP tool returned no evidence")
                            content=json.loads(raw)
                        if isinstance(content,dict) and set(content)=={"result"}:
                            content=content["result"]
                        if not isinstance(content,dict):
                            raise ValueError("MCP tool returned unexpected data")
                        if tool=="investigate_receipt":
                            sess.inspected=True
                            sess.decision=content["decision"]
                        elif tool=="trace_claim_evidence":
                            sess.evidence_traced=True
                            sess.evidence_paths=[{"receipt":x["receipt"],"obligation":x["obligation"],
                                                  "document":x["document"]} for x in content.get("paths",[])]
                        elif tool=="create_followup_draft":
                            sess.draft=content["draft"]
                        # The case contract permits only explicitly fictional records.
                        # Keep actual tool results for judges instead of fabricated
                        # summaries, but bound trace growth and never log credentials.
                        raw_result=json.dumps(content,default=str,ensure_ascii=False)
                        if len(raw_result)>18000:
                            raise ValueError("MCP tool result exceeds auditable size limit")
                        successful_calls+=1
                        sess.trace.append({"round":round_index+1,"tool":tool,
                                           "arguments":params,
                                           "tool_purpose":schemas[tool] and next(
                                               definition["function"]["description"]
                                               for definition in TOOL_SCHEMAS
                                               if definition["function"]["name"]==tool),
                                           "transport":"mcp_stdio",
                                           "result_kind":content.get("kind","information"),
                                           "result":content,
                                           "evidence_rows":content.get("evidence_rows",0)})
                        outcome=content
                    except (ValueError,TypeError,KeyError) as exc:
                        outcome={"kind":"blocked","error":str(exc)}
                        sess.trace.append({"round":round_index+1,"tool":tool,
                                           "arguments":params if isinstance(params,dict) else {},
                                           "transport":"mcp_stdio",
                                           "result_kind":"blocked","reason":str(exc)})
                    messages.append({"role":"tool","tool_call_id":c.id,
                                     "content":json.dumps(outcome,default=str)})
    raise RuntimeError("Agent exceeded bounded tool selection rounds")
