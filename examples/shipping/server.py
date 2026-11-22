import logging
import os

import uvicorn
from dotenv import load_dotenv
from mcp.server.mcpserver.exceptions import ToolError

from agent_tool_use.mcp.server import create_authenticated_server
from agent_tool_use.mcp.server import require_scope
from examples.shipping.shipments import ShipmentStore
from examples.shipping.tools import get_shipping_options


def build_server(
    read_token: str,
    *,
    write_token: str | None = None,
    store: ShipmentStore | None = None,
    port: int = 8000,
):
    tokens = {read_token: ["shipping:read"]}
    if write_token is not None:
        if write_token == read_token:
            raise ValueError("Read and write MCP tokens must differ")
        tokens[write_token] = ["shipping:read", "shipping:write"]
    server = create_authenticated_server(
        "shipping-options",
        tokens=tokens,
        resource_url=f"http://127.0.0.1:{port}/mcp",
        issuer_url="https://auth.example.com",
        required_scope="shipping:read",
    )
    def shipping_options(
        billable_weight_kg: float, destination_zone: str
    ) -> list[dict[str, str | float | int]]:
        options = get_shipping_options(billable_weight_kg, destination_zone)
        summary = ", ".join(
            f"{option['option_id']} (€{option['price_eur']:g}, "
            f"{option['delivery_days']} day{'s' if option['delivery_days'] != 1 else ''})"
            for option in options
        ) or "none"
        print(f"[MCP server] Shipping options: {summary}", flush=True)
        return options

    server.tool(
        name="get_shipping_options",
        description="List fictional domestic shipping options for a parcel by billable weight.",
    )(shipping_options)
    shipment_store = store if store is not None else ShipmentStore()

    def create_shipment(
        option_id: str,
        billable_weight_kg: float,
        destination_zone: str,
        request_id: str,
    ) -> dict[str, str | float | int]:
        require_scope("shipping:write")
        try:
            result = shipment_store.create(option_id, billable_weight_kg, destination_zone, request_id)
        except ValueError as error:
            raise ToolError(str(error)) from error
        print(f"[MCP server] create_shipment returned {result['shipment_id']}", flush=True)
        return result

    server.tool(
        name="create_shipment",
        description="Create one fictional shipment for a valid option using a unique request ID.",
        structured_output=True,
    )(create_shipment)
    return server


def build_app(
    read_token: str,
    *,
    write_token: str | None = None,
    store: ShipmentStore | None = None,
    port: int = 8000,
):
    return build_server(
        read_token, write_token=write_token, store=store, port=port
    ).streamable_http_app()


def main() -> None:
    load_dotenv()
    read_token = os.environ.get("MCP_READ_TOKEN")
    write_token = os.environ.get("MCP_WRITE_TOKEN")
    if not read_token or not write_token:
        raise SystemExit("Set MCP_READ_TOKEN and MCP_WRITE_TOKEN in .env before starting the server")
    port = int(os.environ.get("MCP_PORT", "8000"))
    logging.getLogger("mcp").setLevel(logging.WARNING)
    uvicorn.run(
        build_app(read_token, write_token=write_token, port=port),
        host="127.0.0.1", port=port, access_log=False, log_level="warning",
    )


if __name__ == "__main__":
    main()
