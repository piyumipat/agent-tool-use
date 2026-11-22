import json
import unittest
from collections.abc import Sequence

from agent_tool_use.core.loop import (
    AgentRunner,
    Message,
    ModelResponse,
    Tool,
    ToolCall,
    ToolDefinition,
)


class FakeModel:

    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = responses
        self.requests: list[tuple[Sequence[Message], Sequence[ToolDefinition]]] = []

    async def complete(
        self, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> ModelResponse:
        self.requests.append((messages, tools))
        return self.responses.pop(0)


class AgentLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_result_returns_to_model_before_final_answer(self) -> None:
        async def add(arguments: dict) -> dict:
            return {"total": arguments["a"] + arguments["b"]}

        definition = ToolDefinition(
            "add",
            "Add two numbers",
            {
                "type": "object",
                "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                "required": ["a", "b"],
                "additionalProperties": False,
            },
        )
        model = FakeModel(
            [
                ModelResponse(tool_calls=(ToolCall("call-1", "add", {"a": 2, "b": 3}),)),
                ModelResponse(text="The total is 5."),
            ]
        )
        result = await AgentRunner(model, [Tool(definition, add)]).run("Add 2 and 3")

        self.assertEqual(result.answer, "The total is 5.")
        self.assertEqual(result.model_calls, 2)
        self.assertEqual([(event.name, event.status) for event in result.tool_events], [("add", "ok")])
        self.assertEqual([tool.name for tool in model.requests[0][1]], ["add"])
        tool_message = model.requests[1][0][-1]
        self.assertEqual(tool_message.tool_call_id, "call-1")
        self.assertEqual(json.loads(tool_message.content), {"ok": True, "result": {"total": 5}})

    async def test_unknown_tool_is_not_executed(self) -> None:
        model = FakeModel(
            [
                ModelResponse(tool_calls=(ToolCall("call-1", "not_allowed", {}),)),
                ModelResponse(text="I cannot use that tool."),
            ]
        )
        result = await AgentRunner(model, []).run("Use the unknown tool")
        self.assertEqual(result.tool_events[0].status, "error")
        self.assertEqual(
            json.loads(model.requests[1][0][-1].content)["error"], "Tool is not available"
        )

    async def test_invalid_arguments_never_reach_handler(self) -> None:
        called = False

        async def handler(arguments: dict) -> None:
            nonlocal called
            called = True

        definition = ToolDefinition(
            "read_number", "Read a number", {"type": "object", "properties": {"n": {"type": "number"}}, "required": ["n"]}
        )
        model = FakeModel(
            [
                ModelResponse(tool_calls=(ToolCall("call-1", "read_number", {"n": "wrong"}),)),
                ModelResponse(text="The input was invalid."),
            ]
        )
        result = await AgentRunner(model, [Tool(definition, handler)]).run("Read a number")
        self.assertFalse(called)
        self.assertEqual(result.tool_events[0].status, "error")
        self.assertFalse(json.loads(model.requests[1][0][-1].content)["ok"])

    async def test_model_call_limit_stops_repeated_tool_requests(self) -> None:
        model = FakeModel(
            [ModelResponse(tool_calls=(ToolCall(str(i), "unknown", {}),)) for i in range(2)]
        )
        with self.assertRaisesRegex(RuntimeError, "model-call limit"):
            await AgentRunner(model, [], max_model_calls=2).run("Keep going")
        self.assertEqual(len(model.requests), 2)


class ApprovalTests(unittest.IsolatedAsyncioTestCase):
    async def test_declined_action_never_reaches_handler(self) -> None:
        called = False

        async def create(arguments: dict) -> dict:
            nonlocal called
            called = True
            return {"created": True}

        async def deny(name: str, arguments: dict) -> bool:
            return False

        definition = ToolDefinition("create", "Create a record", {"type": "object"})
        model = FakeModel([
            ModelResponse(tool_calls=(ToolCall("call-1", "create", {}),)),
            ModelResponse(text="No record was created."),
        ])
        result = await AgentRunner(
            model, [Tool(definition, create, requires_approval=True)], approve=deny
        ).run("Create a record")
        self.assertFalse(called)
        self.assertEqual(result.tool_events[0].status, "blocked")
        self.assertFalse(json.loads(model.requests[1][0][-1].content)["ok"])

    async def test_approved_action_reaches_handler(self) -> None:
        called = False

        async def create(arguments: dict) -> dict:
            nonlocal called
            called = True
            return {"created": True}

        async def allow(name: str, arguments: dict) -> bool:
            return True

        definition = ToolDefinition("create", "Create a record", {"type": "object"})
        model = FakeModel([
            ModelResponse(tool_calls=(ToolCall("call-1", "create", {}),)),
            ModelResponse(text="Created."),
        ])
        result = await AgentRunner(
            model, [Tool(definition, create, requires_approval=True)], approve=allow
        ).run("Create a record")
        self.assertTrue(called)
        self.assertEqual(result.tool_events[0].status, "ok")
