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


def call_engine(engine_name: str, func: Callable[[], T], fallback: Any = None) -> EngineResult[T]:
    """
    Executes an engine call inside a try/except block.
    Returns default fallback if execution fails.
    """
    try:
        result = func()
        return EngineResult(value=result, degraded=False)
    except Exception as exc:
        logger.exception("Engine execution failed for %s: %s", engine_name, str(exc))
        return EngineResult(value=fallback, degraded=True, error=f"{engine_name}: {str(exc)}")
