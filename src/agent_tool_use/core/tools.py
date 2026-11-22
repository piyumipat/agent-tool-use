from collections.abc import Callable
from typing import Any

from agent_tool_use.core.loop import Tool, ToolDefinition


def local_tool(definition: ToolDefinition, function: Callable[..., Any]) -> Tool:
    async def invoke(arguments: dict[str, Any]) -> Any:
        return function(**arguments)

    return Tool(definition, invoke)
