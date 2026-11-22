from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


@asynccontextmanager
async def connect_mcp(
    url: str,
    token: str,
    *,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> AsyncIterator[Client]:
    if not token:
        raise ValueError("MCP token must not be empty")
    async with httpx2.AsyncClient(
        headers={"Authorization": f"Bearer {token}"}, transport=transport
    ) as http_client:
        async with Client(streamable_http_client(url, http_client=http_client)) as client:
            yield client
