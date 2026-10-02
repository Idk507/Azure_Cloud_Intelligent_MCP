from __future__ import annotations

import asyncio
from typing import Any

import jwt
from mcp.server.auth.provider import AccessToken

from .config import Settings


class EntraTokenVerifier:
    """Validate Entra access tokens issued for this MCP resource server."""

    def __init__(self, settings: Settings):
        self._settings = settings

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
            tenant_id = claims.get("tid")
            if not tenant_id or tenant_id not in self._settings.entra_allowed_tenant_ids:
                return None
            jwks_url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
            signing_key = await asyncio.to_thread(jwt.PyJWKClient(jwks_url).get_signing_key_from_jwt, token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=[self._settings.entra_api_client_id, f"api://{self._settings.entra_api_client_id}"],
                issuer=f"https://login.microsoftonline.com/{tenant_id}/v2.0",
            )
            scopes = claims.get("scp", "").split()
            if "access_as_user" not in scopes:
                return None
            return AccessToken(token=token, client_id=claims.get("azp") or claims.get("appid") or "", scopes=scopes, expires_at=claims.get("exp"), subject=claims.get("sub"), claims={"tid": tenant_id, "oid": claims.get("oid"), "iss": claims.get("iss")})
        except Exception:
            return None
