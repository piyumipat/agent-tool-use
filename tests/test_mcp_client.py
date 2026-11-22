import asyncio
import secrets
import unittest

import httpx2

from agent_tool_use.mcp.client import connect_mcp
from examples.shipping.server import build_app


class MCPClientTests(unittest.TestCase):
    def test_authenticated_client_lists_and_calls_shipping_tool(self) -> None:
        async def check() -> None:
            token = secrets.token_urlsafe(24)
            app = build_app(token)
            transport = httpx2.ASGITransport(app=app)
            async with app.router.lifespan_context(app):
                async with connect_mcp(
                    "http://127.0.0.1:8000/mcp", token, transport=transport
                ) as client:
                    listed = await client.list_tools()
                    self.assertEqual(
                        sorted(tool.name for tool in listed.tools), ["create_shipment", "get_shipping_options"]
                    )
                    result = await client.call_tool(
                        "get_shipping_options",
                        {"billable_weight_kg": 4.8, "destination_zone": "domestic"},
                    )
                    self.assertFalse(result.is_error)
                    self.assertEqual(len(result.structured_content["result"]), 3)

        asyncio.run(check())

    def test_empty_token_is_rejected_before_connecting(self) -> None:
        async def check() -> None:
            with self.assertRaisesRegex(ValueError, "MCP token"):
                async with connect_mcp("http://127.0.0.1:8000/mcp", ""):
                    pass

        asyncio.run(check())
