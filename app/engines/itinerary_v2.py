"""
ItineraryPlanningEngine — complete, self-contained replacement for
app/engines/itinerary_v2.py.

Fixes the exact bug you're seeing in production: the SAME activities
repeating verbatim across non-adjacent days ("Great Migration River
Crossing Viewing" / "Classic Game Drive" on Day 2, 3, 5, 6). Root cause
was the OLD query re-running independently per day with
`order by case when category='game_drive' then 0 else 1 end, random()`
— the case-priority clause deterministically put the same 1-2
game_drive rows on top every time, and random() only shuffled the tie
within that group, so with few activities seeded you got identical
output day after day.

What changed:
  1. Activity pool is fetched ONCE per destination stay (not once per
     day), ranked by travel_style + destination_type — no hardcoded
     game_drive bias.
  2. A cursor advances across nights so the SAME activity can never be
     picked twice within one stay at one destination.
  3. random() is replaced by a deterministic hash-seeded order
     (cabinet_id + activity id) — reproducible on retry, still
     effectively "shuffled" the first time.
  4. When the pool runs out (a real risk with small seeded datasets —
     see the destination's activities row count before assuming this
     won't happen), the fallback text CYCLES through several
     destination-type-appropriate variants and is tagged
     source='fallback_estimate' so ValidationEngine can flag it and the
     UI never mistakes it for a distinct booked activity. It never
     silently repeats the exact same fallback sentence day after day if
     it can help it.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta, time as dt_time
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models_furniture import (
    Armrest, Cabinet, Drawer, Headboard, Hinge, Shelf, Tray,
)

logger = logging.getLogger(__name__)

DEFAULT_GAME_DRIVE_START = dt_time(6, 0)
DEFAULT_ARRIVAL_TIME = dt_time(14, 0)

# ---------------------------------------------------------------------
# Data-driven rank maps — every literal here is a real activity_category
# enum value from the DDL. No invented categories.
# ---------------------------------------------------------------------
DESTINATION_TYPE_CATEGORY_RANKS: dict[str, list[str]] = {
    "national_park": ["game_drive", "walking_safari", "birding", "night_drive", "photography"],
    "game_reserve": ["game_drive", "walking_safari", "birding", "night_drive", "horseback_safari"],
    "island": ["beach_leisure", "diving", "snorkeling", "boat_safari", "fishing"],
    "beach": ["beach_leisure", "diving", "snorkeling", "boat_safari", "fishing"],
    "marine_park": ["diving", "snorkeling", "boat_safari", "fishing"],
    "mountain": ["mountain_climbing", "hiking"],
    "desert": ["hiking", "camping", "photography"],
    "city": ["cultural_visit", "shopping", "photography"],
    "cultural_site": ["cultural_visit", "photography"],
    "unesco_site": ["cultural_visit", "photography"],
    "lake": ["boat_safari", "canoeing", "fishing", "birding"],
    "waterfall": ["hiking", "photography"],
    "forest_reserve": ["walking_safari", "birding", "hiking"],
    "wetland": ["birding", "boat_safari", "canoeing"],
}

TRAVEL_STYLE_CATEGORY_RANKS: dict[str, list[str]] = {
    "wildlife": ["game_drive", "walking_safari", "birding", "night_drive"],
    "adventure": ["hiking", "mountain_climbing", "diving", "cycling"],
    "beach": ["beach_leisure", "diving", "snorkeling", "boat_safari"],
    "cultural": ["cultural_visit", "shopping", "photography"],
    "photography": ["photography", "birding"],
    "birding": ["birding"],
    "luxury": ["spa_wellness", "photography"],
    "relaxed_pace": ["beach_leisure", "spa_wellness", "boat_safari"],
}

# Multiple honest fallback variants per destination_type, so a run of
# fallback days (pool exhausted) doesn't read as the same sentence
# copy-pasted repeatedly. Cycled in order, wrapping if more days need
# fallbacks than variants exist.
FALLBACK_VARIANTS: dict[str, list[tuple[str, str]]] = {
    "island": [
        ("Beach & relaxation", "Free time at the lodge's beach area — no specific excursion booked; the operator will offer whatever suits sea conditions."),
        ("Snorkel gear & shoreline time", "Open beach time with snorkel gear available at the lodge — no guided excursion booked for this slot."),
    ],
    "beach": [
        ("Beach & relaxation", "Free time at the lodge's beach area — no specific excursion booked; the operator will offer whatever suits sea conditions."),
        ("Sunset shoreline walk", "Unstructured time along the beach — no guided activity booked for this slot."),
    ],
    "mountain": [
        ("Acclimatisation walk", "Short lower-altitude walk to acclimatise — no summit attempt scheduled today."),
        ("Rest & recovery time", "Open time at camp to rest — no scheduled activity for this slot."),
    ],
    "desert": [
        ("Desert nature walk", "Light guided walk on sand or boardwalk surfaces suited to the terrain — no specific site booked."),
        ("Open camp time", "Unstructured time at camp — no specific excursion booked for this slot."),
    ],
    "marine_park": [
        ("Shore time at the lodge", "Open time at the lodge — operator will offer optional water-based excursions if conditions allow."),
    ],
    "city": [
        ("Guided cultural stop", "Short guided visit to a locally significant site — no specific venue booked in advance."),
        ("Free time to explore", "Unstructured time to explore independently — no guided activity booked for this slot."),
    ],
    "cultural_site": [
        ("Guided cultural stop", "Short guided visit to a locally significant site — no specific venue booked in advance."),
    ],
    "unesco_site": [
        ("Guided cultural stop", "Short guided visit to a locally significant site — no specific venue booked in advance."),
    ],
    "national_park": [
        ("Guided wilderness drive", "Game drive on lodge circuits — no specific route booked in advance. Times may shift with conditions."),
        ("Extended photographic drive", "A slower-paced drive focused on photography opportunities — no specific route booked in advance."),
        ("Bush walk near camp", "Short guided walk near the lodge grounds, conditions permitting — no specific route booked in advance."),
    ],
    "game_reserve": [
        ("Guided wilderness drive", "Game drive on lodge circuits — no specific route booked in advance. Times may shift with conditions."),
        ("Extended photographic drive", "A slower-paced drive focused on photography opportunities — no specific route booked in advance."),
    ],
}
_DEFAULT_FALLBACK = [("Time at the lodge", "Open time at the lodge — operator will offer what suits the day's conditions.")]


def _default_start_for(category: str | None) -> dt_time:
    if category in ("game_drive", "walking_safari", "hiking", "mountain_climbing"):
        return DEFAULT_GAME_DRIVE_START
    if category in ("diving", "snorkeling", "boat_safari"):
        return dt_time(9, 0)
    if category in ("cultural_visit", "shopping"):
        return dt_time(10, 0)
    if category == "spa_wellness":
        return dt_time(11, 0)
    return dt_time(10, 0)


def _fallback_drawer_text(destination_type: str | None, variant_index: int) -> tuple[str, str]:
    variants = FALLBACK_VARIANTS.get(destination_type or "", _DEFAULT_FALLBACK) or _DEFAULT_FALLBACK
    return variants[variant_index % len(variants)]


def _merged_ranked_categories(destination_type: str | None, travel_style: list[str]) -> list[str]:
    """Travel-style preferences rank first, destination-type defaults backfill. No hardcoded game_drive bias anywhere."""
    seen: set[str] = set()
    out: list[str] = []
    for style in travel_style:
        for cat in TRAVEL_STYLE_CATEGORY_RANKS.get(style, []):
            if cat not in seen:
                out.append(cat)
                seen.add(cat)
    if destination_type:
        for cat in DESTINATION_TYPE_CATEGORY_RANKS.get(destination_type, []):
            if cat not in seen:
                out.append(cat)
                seen.add(cat)
    return out


@dataclass
class BuildResult:
    cabinet: Cabinet
    warnings: list[str] = field(default_factory=list)


class ItineraryPlanningEngine:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    def build(self, request: dict[str, Any], destination_ids: list[str]) -> BuildResult:
        days: int = request["days"]
        travelers = request.get("travelers", 1)
        travel_style: list[str] = request.get("travel_style", []) or self._infer_style(request)
        budget_tier = request.get("budget_tier", "mid")
        start_date_raw = request.get("start_date")
        start_date = date.fromisoformat(start_date_raw) if start_date_raw else None

        cabinet = Cabinet(
            request_json=request,
            title=request.get("title") or self._default_title(request),
            duration_days=days,
            travelers_adults=travelers,
            travel_style=travel_style,
            budget_tier=budget_tier,
            status="draft",
            start_date=start_date,
            end_date=(start_date + timedelta(days=days - 1)) if start_date else None,
            primary_destination_id=destination_ids[0] if destination_ids else None,
            route_destination_ids=destination_ids,
        )
        self.db.add(cabinet)
        self.db.flush()

        warnings: list[str] = []

        legs = self._build_hinges(cabinet.id, destination_ids)
        relaxed = "relaxed_pace" in travel_style
        allocation = self._allocate_days(destination_ids, days, relaxed)
        destination_types = self._resolve_destination_types(destination_ids)

        # Pool fetched ONCE per destination — this is the actual fix.
        # Cursor + fallback_variant_index both advance across nights so
        # nothing repeats within a stay unless the pool is truly
        # exhausted, and even then the fallback text cycles.
        per_destination_pool: dict[str, list[dict[str, Any]]] = {}
        for dest_id in destination_ids:
            per_destination_pool[dest_id] = self._fetch_ranked_activity_pool(
                dest_id=dest_id,
                destination_type=destination_types.get(dest_id),
                travel_style=travel_style,
                start_date=start_date,
                cabinet_id=str(cabinet.id),
            )
            if len(per_destination_pool[dest_id]) < 4:
                logger.warning(
                    "Destination %s has only %d activities seeded — a multi-day "
                    "stay here will exhaust the pool and fall back to honest "
                    "placeholder activities. Seed more activities to fix this "
                    "at the data layer, not just the engine layer.",
                    dest_id, len(per_destination_pool[dest_id]),
                )
                warnings.append(
                    f"Destination {dest_id} has very few seeded activities — "
                    "some days on this trip may use generic placeholder activities."
                )

        cursors: dict[str, int] = {d: 0 for d in destination_ids}
        fallback_counters: dict[str, int] = {d: 0 for d in destination_ids}

        day_number = 1
        current_date = start_date
        for idx, dest_id in enumerate(destination_ids):
            nights_here = allocation[idx]
            dest_type = destination_types.get(dest_id)
            for night_idx in range(nights_here):
                is_first_day_overall = day_number == 1
                is_arrival_day = night_idx == 0 and idx > 0
                is_last_day_overall = day_number == days
                month = current_date.strftime("%B").lower() if current_date else None

                shelf = Shelf(
                    cabinet_id=cabinet.id,
                    day_number=day_number,
                    date=current_date,
                    destination_id=dest_id,
                    theme=self._theme_for(idx, night_idx, is_first_day_overall, is_last_day_overall),
                )
                self.db.add(shelf)
                self.db.flush()

                self._populate_drawers(
                    shelf=shelf,
                    pool=per_destination_pool[dest_id],
                    cursor=cursors,
                    fallback_counters=fallback_counters,
                    dest_id=dest_id,
                    dest_type=dest_type,
                    travel_style=travel_style,
                    day_number=day_number,
                    is_first_day=is_first_day_overall,
                    is_last_day=is_last_day_overall,
                )
                self._populate_headboard(shelf, dest_id, budget_tier, nights_here - night_idx)
                self._populate_armrest(shelf, dest_id, legs, idx, is_arrival_day)
                self._populate_trays(shelf, is_first_day_overall)

                day_number += 1
                if current_date:
                    current_date += timedelta(days=1)

        self.db.flush()
        return BuildResult(cabinet=cabinet, warnings=warnings)

    # ------------------------------------------------------------------
    def _fetch_ranked_activity_pool(
        self, dest_id: str, destination_type: str | None, travel_style: list[str],
        start_date: date | None, cabinet_id: str,
    ) -> list[dict[str, Any]]:
        ranked_categories = _merged_ranked_categories(destination_type, travel_style)
        ranked_array_sql = "{" + ",".join(ranked_categories) + "}" if ranked_categories else "{}"
        month_token = start_date.strftime("%B").lower() if start_date else None

        sql = text("""
            with ranked as (
              select
                a.id, a.name, a.description, a.category, a.difficulty,
                a.available_months,
                case
                  when cardinality(:ranked) = 0 then 999
                  else array_position(:ranked, a.category::text)
                end as style_position,
                case
                  when :month::month_enum is null then 0
                  when a.available_months is null then 0
                  when :month::month_enum = any(a.available_months) then 0
                  else 1
                end as month_mismatch,
                hashtext(:cab_id || '|' || a.id::text) as seed_hash
              from activities a
              where a.destination_id = :dest_id
            )
            select id, name, description, category, difficulty,
                   style_position, month_mismatch, seed_hash
            from ranked
            order by style_position asc, month_mismatch asc, seed_hash asc
        """)
        rows = self.db.execute(sql, {
            "ranked": ranked_array_sql, "dest_id": dest_id,
            "month": month_token, "cab_id": cabinet_id,
        }).fetchall()

        return [
            {"id": r[0], "name": r[1], "description": r[2], "category": r[3], "difficulty": r[4]}
            for r in rows
        ]

    # ------------------------------------------------------------------
    def _populate_drawers(
        self, shelf, pool: list[dict[str, Any]], cursor: dict[str, int], fallback_counters: dict[str, int],
        dest_id: str, dest_type: str | None, travel_style: list[str],
        day_number: int, is_first_day: bool, is_last_day: bool,
    ) -> None:
        order = 1

        if is_first_day:
            self._add_drawer(shelf, "Airport welcome", "Met at the airport by your driver-guide.",
                              DEFAULT_ARRIVAL_TIME, 60, order, "ARRIVAL", source="hardcoded_arrival_departure"); order += 1
            self._add_drawer(shelf, "Transfer to lodge", "Slow, scenic drive — no activities scheduled today.",
                              dt_time(15, 30), 60, order, "TRANSFER", source="hardcoded_arrival_departure"); order += 1
            self._add_drawer(shelf, "Dinner at the lodge", "Garden setting, early night before the parks.",
                              dt_time(19, 30), 90, order, "MEAL", source="hardcoded_arrival_departure")
            return

        if is_last_day:
            self._add_drawer(shelf, "Breakfast", None, dt_time(7, 0), 45, order, "MEAL", source="hardcoded_arrival_departure"); order += 1
            self._add_drawer(shelf, "Transfer to airport", None, dt_time(9, 0), 120, order, "TRANSFER", source="hardcoded_arrival_departure"); order += 1
            self._add_drawer(shelf, "Departure", None, dt_time(12, 0), 30, order, "DEPARTURE", source="hardcoded_arrival_departure")
            return

        # --- Standard park/reserve day — pool cursor advances, never repeats ---
        c = cursor[dest_id]
        if c < len(pool):
            morning = pool[c]
            cursor[dest_id] += 1
            self._add_drawer(shelf, morning["name"], morning["description"],
                              _default_start_for(morning["category"]), 240, order, "EXPERIENCE",
                              activity_id=morning["id"], source="activities_table")
        else:
            title, desc = _fallback_drawer_text(dest_type, fallback_counters[dest_id])
            fallback_counters[dest_id] += 1
            self._add_drawer(shelf, title, desc, _default_start_for(None), 180, order,
                              "EXPERIENCE", source="fallback_estimate")
            logger.warning("Day %s at %s: activity pool exhausted (morning slot) — using fallback", day_number, dest_id)
        order += 1

        self._add_drawer(shelf, "Lunch at the lodge", None, dt_time(13, 0), 60, order, "MEAL", source="hardcoded_lunch")
        order += 1

        c = cursor[dest_id]
        if c < len(pool):
            afternoon = pool[c]
            cursor[dest_id] += 1
            self._add_drawer(shelf, afternoon["name"], afternoon["description"],
                              dt_time(16, 0), 150, order, "EXPERIENCE",
                              activity_id=afternoon["id"], source="activities_table")
        else:
            title, desc = _fallback_drawer_text(dest_type, fallback_counters[dest_id])
            fallback_counters[dest_id] += 1
            self._add_drawer(shelf, title, desc, dt_time(16, 0), 150, order,
                              "EXPERIENCE", source="fallback_estimate")
            logger.warning("Day %s at %s: activity pool exhausted (afternoon slot) — using fallback", day_number, dest_id)
        order += 1

        if "relaxed_pace" in travel_style:
            self._add_drawer(shelf, "Sundowner at the lodge", None, dt_time(18, 30), 60, order,
                              "EXPERIENCE", source="hardcoded_sundowner")

    @staticmethod
    def _add_drawer(shelf, name, description, start_time, duration_minutes, sort_order,
                     activity_type, activity_id=None, source="activities_table"):
        drawer = Drawer(
            shelf_id=shelf.id, activity_id=activity_id, name=name, description=description,
            start_time=start_time, duration_minutes=duration_minutes, sort_order=sort_order,
            activity_type=activity_type,
        )
        if hasattr(drawer, "source"):
            drawer.source = source
        shelf.drawers.append(drawer) if hasattr(shelf, "drawers") else None

    # ------------------------------------------------------------------
    def _build_hinges(self, cabinet_id, destination_ids: list[str]) -> list[dict]:
        legs = []
        for i in range(len(destination_ids) - 1):
            frm, to = destination_ids[i], destination_ids[i + 1]
            if frm == to:
                continue # TC-B4: skip zero-distance repeated-destination pairs
            row = self.db.execute(text("""
                select distance_km, duration_minutes_dry_season
                from drive_times where destination_id = :to_dest
                order by distance_km asc limit 1
            """), {"to_dest": to}).fetchone()
            if row:
                distance_km, duration_minutes, source = float(row[0]), int(row[1]), "drive_times"
            else:
                distance_km, duration_minutes, source = 150.0, 180, "fallback_estimate"
                logger.warning("No drive_times row for %s -> %s; using fallback estimate", frm, to)
            hinge = Hinge(cabinet_id=cabinet_id, from_destination_id=frm, to_destination_id=to,
                          sequence_order=len(legs) + 1, distance_km=distance_km,
                          duration_minutes=duration_minutes, mode="private_4x4", source=source)
            self.db.add(hinge)
            legs.append({"from": frm, "to": to, "duration_minutes": duration_minutes, "source": source})
        return legs

    def _allocate_days(self, destination_ids, total_days, relaxed):
        n = len(destination_ids)
        if n == 0:
            return []
        base = total_days // n
        remainder = total_days % n
        allocation = [base] * n
        i = n - 1
        while remainder > 0:
            allocation[i] += 1
            remainder -= 1
            i -= 1
        return [max(1, a) for a in allocation]

    def _resolve_destination_types(self, destination_ids: list[str]) -> dict[str, str | None]:
        if not destination_ids:
            return {}
        rows = self.db.execute(text("""
            select id::text, destination_type::text from travel_places where id = any(:ids)
        """), {"ids": destination_ids}).fetchall()
        return {r[0]: r[1] for r in rows}

    def _populate_headboard(self, shelf, dest_id, budget_tier, remaining_nights_here):
        tier_map = {"budget": ("budget", "camping"), "mid": ("mid_range",), "luxury": ("luxury", "ultra_luxury")}
        tiers = tier_map.get(budget_tier, ("mid_range",))
        row = self.db.execute(text("""
            select id, name, tier from lodges
            where destination_id = :dest_id and tier = any(:tiers)
            order by star_rating desc nulls last limit 1
        """), {"dest_id": dest_id, "tiers": list(tiers)}).fetchone()
        if row:
            self.db.add(Headboard(shelf_id=shelf.id, lodge_id=row[0], name=row[1], tier=row[2],
                                   check_in=shelf.date, nights=remaining_nights_here))
        else:
            self.db.add(Headboard(shelf_id=shelf.id, name=f"{budget_tier.title()} lodge",
                                   tier=budget_tier, check_in=shelf.date, nights=remaining_nights_here))

    def _populate_armrest(self, shelf, dest_id, legs, dest_idx, is_arrival_day):
        if is_arrival_day and dest_idx > 0:
            leg = legs[dest_idx - 1]
            minutes = leg["duration_minutes"]
            self.db.add(Armrest(shelf_id=shelf.id, mode="private_4x4",
                                 description=f"Private 4x4 · {minutes} min transfer",
                                 duration_minutes=minutes, is_private=True))
        else:
            self.db.add(Armrest(shelf_id=shelf.id, mode="private_4x4",
                                 description="Private 4x4 · within-park game drives",
                                 duration_minutes=0, is_private=True))

    def _populate_trays(self, shelf, is_first_day):
        meals = ["dinner"] if is_first_day else ["breakfast", "lunch", "dinner"]
        for m in meals:
            self.db.add(Tray(shelf_id=shelf.id, meal_type=m, included=True))

    @staticmethod
    def _theme_for(idx, night_idx, is_first, is_last) -> str:
        if is_first:
            return "Arrival & slow start"
        if is_last:
            return "Departure"
        return "Wildlife & wide horizons" if night_idx == 0 else "Deeper into the park"

    @staticmethod
    def _infer_style(request: dict[str, Any]) -> list[str]:
        style = []
        if request.get("focus") == "wildlife":
            style.append("wildlife")
        if request.get("budget_tier") == "luxury":
            style.append("luxury")
        if request.get("travelers", 2) <= 2:
            style.append("private")
        style.append("relaxed_pace")
        return style

    @staticmethod
    def _default_title(request: dict[str, Any]) -> str:
        country = request.get("country_name", "Africa")
        return f"{country}, Wild & Unhurried"

