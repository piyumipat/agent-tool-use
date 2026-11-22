import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from jsonschema import ValidationError, validate


@dataclass(frozen=True)
class ToolDefinition:

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Message:

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None


@dataclass(frozen=True)
class ModelResponse:

    text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


class ModelClient(Protocol):

    async def complete(
        self, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> ModelResponse: ...


ToolHandler = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass(frozen=True)
class Tool:

    definition: ToolDefinition
    handler: ToolHandler
    requires_approval: bool = False
    source: Literal["local", "mcp"] = "local"


@dataclass(frozen=True)
class ToolEvent:

    name: str
    status: Literal["ok", "error", "blocked"]


@dataclass(frozen=True)
class RunResult:

    answer: str
    model_calls: int
    tool_events: tuple[ToolEvent, ...]


@dataclass
class AgentRunner:

    model: ModelClient
    tools: Sequence[Tool]
    max_model_calls: int = 8
    approve: Callable[[str, dict[str, Any]], Awaitable[bool]] | None = None
    trace: Callable[[str], None] | None = None
    _by_name: dict[str, Tool] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_model_calls < 1:
            raise ValueError("max_model_calls must be positive")
        self._by_name = {tool.definition.name: tool for tool in self.tools}
        if len(self._by_name) != len(self.tools):
            raise ValueError("Tool names must be unique")

    async def run(self, question: str, instructions: str = "") -> RunResult:
        messages = []
        if instructions:
            messages.append(Message(role="system", content=instructions))
        messages.append(Message(role="user", content=question))
        definitions = tuple(tool.definition for tool in self.tools)
        events: list[ToolEvent] = []
        recent_events: list[ToolEvent] = []

        for model_calls in range(1, self.max_model_calls + 1):
            if recent_events:
                results = ", ".join(
                    f"{event.name} ({event.status})" for event in recent_events
                )
                self._report(f"[agent] Input: conversation and latest tool results: {results}")
            else:
                self._report("[agent] Input: your request and task instructions")
            response = await self.model.complete(tuple(messages), definitions)
            if not response.tool_calls:
                if not response.text:
                    raise ValueError("Model returned neither an answer nor tool calls")
                self._report("[agent] Output: answer to user")
                return RunResult(response.text, model_calls, tuple(events))

            names = ", ".join(call.name for call in response.tool_calls)
            self._report(f"[agent] Output: call {names}")
            messages.append(
                Message(role="assistant", content=response.text or "", tool_calls=response.tool_calls)
            )
            recent_events = []
            for call in response.tool_calls:
                result, status = await self._invoke(call)
                event = ToolEvent(call.name, status)
                events.append(event)
                recent_events.append(event)
                messages.append(
                    Message(
                        role="tool",
                        content=json.dumps(result, ensure_ascii=False),
                        tool_call_id=call.id,
                    )
                )

        raise RuntimeError("Agent reached the model-call limit without an answer")

    async def _invoke(self, call: ToolCall) -> tuple[dict[str, Any], Literal["ok", "error", "blocked"]]:
        tool = self._by_name.get(call.name)
        if tool is None:
            self._report(f"[agent] Rejected unavailable tool: {call.name}")
            return {"ok": False, "error": "Tool is not available"}, "error"
        try:
            validate(call.arguments, tool.definition.parameters)
            if tool.requires_approval:
                self._report(f"[approval] Review requested for {call.name}")
                if self.approve is None or not await self.approve(call.name, call.arguments):
                    self._report(f"[approval] Declined {call.name}; no tool call sent")
                    return {"ok": False, "error": "User did not approve this action"}, "blocked"
                self._report(f"[approval] Approved {call.name}")
            source = "MCP client" if tool.source == "mcp" else "local tool"
            self._report(f"[{source}] Calling {call.name}")
            value = await tool.handler(call.arguments)
        except (ValidationError, ValueError, TypeError) as exc:
            self._report(f"[agent] {call.name} failed: {exc}")
            return {"ok": False, "error": str(exc)}, "error"
        self._report(f"[{source}] {call.name} completed")
        return {"ok": True, "result": value}, "ok"

    def _report(self, message: str) -> None:
        if self.trace is not None:
            self.trace(message)
