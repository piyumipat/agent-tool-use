import asyncio
import secrets
import unittest

from mcp import Client
from starlette.testclient import TestClient

from examples.shipping.server import build_app, build_server


class ShippingMCPServerTests(unittest.TestCase):
    def test_shipping_tool_is_registered(self) -> None:
        async def check() -> None:
            server = build_server(secrets.token_urlsafe(24))
            async with Client(server) as client:
                listed = await client.list_tools()
                self.assertEqual(sorted(tool.name for tool in listed.tools), ["create_shipment", "get_shipping_options"])
                result = await client.call_tool(
                    "get_shipping_options",
                    {"billable_weight_kg": 4.8, "destination_zone": "domestic"},
                )
                self.assertFalse(result.is_error)
                self.assertEqual(len(result.structured_content["result"]), 3)

        asyncio.run(check())

    def test_http_endpoint_accepts_a_valid_read_token(self) -> None:
        token = secrets.token_urlsafe(24)
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                    "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "1"},
                    "io.modelcontextprotocol/clientCapabilities": {},
                }
            },
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "MCP-Protocol-Version": "2026-07-28",
            "Mcp-Method": "tools/list",
            "Accept": "application/json, text/event-stream",
        }
        with TestClient(build_app(token), base_url="http://127.0.0.1:8000") as client:
            response = client.post("/mcp", json=request, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["tools"][0]["name"], "get_shipping_options")

    def test_http_endpoint_requires_a_bearer_token(self) -> None:
        token = secrets.token_urlsafe(24)
        with TestClient(build_app(token)) as client:
            response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        self.assertEqual(response.status_code, 401)
        self.assertIn("Bearer", response.headers["www-authenticate"])
