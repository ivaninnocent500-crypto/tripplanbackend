"""
Three new route groups:

  1. POST /internal/benches/{bench_id}/record-quote — OPS-ONLY (see
     ops_auth.py). This is the endpoint from design option A in the
     quote-update discussion: your ops person (or later, an email-
     parsing webhook / operator portal) calls this once an operator's
     reply is in hand. It writes the Counter, flips the Bench status,
     sets responded_at, and emails the customer that a quote landed.

  2. GET /api/trips/{cabinet_id}/documents — customer-facing, backs the
     "Documents" tab. Returns whatever's in `trip_documents`; empty list
     is a valid, honest response (no generation pipeline exists yet —
     see migration 013's docstring).

  3. GET /api/trips/{cabinet_id}/operator — customer-facing, backs the
     "Operator" tab. Only meaningful after a Wardrobe (booking) exists;
     computes avg response time from real bench data instead of
     guessing a number.

Merge into trip_v2.py (or keep as a separate included router — either
works with FastAPI's `app.include_router`).
"""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import require_api_key
from app.api.ops_auth import require_ops_api_key
from app.db.session import get_supabase_db
from app.db.models_furniture import Bench, Cabinet
from app.engines.resilience import call_engine
from app.engines.quote_engine_v2 import QuoteEngine

router = APIRouter(prefix="/api/trips", tags=["trips"])
ops_router = APIRouter(prefix="/internal", tags=["ops"])


# =======================================================================
# 1. Ops-only: record an operator's quote reply
# =======================================================================
class RecordQuoteBody(BaseModel):
    price_per_person: float = Field(..., gt=0)
    currency: str = "USD"
    validity_date: date | None = None
    accommodation_summary: str | None = None
    activities_summary: str | None = None
    transport_summary: str | None = None
    meals_summary: str | None = None
    difference_notes: str | None = None
    user_email: str | None = None # so the "quote landed" email can be sent


@ops_router.post("/benches/{bench_id}/record-quote")
def record_quote(
    bench_id: str,
    body: RecordQuoteBody,
    db: Session = Depends(get_supabase_db),
    _=Depends(require_ops_api_key),
):
    bench = db.get(Bench, bench_id)
    if not bench:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quote request (bench) not found")

    cabinet = db.get(Cabinet, bench.cabinet_id)
    if not cabinet:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trip not found for this bench")

    engine = QuoteEngine(db)
    # record_quote_with_response_time / notify_quote_received are bound
    # onto QuoteEngine per quote_engine_v3.py's merge instructions.
    result = call_engine(
        "QuoteEngine.record_quote",
        lambda: engine.record_quote_with_response_time(bench, body.model_dump(exclude={"user_email"})),
        fallback=None, db=db,
    )
    if result.value is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to record quote.")

    db.commit()

    notify_result = {"user_notified": False, "email_configured": False}
    if body.user_email:
        notify_result = engine.notify_quote_received(cabinet, bench, result.value, body.user_email)

    return {
        "bench_id": str(bench.id),
        "counter_id": str(result.value.id),
        "status": "quote_received",
        "notifications": notify_result,
    }


# =======================================================================
# 2. Customer-facing: Documents tab
# =======================================================================
@router.get("/{cabinet_id}/documents")
def get_documents(cabinet_id: str, db: Session = Depends(get_supabase_db), _=Depends(require_api_key)):
    cabinet = db.get(Cabinet, cabinet_id)
    if not cabinet:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trip not found")

    rows = db.execute(
        text("""
            select document_type, display_name, file_url, generated_at
            from trip_documents
            where cabinet_id = :cabinet_id
            order by generated_at desc
        """),
        {"cabinet_id": cabinet_id},
    ).fetchall()

    return {
        "documents": [
            {
                "document_type": r[0], "display_name": r[1], "file_url": r[2],
                "generated_at": r[3].isoformat() if r[3] else None,
            }
            for r in rows
        ],
    }


# =======================================================================
# 3. Customer-facing: Operator tab
# =======================================================================
@router.get("/{cabinet_id}/operator")
def get_booked_operator(cabinet_id: str, db: Session = Depends(get_supabase_db), _=Depends(require_api_key)):
    cabinet = db.get(Cabinet, cabinet_id)
    if not cabinet:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trip not found")

    wardrobe_row = db.execute(
        text("select tour_operator_id from wardrobes where cabinet_id = :cid order by created_at desc limit 1"),
        {"cid": cabinet_id},
    ).fetchone()
    if not wardrobe_row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No confirmed operator yet for this trip")

    operator_id = wardrobe_row[0]
    operator_row = db.execute(
        text("""
            select name, headquarters_country, years_in_operation, verification_status, rating, review_count
            from tour_operators where id = :id
        """),
        {"id": operator_id},
    ).fetchone()
    if not operator_row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Operator record missing")

    # Honest average-response-time computation — null if no data yet,
    # never a placeholder like "~4 hours" invented for the UI.
    avg_row = db.execute(
        text("""
            select avg(extract(epoch from (responded_at - requested_at)) / 3600.0)
            from benches
            where tour_operator_id = :op_id and responded_at is not null
        """),
        {"op_id": operator_id},
    ).fetchone()
    avg_response_hours = round(float(avg_row[0]), 1) if avg_row and avg_row[0] is not None else None

    return {
        "tour_operator_id": str(operator_id),
        "name": operator_row[0],
        "headquarters_country": operator_row[1],
        "years_in_operation": operator_row[2],
        "verification_status": operator_row[3],
        "rating": float(operator_row[4]) if operator_row[4] is not None else None,
        "review_count": operator_row[5],
        "avg_response_hours": avg_response_hours,
        "avg_response_label": (
            f"Replies within ~{int(avg_response_hours)} hours" if avg_response_hours is not None
            else "Response time not yet available"
        ),
    }

