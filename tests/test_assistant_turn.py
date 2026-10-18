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
