"""
Health check — split out of the old app/api/trip.py since that file no
longer exists in the new architecture. Behavior is identical to before:
unauthenticated (Render's own health checks need to hit it without a key),
reports connection status only, never leaks credentials.
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter

from app.api.schemas_v2 import HealthResponse
from app.db.session import check_legacy_connection, check_supabase_connection

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    supabase_ok = False
    legacy_ok = False

    try:
        supabase_ok = check_supabase_connection()
        if not supabase_ok:
            logger.error("❌ Health Check: check_supabase_connection() returned False.")
    except Exception as exc:
        logger.exception("❌ Health Check - Supabase Connection Exception: %s", exc)

    try:
        legacy_ok = check_legacy_connection()
    except Exception as exc:
        logger.info("Legacy DB not configured or unreachable (non-fatal in new architecture): %s", exc)

    ai_enabled = os.environ.get("ATI_AI_ENABLED", "false").lower() == "true"

    return HealthResponse(
        status="ok" if supabase_ok else "degraded",
        supabase_connected=supabase_ok,
        legacy_db_connected=legacy_ok,
        ai_gateway_enabled=ai_enabled,
    )
