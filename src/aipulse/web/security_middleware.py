"""Bearer-token verification middleware for AIPulse API endpoints.

Spec §9.3 (Q130.B) — all AIPulse API routes use ``Authorization: Bearer <token>``
where the token matches ``settings.aipulse_api_token``. If the token is unset,
verification is skipped (developer-friendly default).
"""

from __future__ import annotations

from fastapi import Request

from aipulse.core.config import get_settings


_BEARER_PREFIX = "Bearer "


def verify_auth_header(request: Request) -> bool:
    """Return True if the request passes Bearer-token verification.

    Behaviour:
        - ``aipulse_api_token`` is empty → always True (no auth configured).
        - Header missing, malformed, or wrong scheme → False.
        - ``Authorization: Bearer <token>`` where token matches → True.
    """
    settings = get_settings()
    token = settings.aipulse_api_token.get_secret_value()
    if not token:
        # No token configured, dev mode is bypassed.
        return True

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith(_BEARER_PREFIX):
        return False

    presented = auth_header[len(_BEARER_PREFIX):]
    return presented == token
