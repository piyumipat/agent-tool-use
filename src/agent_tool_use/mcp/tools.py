from typing import Any

from mcp import Client

from agent_tool_use.core.loop import Tool, ToolDefinition


async def discover_mcp_tools(
    client: Client, allowed_names: set[str], approval_names: set[str] | None = None
) -> tuple[Tool, ...]:
    approval_names = approval_names or set()
    if not approval_names <= allowed_names:
        raise ValueError("Approval tools must be allowed tools")
    listed = await client.list_tools()
    available = {tool.name: tool for tool in listed.tools}
    missing = allowed_names - available.keys()
    if missing:
        raise ValueError(f"MCP tools unavailable: {', '.join(sorted(missing))}")

    bound = []
    for name in sorted(allowed_names):
        remote = available[name]

        async def invoke(arguments: dict[str, Any], tool_name: str = name) -> Any:
            result = await client.call_tool(tool_name, arguments)
            if result.is_error:
                raise ValueError("MCP tool returned an error")
            if result.structured_content is not None:
                return result.structured_content
            return [part.text for part in result.content if part.type == "text"]

        definition = ToolDefinition(name, remote.description or "", remote.input_schema)
        bound.append(Tool(definition, invoke, requires_approval=name in approval_names, source="mcp"))
    return tuple(bound)
