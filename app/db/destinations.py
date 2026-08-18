"""
Slug <-> UUID resolution. The API contract (TripRequest.destinations,
e.g. ["nairobi", "maasai_mara"]) predates the real Supabase data, and the
real travel_places.slug values turned out to be hyphenated
("maasai-mara-national-reserve"), not the short underscore style assumed
earlier ("maasai_mara"). This resolver normalizes both directions so
existing callers don't all need simultaneous updates — without this,
every request would have silently resolved zero destinations, since
"maasai_mara" != "maasai-mara-national-reserve" as a literal string match.
"""
from __future__ import annotations

import re
from sqlalchemy.orm import Session
from app.db.models_v2 import TravelPlace


def _normalize(value: str) -> str:
    """
    Normalizes any slug-like string: lowercase, hyphens/underscores/
    whitespace all collapsed to a single hyphen. "maasai_mara",
    "maasai-mara", and "Maasai Mara" all normalize identically.
    """
    return re.sub(r"[\s_-]+", "-", value.strip().lower())


def resolve_slugs_to_ids(db: Session, slugs: list[str]) -> dict[str, str]:
    """
    Returns {ORIGINAL_input_slug: uuid_string} for every slug that
    resolves — keyed by what the CALLER passed in (e.g. "maasai_mara"),
    not the real DB slug, so downstream code that keys off the original
    request strings (orchestrator.py's `unmatched` list, engines that
    build a slug_to_id dict) doesn't need to change even though the real
    slug format differs.

    Matching strategy: exact normalized match first; if that fails, also
    matches when the real DB slug starts with "{normalized-input}-" (so
    "maasai-mara" matches "maasai-mara-national-reserve") — but NOT the
    reverse (a short input shouldn't accidentally match multiple longer
    real slugs sharing a prefix; if that becomes a real ambiguity as the
    knowledge base grows past ~30 destinations, switch to exact-only
    matching and update caller-side slugs to the real values instead).
    """
    if not slugs:
        return {}

    normalized_input = {_normalize(s): s for s in slugs}
    rows = db.query(TravelPlace.id, TravelPlace.slug).all()

    result: dict[str, str] = {}
    for row_id, row_slug in rows:
        normalized_db_slug = _normalize(row_slug)
        for norm_input, original_input in normalized_input.items():
            if original_input in result:
                continue  # already matched, don't overwrite with a second candidate
            if norm_input == normalized_db_slug or normalized_db_slug.startswith(norm_input + "-"):
                result[original_input] = row_id

    return result


def get_destination_by_slug(db: Session, slug: str) -> TravelPlace | None:
    resolved = resolve_slugs_to_ids(db, [slug])
    if slug not in resolved:
        return None
    return db.query(TravelPlace).filter(TravelPlace.id == resolved[slug]).first()


def get_lat_lng(db: Session, destination_id: str) -> tuple[float, float] | None:
    """
    Extracts plain lat/lng floats from the PostGIS geography(Point)
    column, for engines/responses that need simple coordinates (e.g. the
    Android app's RouteSummaryMap / OSMDroid pins).
    """
    from sqlalchemy import text

    result = db.execute(
        text(
            "SELECT ST_Y(centroid::geometry) as lat, ST_X(centroid::geometry) as lng "
            "FROM physical_geography WHERE destination_id = :dest_id"
        ),
        {"dest_id": destination_id}
    ).fetchone()

    if result is None or result.lat is None or result.lng is None:
        return None
    return (float(result.lat), float(result.lng))
