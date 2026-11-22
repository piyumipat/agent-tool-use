import hmac
from collections.abc import Mapping, Sequence

from pydantic import AnyHttpUrl
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError


class StaticTokenVerifier(TokenVerifier):
    def __init__(self, tokens: Mapping[str, Sequence[str]], resource_url: str) -> None:
        if not tokens or any(not token for token in tokens):
            raise ValueError("MCP tokens must not be empty")
        self._tokens = dict(tokens)
        self._resource_url = resource_url

    async def verify_token(self, token: str) -> AccessToken | None:
        for expected, scopes in self._tokens.items():
            if hmac.compare_digest(token, expected):
                return AccessToken(
                    token=token,
                    client_id="local-demo-client",
                    scopes=list(scopes),
                    resource=self._resource_url,
                    subject="local-demo-user",
                )
        return None


def create_authenticated_server(
    name: str,
    *,
    tokens: Mapping[str, Sequence[str]],
    resource_url: str,
    issuer_url: str,
    required_scope: str,
) -> MCPServer:
    return MCPServer(
        name,
        token_verifier=StaticTokenVerifier(tokens, resource_url),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(issuer_url),
            resource_server_url=AnyHttpUrl(resource_url),
            required_scopes=[required_scope],
            validate_token_resource=True,
        ),
    )


def require_scope(scope: str) -> None:
    access_token = get_access_token()
    if access_token is None or scope not in access_token.scopes:
        raise ToolError(f"MCP caller lacks {scope} permission")
