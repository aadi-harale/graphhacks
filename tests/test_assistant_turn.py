"""Provider-specific data on tool calls must survive the round trip (Gemini thought signatures)."""
from types import SimpleNamespace as NS
from openai.types.chat import ChatCompletionMessage
from app.track1_agent import assistant_turn


def test_gemini_thought_signature_is_echoed_back():
    msg = ChatCompletionMessage.model_validate({
        "role": "assistant", "content": None,
        "tool_calls": [{"id": "c1", "type": "function",
                        "function": {"name": "investigate_receipt", "arguments": "{}"},
                        "extra_content": {"google": {"thought_signature": "sig123"}}}]})
    turn = assistant_turn(msg, msg.tool_calls)
    assert turn["tool_calls"][0]["extra_content"] == {"google": {"thought_signature": "sig123"}}
    assert turn["tool_calls"][0]["function"]["name"] == "investigate_receipt"


def test_plain_providers_and_test_doubles_keep_the_minimal_shape():
    call = NS(id="c1", function=NS(name="list_case_receipts", arguments="{}"))
    turn = assistant_turn(NS(content=None, tool_calls=[call]), [call])
    assert turn == {"role": "assistant", "content": None,
                    "tool_calls": [{"id": "c1", "type": "function",
                                    "function": {"name": "list_case_receipts", "arguments": "{}"}}]}


def test_rate_limited_calls_are_retried_then_succeed(monkeypatch):
    import asyncio
    from app import track1_mcp_loop as loop

    class RateLimitError(Exception):
        pass

    calls = {"n": 0}

    def create(**kw):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RateLimitError("slow down")
        return "ok"

    async def no_sleep(_):
        return None

    monkeypatch.setattr(loop.asyncio, "sleep", no_sleep)
    client = NS(chat=NS(completions=NS(create=create)))
    assert asyncio.run(loop._create_with_backoff(client, model="m")) == "ok"
    assert calls["n"] == 3


def test_other_errors_are_not_retried():
    import asyncio
    import pytest
    from app import track1_mcp_loop as loop

    def create(**kw):
        raise ValueError("bad request")

    client = NS(chat=NS(completions=NS(create=create)))
    with pytest.raises(ValueError):
        asyncio.run(loop._create_with_backoff(client, model="m"))
