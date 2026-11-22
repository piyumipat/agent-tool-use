import json
import unittest
from types import SimpleNamespace

from agent_tool_use.core.loop import Message, ToolCall, ToolDefinition
from agent_tool_use.core.model import ChatCompletionModel


class FakeCompletions:
    def __init__(self, response) -> None:
        self.response = response
        self.request = None

    async def create(self, **kwargs):
        self.request = kwargs
        return self.response


class ModelAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_translates_tool_history_and_model_call(self) -> None:
        call = SimpleNamespace(
            id="next-call",
            type="function",
            function=SimpleNamespace(name="lookup", arguments='{"code": "A"}'),
        )
        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[call]))]
        )
        endpoint = FakeCompletions(completion)
        client = SimpleNamespace(chat=SimpleNamespace(completions=endpoint))
        model = ChatCompletionModel(client, "demo-model")
        messages = [
            Message("user", "Find a code"),
            Message("assistant", "", (ToolCall("old-call", "lookup", {"code": "B"}),)),
            Message("tool", '{"ok": true}', tool_call_id="old-call"),
        ]
        tools = [ToolDefinition("lookup", "Look up a code", {"type": "object"})]

        result = await model.complete(messages, tools)

        self.assertEqual(result.tool_calls, (ToolCall("next-call", "lookup", {"code": "A"}),))
        self.assertEqual(endpoint.request["messages"][2]["tool_call_id"], "old-call")
        self.assertEqual(
            json.loads(endpoint.request["messages"][1]["tool_calls"][0]["function"]["arguments"]),
            {"code": "B"},
        )
        self.assertEqual(endpoint.request["tools"][0]["function"]["name"], "lookup")

    async def test_rejects_non_object_tool_arguments(self) -> None:
        call = SimpleNamespace(
            id="call-1", type="function", function=SimpleNamespace(name="lookup", arguments="[]")
        )
        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[call]))]
        )
        client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions(completion)))
        with self.assertRaisesRegex(ValueError, "must be an object"):
            await ChatCompletionModel(client, "demo-model").complete([], [])
