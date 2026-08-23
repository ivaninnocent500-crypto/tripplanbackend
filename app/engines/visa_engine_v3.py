"""
VisaIntelligenceEngine (v3) — the checkout screenshots show specific
fields (Cost, Processing time) that the v1 engine's border_crossings-
only lookup can't provide. This checks `visa_requirements` (migration
011) FIRST — it's the table that actually has fee_usd/processing_days_
typical — falling back to border_crossings notes, then to the honest
"unverified" message, exactly like v1 did for the two-tier case.

Same rule as before: never invented, always sourced. If nationality
isn't in visa_requirements, this does NOT guess a generic answer.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models_furniture import Cabinet


class VisaIntelligenceEngineV3:
    def __init__(self, db: Session):
        self.db = db

    def entry_requirements_for_trip(self, cabinet: Cabinet, traveler_nationality: str | None) -> dict[str, Any]:
        countries = getattr(cabinet, "route_countries", None) or self._infer_countries(cabinet)
        country_results = [self._requirement_for_country(c, traveler_nationality) for c in countries]
        border_notes = self._border_notes_for_route(countries)

        return {
            "traveler_nationality": traveler_nationality,
            "countries": country_results,
            "border_crossings": border_notes,
            "data_confidence": (
                "verified" if country_results and all(r["source"] in ("visa_requirements", "border_crossings")
                                                       for r in country_results)
                else "partial_or_unverified"
            ),
        }

    # ------------------------------------------------------------------
    def _infer_countries(self, cabinet: Cabinet) -> list[str]:
        if not cabinet.route_destination_ids:
            return []
        rows = self.db.execute(
            text("select distinct country::text from travel_places where id = any(:ids)"),
            {"ids": cabinet.route_destination_ids},
        ).fetchall()
        return [r[0] for r in rows]

    def _requirement_for_country(self, country: str, nationality: str | None) -> dict[str, Any]:
        if not nationality:
            return {
                "country": country, "requirement": "unknown",
                "notes": "Add your nationality to get a specific visa answer for this destination.",
                "fee_usd": None, "processing_days_typical": None,
                "source": "no_nationality_provided",
            }

        # Tier 1: visa_requirements — has the real fee/processing fields
        # the checkout screen displays.
        row = self.db.execute(
            text("""
                select requirement, fee_usd, processing_days_typical, notes, applicable_bloc_code
                from visa_requirements
                where nationality_country = :nat and destination_country = :country
            """),
            {"nat": nationality, "country": country},
        ).fetchone()
        if row:
            requirement, fee_usd, processing_days, notes, bloc_code = row
            result = {
                "country": country, "requirement": requirement,
                "notes": notes, "fee_usd": float(fee_usd) if fee_usd is not None else None,
                "processing_days_typical": processing_days,
                "source": "visa_requirements",
            }
            if bloc_code:
                bloc_row = self.db.execute(
                    text("select name, member_countries from regional_visa_blocs where bloc_code = :code"),
                    {"code": bloc_code},
                ).fetchone()
                if bloc_row:
                    result["regional_bloc"] = {"name": bloc_row[0], "member_countries": list(bloc_row[1] or [])}
            return result

        # Tier 2: border_crossings.visa_notes (weaker signal — a note
        # attached to a crossing, not a nationality-specific rule).
        bc_row = self.db.execute(
            text("""
                select visa_notes from border_crossings
                where country_a = :country or country_b = :country
                order by (visa_notes is not null) desc limit 1
            """),
            {"country": country},
        ).fetchone()
        if bc_row and bc_row[0]:
            return {
                "country": country, "requirement": "see_notes", "notes": bc_row[0],
                "fee_usd": None, "processing_days_typical": None, "source": "border_crossings",
            }

        # Tier 3: honest unknown.
        return {
            "country": country, "requirement": "unknown",
            "notes": (
                f"We don't have a verified visa rule for {nationality} travelers entering {country} yet. "
                "Please confirm with the relevant embassy/consulate or an e-visa portal before booking."
            ),
            "fee_usd": None, "processing_days_typical": None, "source": "unverified_no_data",
        }

    def _border_notes_for_route(self, countries: list[str]) -> list[dict[str, Any]]:
        if len(countries) < 2:
            return []
        out = []
        for i in range(len(countries) - 1):
            a, b = countries[i], countries[i + 1]
            row = self.db.execute(
                text("""
                    select name, status::text, visa_notes from border_crossings
                    where (country_a = :a and country_b = :b) or (country_a = :b and country_b = :a)
                    limit 1
                """),
                {"a": a, "b": b},
            ).fetchone()
            if row:
                out.append({"leg": f"{a} -> {b}", "crossing": row[0], "status": row[1], "notes": row[2]})
            else:
                out.append({
                    "leg": f"{a} -> {b}", "crossing": None, "status": "unknown",
                    "notes": "No border-crossing record on file for this leg — verify manually before travel.",
                })
        return out

