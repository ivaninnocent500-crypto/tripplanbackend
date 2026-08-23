"""
Simple shared-secret auth: verifies the X-Api-Key header against
ATI_API_KEY from the environment (see .env.example).

This is intentionally minimal — a single shared key for the Android app,
not per-user auth. If per-user auth (Supabase JWT) is needed later, this
is the one place to swap it out; every customer-facing route depends on
`require_api_key` rather than checking the header itself, so the change
is contained here.

NOTE: this is a DIFFERENT secret from require_ops_api_key in
app/api/ops_auth.py (ATI_OPS_API_KEY) — that one guards the internal
quote-recording endpoint and must never share a value with this one.
"""
from __future__ import annotations

import os
import secrets

from fastapi import Header, HTTPException, status


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-Api-Key")) -> None:
    expected = os.environ.get("ATI_API_KEY")

    if not expected:
        # Fail closed: an unset ATI_API_KEY on the server is a
        # deployment/config error, not "no auth required". Silently
        # allowing all requests through because the env var is missing
        # would be a much worse failure mode than a loud 500.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: ATI_API_KEY is not set.",
        )

    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-Api-Key header.",
        )

