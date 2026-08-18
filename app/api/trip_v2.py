"""
Trip lifecycle routes — the entire backend contract for the app screens:
generate -> match operators -> request/track/compare quotes -> book ->
confirm. One endpoint per screen, all backed by persisted Cabinet state
(no ephemeral in-memory response — see app/db/models_furniture.py).

Each engine call is wrapped in call_engine() (app/engines/resilience.py),
same pattern your original orchestrator.py used: failures degrade
gracefully into an EngineResult with .degraded=True rather than crashing
the whole request. RulesEngine.evaluate_rules() runs first — it currently
always returns {"status": "success", "validated": True} (a stub), so this
just logs a warning if that ever changes rather than blocking requests.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import require_api_key
from app.db.session import get_supabase_db
from app.db.destinations import resolve_slugs_to_ids
from app.db.models_furniture import Bench, Cabinet, Counter, Wardrobe
from app.engines.rules import RulesEngine
from app.engines.resilience import call_engine
from app.engines.itinerary_v2 import ItineraryPlanningEngine
from app.engines.validation import ValidationEngine
from app.engines.explanation import ExplanationEngine
from app.engines.operator_match_v2 import OperatorMatchEngine
from app.engines.quote_engine import QuoteEngine
from app.engines.booking_engine import BookingEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/trips", tags=["trips"])


def _get_cabinet_or_404(db: Session, cabinet_id: str) -> Cabinet:
    cabinet = db.get(Cabinet, cabinet_id)
    if not cabinet:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trip not found")
    return cabinet


def _operator_summary(db: Session, tour_operator_id) -> dict:
    row = db.execute(
        text("select name, years_in_operation, headquarters_country, verification_status "
             "from tour_operators where id = :id"),
        {"id": tour_operator_id},
    ).fetchone()
    if not row:
        return {"name": None, "years_in_operation": None, "headquarters_country": None, "verification_status": None}
    return {"name": row[0], "years_in_operation": row[1], "headquarters_country": row[2], "verification_status": row[3]}


# ---------------------------------------------------------------------
@router.post("/generate")
def generate_trip(request: dict, db: Session = Depends(get_supabase_db), _=Depends(require_api_key)):
    rules_result = RulesEngine().evaluate_rules(dict(request))
    if rules_result.get("status") != "success" or not rules_result.get("validated", False):
        logger.warning("Rules validation did not pass: %s", rules_result)

    slug_to_id = resolve_slugs_to_ids(db, request["destinations"])
    ordered_ids = [slug_to_id[s] for s in request["destinations"] if s in slug_to_id]
    unmatched = [s for s in request["destinations"] if s not in slug_to_id]
    if not ordered_ids:
        raise HTTPException(422, "None of the requested destinations could be resolved.")

    build_result = call_engine(
        "ItineraryPlanningEngine",
        lambda: ItineraryPlanningEngine(db).build(request, ordered_ids),
        fallback=None,
    )
    if build_result.value is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Trip generation failed unexpectedly.")

    cabinet = build_result.value.cabinet

    validation_result = call_engine(
        "ValidationEngine",
        lambda: ValidationEngine(db).validate(cabinet),
        fallback={"status": "unknown", "issue_count": 0, "errors": [], "warnings": ["Validation engine unavailable"]},
    )

    explanation_result = call_engine(
        "ExplanationEngine",
        lambda: ExplanationEngine().explain(cabinet),
        fallback={"facts": [], "generated_by": "unavailable"},
    )

    db.commit()

    return {
        "cabinet_id": str(cabinet.id),
        "status": cabinet.status,
        "validation": validation_result.value,
        "why_itinerary": explanation_result.value["facts"],
        "days": [_day_to_dict(s) for s in cabinet.shelves],
        "generation_meta": {
            "degraded": build_result.degraded or validation_result.degraded or explanation_result.degraded,
            "unmatched_destinations": unmatched,
        },
    }


@router.get("/{cabinet_id}")
def get_trip(cabinet_id: str, db: Session = Depends(get_supabase_db), _=Depends(require_api_key)):
    cabinet = _get_cabinet_or_404(db, cabinet_id)
    explanation_result = call_engine(
        "ExplanationEngine", lambda: ExplanationEngine().explain(cabinet), fallback={"facts": []},
    )
    return {
        "cabinet_id": str(cabinet.id),
        "title": cabinet.title,
        "status": cabinet.status,
        "duration_days": cabinet.duration_days,
        "travelers": cabinet.travelers_adults + cabinet.travelers_children,
        "style": cabinet.travel_style,
        "route": [str(x) for x in cabinet.route_destination_ids],
        "dates": {"start": cabinet.start_date, "end": cabinet.end_date},
        "estimated_budget": {"low": cabinet.estimated_budget_low, "high": cabinet.estimated_budget_high},
        "days": [_day_to_dict(s) for s in cabinet.shelves],
        "why_itinerary": explanation_result.value["facts"],
    }


# ---------------------------------------------------------------------
@router.post("/{cabinet_id}/match-operators")
def match_operators(cabinet_id: str, db: Session = Depends(get_supabase_db), _=Depends(require_api_key)):
    cabinet = _get_cabinet_or_404(db, cabinet_id)
    match_result = call_engine(
        "OperatorMatchEngine", lambda: OperatorMatchEngine(db).match(cabinet), fallback=[],
    )
    cabinet.status = "matching"
    db.add(cabinet)
    db.commit()

    matches = []
    for s in match_result.value:
        summary = _operator_summary(db, s.tour_operator_id)
        matches.append({
            "tour_operator_id": str(s.tour_operator_id),
            "operator_name": summary["name"],
            "years_in_operation": summary["years_in_operation"],
            "headquarters_country": summary["headquarters_country"],
            "verification_status": summary["verification_status"],
            "trip_match_pct": s.trip_match_pct,
            "badge": s.badge,
            "strengths": s.strengths,
            "estimated_price_pp": float(s.estimated_price_pp) if s.estimated_price_pp else None,
        })

    return {"degraded": match_result.degraded, "matches": matches}


# ---------------------------------------------------------------------
@router.post("/{cabinet_id}/quotes/request")
def request_quotes(cabinet_id: str, body: dict, db: Session = Depends(get_supabase_db), _=Depends(require_api_key)):
    cabinet = _get_cabinet_or_404(db, cabinet_id)
    result = call_engine(
        "QuoteEngine.request_quotes",
        lambda: QuoteEngine(db).request_quotes(cabinet, body["tour_operator_ids"], body.get("note")),
        fallback=[],
    )
    db.commit()
    return {"degraded": result.degraded, "benches": [str(b.id) for b in result.value], "status": "request_sent"}


@router.get("/{cabinet_id}/quotes")
def track_quotes(cabinet_id: str, db: Session = Depends(get_supabase_db), _=Depends(require_api_key)):
    cabinet = _get_cabinet_or_404(db, cabinet_id)
    result = call_engine(
        "QuoteEngine.tracking_summary", lambda: QuoteEngine(db).tracking_summary(cabinet),
        fallback={"requests_sent": 0, "quotes_received": 0, "awaiting_response": 0, "benches": []},
    )
    return result.value


@router.get("/{cabinet_id}/quotes/compare")
def compare_quotes(cabinet_id: str, db: Session = Depends(get_supabase_db), _=Depends(require_api_key)):
    cabinet = _get_cabinet_or_404(db, cabinet_id)
    result = call_engine(
        "QuoteEngine.compare", lambda: QuoteEngine(db).compare(cabinet),
        fallback={"quotes": [], "best_value_bench_id": None, "best_fit_bench_id": None},
    )
    return result.value


# ---------------------------------------------------------------------
@router.post("/{cabinet_id}/book")
def book_trip(cabinet_id: str, body: dict, db: Session = Depends(get_supabase_db), _=Depends(require_api_key)):
    cabinet = _get_cabinet_or_404(db, cabinet_id)
    counter = db.get(Counter, body["counter_id"])
    if not counter:
        raise HTTPException(404, "Quote not found")

    result = call_engine(
        "BookingEngine.create_booking", lambda: BookingEngine(db).create_booking(cabinet, counter), fallback=None,
    )
    if result.value is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Booking failed unexpectedly.")

    db.commit()
    return _wardrobe_to_dict(db, result.value)


@router.post("/bookings/{wardrobe_id}/confirm")
def confirm_booking(wardrobe_id: str, db: Session = Depends(get_supabase_db), _=Depends(require_api_key)):
    wardrobe = db.get(Wardrobe, wardrobe_id)
    if not wardrobe:
        raise HTTPException(404, "Booking not found")

    result = call_engine(
        "BookingEngine.confirm_booking", lambda: BookingEngine(db).confirm_booking(wardrobe), fallback=None,
    )
    if result.value is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Confirmation failed unexpectedly.")

    db.commit()
    return _wardrobe_to_dict(db, wardrobe)


# ---------------------------------------------------------------------
def _wardrobe_to_dict(db: Session, wardrobe: Wardrobe) -> dict:
    """
    Full payload for the "Your safari is ready" / "Booking confirmed"
    screens (img 12 / img 1) — trip title, operator name, dates,
    travelers, accommodation, transport, price, deposit, status.
    Previously book_trip/confirm_booking only returned the four booking
    fields; this was a real gap against what those two screens display,
    found while checking output against the screenshots.
    """
    cabinet = wardrobe.cabinet
    operator_row = db.execute(
        text("select name from tour_operators where id = :id"),
        {"id": wardrobe.tour_operator_id},
    ).fetchone()
    operator_name = operator_row[0] if operator_row else None

    first_shelf = cabinet.shelves[0] if cabinet.shelves else None
    accommodation = None
    transport = None
    if first_shelf:
        nights_total = sum(h.nights for s in cabinet.shelves for h in s.headboards)
        tier = first_shelf.headboards[0].tier if first_shelf.headboards else None
        accommodation = f"{(tier or 'Standard').title()} lodge · {nights_total} nights" if nights_total else None
        transport = first_shelf.armrests[0].description.split(" · ")[0] if first_shelf.armrests else None

    return {
        "wardrobe_id": str(wardrobe.id),
        "confirmation_code": wardrobe.confirmation_code,
        "trip_title": cabinet.title,
        "operator_name": operator_name,
        "dates": {"start": cabinet.start_date, "end": cabinet.end_date},
        "travelers": cabinet.travelers_adults + cabinet.travelers_children,
        "accommodation": accommodation,
        "transport": transport,
        "price_per_person": float(wardrobe.price_per_person),
        "total_price": float(wardrobe.total_price),
        "deposit_amount": float(wardrobe.deposit_amount) if wardrobe.deposit_amount else None,
        "status": wardrobe.status,
    }


# ---------------------------------------------------------------------
def _day_to_dict(shelf) -> dict:
    return {
        "day": shelf.day_number,
        "date": shelf.date,
        "destination_id": str(shelf.destination_id) if shelf.destination_id else None,
        "theme": shelf.theme,
        "activities": [
            {"name": d.name, "description": d.description, "start_time": str(d.start_time) if d.start_time else None,
             "duration_minutes": d.duration_minutes, "type": d.activity_type}
            for d in sorted(shelf.drawers, key=lambda x: x.sort_order)
        ],
        "accommodation": shelf.headboards[0].name if shelf.headboards else None,
        "transport": shelf.armrests[0].description if shelf.armrests else None,
        "meals": [t.meal_type for t in shelf.trays if t.included],
    }
