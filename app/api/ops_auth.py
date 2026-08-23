"""
require_ops_api_key — a SECOND, separate shared secret from the
customer-facing X-Api-Key (require_api_key in app/api/auth.py).

Why separate: the record-quote endpoint (trip_v2_ops_and_docs_routes.py)
lets its caller set an arbitrary price on someone else's trip and
trigger a customer-facing "your quote is ready" email. That must never
be reachable with the same key that ships inside the Android app's
BuildConfig — if the customer-facing key leaked (decompiled APK, log
capture, whatever), an attacker could not use it to inject fake quotes.

Set ATI_OPS_API_KEY in Render's environment (distinct from ATI_API_KEY)
and give it only to your ops tooling / admin dashboard / email-parsing
webhook — never to the mobile app.
"""
from __future__ import annotations

import os
import secrets

from fastapi import Header, HTTPException, status


def require_ops_api_key(x_ops_api_key: str | None = Header(default=None, alias="X-Ops-Api-Key")) -> None:
    expected = os.environ.get("ATI_OPS_API_KEY")

    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: ATI_OPS_API_KEY is not set.",
        )

    if not x_ops_api_key or not secrets.compare_digest(x_ops_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-Ops-Api-Key header.",
        )

