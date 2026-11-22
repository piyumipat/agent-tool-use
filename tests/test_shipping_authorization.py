import asyncio
import secrets
import unittest

import httpx2

from agent_tool_use.mcp.client import connect_mcp
from examples.shipping.server import build_app
from examples.shipping.shipments import ShipmentStore


class ShippingAuthorizationTests(unittest.TestCase):
    def test_read_token_cannot_create_and_write_token_can_retry(self) -> None:
        async def check() -> None:
            read_token = secrets.token_urlsafe(24)
            write_token = secrets.token_urlsafe(24)
            store = ShipmentStore()
            app = build_app(read_token, write_token=write_token, store=store)
            arguments = {
                "option_id": "standard",
                "billable_weight_kg": 4.8,
                "destination_zone": "domestic",
                "request_id": "request-1",
            }
            async with app.router.lifespan_context(app):
                async with connect_mcp(
                    "http://127.0.0.1:8000/mcp",
                    read_token,
                    transport=httpx2.ASGITransport(app=app),
                ) as client:
                    denied = await client.call_tool("create_shipment", arguments)
                    self.assertTrue(denied.is_error)
                    self.assertEqual(len(store.shipments), 0)
                async with connect_mcp(
                    "http://127.0.0.1:8000/mcp",
                    write_token,
                    transport=httpx2.ASGITransport(app=app),
                ) as client:
                    created = await client.call_tool("create_shipment", arguments)
                    repeated = await client.call_tool("create_shipment", arguments)
                    self.assertFalse(created.is_error)
                    self.assertFalse(repeated.is_error)
                    self.assertEqual(created.structured_content, repeated.structured_content)
                    self.assertEqual(created.structured_content["shipment_id"], "SHIP-0001")
                    self.assertEqual(len(store.shipments), 1)

        asyncio.run(check())
