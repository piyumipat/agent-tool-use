import json
from collections.abc import Sequence

from openai import AsyncOpenAI

from agent_tool_use.core.loop import Message, ModelResponse, ToolCall, ToolDefinition


class ChatCompletionModel:
    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        if not model:
            raise ValueError("LLM_MODEL must be configured")
        self.client = client
        self.model = model

    async def complete(
        self, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> ModelResponse:
        sdk_messages = []
        for message in messages:
            item = {"role": message.role, "content": message.content}
            if message.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments),
                        },
                    }
                    for call in message.tool_calls
                ]
            if message.tool_call_id:
                item["tool_call_id"] = message.tool_call_id
            sdk_messages.append(item)

        sdk_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]
        response = await self.client.chat.completions.create(
            model=self.model, messages=sdk_messages, tools=sdk_tools
        )
        if not response.choices:
            raise ValueError("Model returned no choices")
        message = response.choices[0].message
        calls = []
        for call in message.tool_calls or []:
            if call.type != "function":
                raise ValueError("Model returned an unsupported tool call")
            try:
                arguments = json.loads(call.function.arguments)
            except json.JSONDecodeError as error:
                raise ValueError("Model returned invalid tool arguments") from error
            if not isinstance(arguments, dict):
                raise ValueError("Model tool arguments must be an object")
            calls.append(ToolCall(call.id, call.function.name, arguments))
        return ModelResponse(message.content, tuple(calls))
