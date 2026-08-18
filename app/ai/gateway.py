"""
AI Gateway module providing enhancement wrappers for trip generation payloads.
"""
from __future__ import annotations

import os
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class AIEnhancementResult:
    def __init__(self, data: Dict[str, Any] | None = None, available: bool = False, error: str | None = None):
        self.data = data or {}
        self.available = available
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return self.data


class AIGateway:
    def __init__(self):
        # Checks if AI service environment key is present
        self.enabled = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("GEMINI_API_KEY"))

    def is_available(self) -> bool:
        return self.enabled

    def enhance_trip(self, trip_dict: Dict[str, Any]) -> AIEnhancementResult:
        if not self.enabled:
            return AIEnhancementResult(
                data={},
                available=False,
                error="AI Gateway disabled: missing API credentials"
            )

        try:
            # Operational AI enhancement logic goes here
            enhancements = {
                "summary": f"Enhanced experience planned for {trip_dict.get('title', 'Your Safari')}.",
                "highlights": ["Customized daily schedules", "Optimized route transfers"]
            }
            return AIEnhancementResult(data=enhancements, available=True)
        except Exception as exc:
            logger.exception("AI enhancement failed: %s", str(exc))
            return AIEnhancementResult(data={}, available=False, error=str(exc))


_ai_gateway_instance = AIGateway()


def get_ai_gateway() -> AIGateway:
    return _ai_gateway_instance
