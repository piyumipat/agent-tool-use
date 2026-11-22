import asyncio
import json
import secrets
import unittest
from collections.abc import Sequence

import httpx2

from agent_tool_use.core.loop import Message, ModelResponse, ToolCall, ToolDefinition
from agent_tool_use.mcp.client import connect_mcp
from examples.shipping.agent import run_shipping
from examples.shipping.server import build_app


class ShippingFakeModel:
    def __init__(self) -> None:
        self.turn = 0

    async def complete(
        self, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> ModelResponse:
        self.turn += 1
        if self.turn == 1:
            assert {tool.name for tool in tools} == {
                "calculate_billable_weight", "get_shipping_options"
            }
            return ModelResponse(
                tool_calls=(
                    ToolCall(
                        "weight-1",
                        "calculate_billable_weight",
                        {"length_cm": 40, "width_cm": 30, "height_cm": 20, "actual_weight_kg": 3},
                    ),
                )
            )
        if self.turn == 2:
            weight = json.loads(messages[-1].content)["result"]["billable_weight_kg"]
            assert weight == 4.8
            return ModelResponse(
                tool_calls=(
                    ToolCall(
                        "options-1",
                        "get_shipping_options",
                        {"billable_weight_kg": weight, "destination_zone": "domestic"},
                    ),
                )
            )
        options = json.loads(messages[-1].content)["result"]["result"]
        assert [option["option_id"] for option in options] == ["economy", "standard", "express"]
        return ModelResponse(text="Standard costs €11 and arrives in 3 days.")


class ShippingAgentTests(unittest.TestCase):
    def test_read_only_flow_uses_local_and_authenticated_mcp_tools(self) -> None:
        async def check() -> None:
            token = secrets.token_urlsafe(24)
            app = build_app(token)
            async with app.router.lifespan_context(app):
                async with connect_mcp(
                    "http://127.0.0.1:8000/mcp", token,
                    transport=httpx2.ASGITransport(app=app),
                ) as client:
                    model = ShippingFakeModel()
                    trace = []
                    result = await run_shipping(
                        "Ship a 40 x 30 x 20 cm parcel weighing 3 kg within 3 days for €12",
                        model,
                        client,
                        trace=trace.append,
                    )
            self.assertEqual(result.answer, "Standard costs €11 and arrives in 3 days.")
            self.assertEqual(result.model_calls, 3)
            self.assertEqual(
                [(event.name, event.status) for event in result.tool_events],
                [("calculate_billable_weight", "ok"), ("get_shipping_options", "ok")],
            )
            self.assertIn("[local tool] Calling calculate_billable_weight", trace)
            self.assertIn("[local tool] Billable weight: 4.8 kg", trace)
            self.assertIn("[MCP client] Calling get_shipping_options", trace)
            self.assertIn("[agent] Input: your request and task instructions", trace)
            self.assertIn("[agent] Output: call calculate_billable_weight", trace)
            self.assertIn(
                "[agent] Input: conversation and latest tool results: calculate_billable_weight (ok)",
                trace,
            )
            self.assertIn("[agent] Output: answer to user", trace)

        asyncio.run(check())


class BookingFakeModel:
    def __init__(self) -> None:
        self.turn = 0

    async def complete(
        self, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> ModelResponse:
        self.turn += 1
        if self.turn == 1:
            assert {tool.name for tool in tools} == {
                "calculate_billable_weight", "get_shipping_options", "create_shipment"
            }
            return ModelResponse(tool_calls=(ToolCall(
                "weight-1", "calculate_billable_weight",
                {"length_cm": 40, "width_cm": 30, "height_cm": 20, "actual_weight_kg": 3},
            ),))
        if self.turn == 2:
            weight = json.loads(messages[-1].content)["result"]["billable_weight_kg"]
            return ModelResponse(tool_calls=(ToolCall(
                "options-1", "get_shipping_options",
                {"billable_weight_kg": weight, "destination_zone": "domestic"},
            ),))
        if self.turn == 3:
            return ModelResponse(tool_calls=(ToolCall(
                "book-1", "create_shipment",
                {"option_id": "standard", "billable_weight_kg": 4.8,
                 "destination_zone": "domestic", "request_id": "request-1"},
            ),))
        outcome = json.loads(messages[-1].content)
        if outcome["ok"]:
            return ModelResponse(text=f"Created {outcome['result']['shipment_id']}.")
        return ModelResponse(text="No shipment was created.")


class BookingAgentTests(unittest.TestCase):
    def test_booking_requires_approval_and_uses_authenticated_mcp(self) -> None:
        async def check(approved: bool) -> None:
            from examples.shipping.shipments import ShipmentStore

            read_token = secrets.token_urlsafe(24)
            write_token = secrets.token_urlsafe(24)
            store = ShipmentStore()
            app = build_app(read_token, write_token=write_token, store=store)
            approvals = []
            trace = []

            async def approve(name: str, arguments: dict) -> bool:
                approvals.append((name, arguments))
                return approved

            async with app.router.lifespan_context(app):
                async with connect_mcp(
                    "http://127.0.0.1:8000/mcp", write_token,
                    transport=httpx2.ASGITransport(app=app),
                ) as client:
                    result = await run_shipping(
                        "Book a 40 x 30 x 20 cm, 3 kg domestic parcel for €12 within 3 days",
                        BookingFakeModel(), client, booking=True, approve=approve,
                        trace=trace.append,
                    )
            self.assertEqual(len(approvals), 1)
            self.assertEqual(approvals[0][0], "create_shipment")
            self.assertEqual(len(store.shipments), int(approved))
            self.assertEqual(result.tool_events[-1].status, "ok" if approved else "blocked")
            self.assertIn("[approval] Review requested for create_shipment", trace)
            self.assertEqual("[MCP client] Calling create_shipment" in trace, approved)
            self.assertEqual(
                result.answer,
                "Created SHIP-0001." if approved else "No shipment was created.",
            )

        asyncio.run(check(False))
        asyncio.run(check(True))
