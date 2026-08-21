"""
Two independent SQLAlchemy engines/sessions.

    get_supabase_db() -> the Travel Intelligence knowledge base AND the
                           new trip-instance layer (travel_places,
                           wildlife, lodges, cabinets, shelves, etc. —
                           all in the same Supabase Postgres project).
    get_legacy_db() -> kept for backward compatibility with any
                           remaining legacy-DB consumers. Not required
                           by the v2 trip lifecycle (app/api/trip_v2.py
                           does not use it) — app/api/health.py treats
                           its failure as non-fatal for that reason.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

logger = logging.getLogger(__name__)


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when a required *_DATABASE_URL env var is missing at request time."""


_supabase_engine: Engine | None = None
_legacy_engine: Engine | None = None
_SupabaseSession: sessionmaker | None = None
_LegacySession: sessionmaker | None = None


def _build_supabase_engine() -> Engine:
    url = os.environ.get("SUPABASE_DATABASE_URL")
    if not url:
        logger.error("❌ SUPABASE_DATABASE_URL environment variable is missing.")
        raise DatabaseNotConfiguredError("SUPABASE_DATABASE_URL is not set.")

    url = url.strip("'\" ")

    is_pooled = ":6543" in url
    pool_class = NullPool if is_pooled else QueuePool

    kwargs: dict = {"pool_pre_ping": True}
    if pool_class is QueuePool:
        kwargs.update(pool_size=5, max_overflow=10, pool_recycle=1800)

    if is_pooled:
        # Supabase's pooler (Supavisor, transaction mode — the :6543 URL)
        # hands each transaction to whichever backend Postgres connection
        # is free, not necessarily the same one each time. psycopg3
        # automatically prepares repeated statements server-side under
        # auto-generated names like "_pg3_0" — if two unrelated requests
        # land on the same backend connection, the second prepare
        # collides with one already registered by the first, raising
        # psycopg.errors.DuplicatePreparedStatement. Disabling
        # server-side prepare for pooled connections avoids this
        # entirely; it costs a small amount of query-planning overhead
        # per call, which is the right tradeoff against random 500s.
        kwargs["connect_args"] = {"prepare_threshold": None}

    try:
        return create_engine(url, poolclass=pool_class, **kwargs)
    except Exception as exc:
        logger.error("❌ Failed to create Supabase engine: %s", exc, exc_info=True)
        raise


def _build_legacy_engine() -> Engine:
    url = os.environ.get("DATABASE_URL") or os.environ.get("LEGACY_DATABASE_URL")
    if not url:
        logger.error("❌ DATABASE_URL / LEGACY_DATABASE_URL environment variable is missing.")
        raise DatabaseNotConfiguredError("DATABASE_URL is not set.")

    url = url.strip("'\" ")

    try:
        return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10, pool_recycle=1800)
    except Exception as exc:
        logger.error("❌ Failed to create Legacy engine: %s", exc, exc_info=True)
        raise


def _get_supabase_sessionmaker() -> sessionmaker:
    global _supabase_engine, _SupabaseSession
    if _SupabaseSession is None:
        _supabase_engine = _build_supabase_engine()
        _SupabaseSession = sessionmaker(bind=_supabase_engine, autoflush=False, autocommit=False)
    return _SupabaseSession


def _get_legacy_sessionmaker() -> sessionmaker:
    global _legacy_engine, _LegacySession
    if _LegacySession is None:
        _legacy_engine = _build_legacy_engine()
        _LegacySession = sessionmaker(bind=_legacy_engine, autoflush=False, autocommit=False)
    return _LegacySession


def get_supabase_db() -> Iterator[Session]:
    """FastAPI dependency: yields a Supabase session."""
    SessionLocal = _get_supabase_sessionmaker()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_legacy_db() -> Iterator[Session]:
    """FastAPI dependency: yields a legacy DB session."""
    SessionLocal = _get_legacy_sessionmaker()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def supabase_session() -> Iterator[Session]:
    """Context manager for health checks and standalone scripts."""
    SessionLocal = _get_supabase_sessionmaker()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def legacy_session() -> Iterator[Session]:
    """Context manager for health checks and standalone scripts."""
    SessionLocal = _get_legacy_sessionmaker()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_supabase_connection() -> bool:
    try:
        from sqlalchemy import text
        with supabase_session() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("❌ Supabase connection failed: %s", exc, exc_info=True)
        return False


def check_legacy_connection() -> bool:
    try:
        from sqlalchemy import text
        with legacy_session() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("❌ Legacy DB connection failed: %s", exc, exc_info=True)
        return False

