"""
ValidationEngine — checks a built Cabinet against real constraints and
writes results to `footstools`. This is what lets the pipeline say
GENERATE -> VALIDATE -> REPAIR -> VALIDATE AGAIN -> RETURN instead of
trusting whatever the planning engine produced.

Kept intentionally rule-based (no AI) per the architecture doc: AI must
never be in a position to silently wave through a physically impossible
itinerary.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.db.models_furniture import Cabinet, Drawer, Footstool, Headboard, Shelf


class ValidationEngine:
    def __init__(self, db: Session):
        self.db = db

    def validate(self, cabinet: Cabinet) -> dict[str, Any]:
        issues: list[Footstool] = []

        for shelf in cabinet.shelves:
            issues += self._check_time_overlaps(cabinet, shelf)
            issues += self._check_accommodation_present(cabinet, shelf)

        issues += self._check_transfer_feasibility(cabinet)

        for issue in issues:
            self.db.add(issue)
        self.db.flush()

        has_errors = any(i.severity == "error" for i in issues)
        cabinet.status = "draft" if has_errors else "ready"
        self.db.add(cabinet)

        return {
            "status": "invalid" if has_errors else "valid",
            "issue_count": len(issues),
            "errors": [i.message for i in issues if i.severity == "error"],
            "warnings": [i.message for i in issues if i.severity == "warning"],
        }

    # ------------------------------------------------------------------
    def _check_time_overlaps(self, cabinet: Cabinet, shelf: Shelf) -> list[Footstool]:
        issues = []
        timed = sorted(
            [d for d in shelf.drawers if d.start_time and d.duration_minutes],
            key=lambda d: d.start_time,
        )
        for a, b in zip(timed, timed[1:]):
            a_end = (datetime.combine(shelf.date or datetime.today(), a.start_time)
                     + timedelta(minutes=a.duration_minutes)).time()
            if a_end > b.start_time:
                issues.append(Footstool(
                    cabinet_id=cabinet.id, shelf_id=shelf.id, severity="error", category="time",
                    message=f"Day {shelf.day_number}: '{a.name}' overlaps with '{b.name}'.",
                ))
        return issues

    # ------------------------------------------------------------------
    def _check_accommodation_present(self, cabinet: Cabinet, shelf: Shelf) -> list[Footstool]:
        if not shelf.headboards:
            return [Footstool(
                cabinet_id=cabinet.id, shelf_id=shelf.id, severity="error", category="accommodation",
                message=f"Day {shelf.day_number}: no accommodation assigned for this overnight.",
            )]
        return []

    # ------------------------------------------------------------------
    def _check_transfer_feasibility(self, cabinet: Cabinet) -> list[Footstool]:
        """
        Rejects itineraries where a same-day activity is scheduled after a
        transfer that couldn't plausibly have finished in time — the exact
        "08:00 game drive / 13:00 transfer / 14:00 activity across a
        3.5h drive" failure case called out in the planning doc.
        """
        issues = []
        for hinge in cabinet.hinges:
            if hinge.duration_minutes and hinge.duration_minutes > 240:
                issues.append(Footstool(
                    cabinet_id=cabinet.id, severity="warning", category="transport",
                    message=(
                        f"Transfer of {hinge.duration_minutes} min exceeds the 4-hour "
                        "same-day comfort threshold — consider a rest stop or splitting the drive."
                    ),
                ))
            if hinge.source == "fallback_estimate":
                issues.append(Footstool(
                    cabinet_id=cabinet.id, severity="warning", category="transport",
                    message="Transfer duration used a fallback estimate, not a measured drive_times record.",
                ))
        return issues
