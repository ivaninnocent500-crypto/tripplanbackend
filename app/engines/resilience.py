"""
Resilience wrapper to handle engine call failures gracefully.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar, Generic

logger = logging.getLogger(__name__)

T = TypeVar("T")

class EngineResult(Generic[T]):
    def __init__(self, value: T, degraded: bool = False, error: str | None = None):
        self.value = value
        self.degraded = degraded
        self.error = error


def call_engine(engine_name: str, func: Callable[[], T], fallback: Any = None, db: Any = None) -> EngineResult[T]:
    """
    Executes an engine call inside a try/except block.
    Returns default fallback if execution fails.

    db: optional SQLAlchemy session. When provided, a failed call rolls
    it back before returning. Without this, a caught exception here
    (e.g. a unique-constraint violation from a retried request) leaves
    the session's transaction in a Postgres-aborted state — every
    subsequent query on that same session then fails too, turning one
    soft "degraded" failure into a hard 500 on whatever runs next in
    the same request (a db.commit() call, another engine, etc).
    """
    try:
        result = func()
        return EngineResult(value=result, degraded=False)
    except Exception as exc:
        logger.exception("Engine execution failed for %s: %s", engine_name, str(exc))
        if db is not None:
            try:
                db.rollback()
            except Exception:
                logger.exception("Failed to roll back session after %s error", engine_name)
        return EngineResult(value=fallback, degraded=True, error=f"{engine_name}: {str(exc)}")

