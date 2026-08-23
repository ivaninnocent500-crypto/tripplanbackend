"""
QuoteEngine (v2) — same responsibilities as before (request_quotes /
record_quote / tracking_summary / compare), PLUS the brief's core ask:

  When the customer taps "Request quotes", the backend must:
    1. Persist the Bench/Mirror rows (unchanged from v1).
    2. Email the admin inbox with the request details (Brevo).
    3. Email the customer a confirmation that operators are working on it.

Email sends are wrapped in call_engine(..., db=None) — NOT db=db — on
purpose: an email failure is not a database error and must never touch
the transaction that already committed the benches/mirrors. Rolling
back a real, already-persisted quote request just because an email
provider timed out would be strictly worse than sending no email at all.
The route layer (trip_v2.py) still commits benches before attempting
either email, so "operators never notified because email failed" never
becomes "quote request silently vanished."
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models_furniture import Bench, Cabinet, Counter, Mirror
from app.engines.resilience import call_engine
from app.integrations.brevo_client import get_brevo_client


class QuoteEngine:
    def __init__(self, db: Session):
        self.db = db

    def _operator_name(self, operator_id) -> str | None:
        row = self.db.execute(
            text("select name from tour_operators where id = :id"), {"id": operator_id},
        ).fetchone()
        return row[0] if row else None

    # ------------------------------------------------------------------
    def request_quotes(
        self,
        cabinet: Cabinet,
        tour_operator_ids: list[str],
        note: str | None,
        visa_addon_selected: bool | None = None,
        traveler_nationality: str | None = None,
    ) -> list[Bench]:
        # Persist the trip-level checkout choices captured on this screen
        # (F: visa add-on toggle) before creating benches, so the email
        # content below reflects what was actually selected.
        if visa_addon_selected is not None:
            cabinet.visa_addon_selected = visa_addon_selected
        if traveler_nationality:
            cabinet.traveler_nationality = traveler_nationality
        self.db.add(cabinet)

        benches = []
        for op_id in tour_operator_ids:
            bench = Bench(cabinet_id=cabinet.id, tour_operator_id=op_id, status="request_sent", note=note)
            self.db.add(bench)
            benches.append(bench)
        self.db.flush()

        for bench in benches:
            self.db.add(Mirror(
                cabinet_id=cabinet.id, bench_id=bench.id, channel="push",
                message="We'll notify you the moment a quote lands.",
            ))
        cabinet.status = "quoting"
        self.db.add(cabinet)
        self.db.flush()
        return benches

    # ------------------------------------------------------------------
    def notify_quote_request(
        self, cabinet: Cabinet, benches: list[Bench], note: str | None, user_email: str | None,
    ) -> dict[str, Any]:
        """
        Fires the two Brevo emails required by the brief. Call this AFTER
        request_quotes() has been committed — see trip_v2.py's
        request_quotes route for the call order. Returns a small summary
        dict; never raises (both sends go through call_engine).
        """
        bench_summaries = [
            {"tour_operator_id": str(b.tour_operator_id), "operator_name": self._operator_name(b.tour_operator_id)}
            for b in benches
        ]
        client = get_brevo_client()
        result = {"admin_notified": False, "user_notified": False, "email_configured": client.is_available()}

        if not client.is_available():
            return result # dev/local env without BREVO_API_KEY — degrade silently, don't 500

        admin_result = call_engine(
            "BrevoEmail.send_admin_quote_alert",
            lambda: client.send_admin_quote_alert(cabinet, bench_summaries, note, user_email),
            fallback=None, db=None,
        )
        result["admin_notified"] = not admin_result.degraded

        if user_email:
            user_result = call_engine(
                "BrevoEmail.send_user_quote_confirmation",
                lambda: client.send_user_quote_confirmation(cabinet, user_email, bench_summaries),
                fallback=None, db=None,
            )
            result["user_notified"] = not user_result.degraded

        return result

    # ------------------------------------------------------------------
    def record_quote(self, bench: Bench, quote_data: dict[str, Any]) -> Counter:
        counter = Counter(
            bench_id=bench.id,
            price_per_person=quote_data["price_per_person"],
            currency=quote_data.get("currency", "USD"),
            validity_date=quote_data.get("validity_date"),
            accommodation_summary=quote_data.get("accommodation_summary"),
            activities_summary=quote_data.get("activities_summary"),
            transport_summary=quote_data.get("transport_summary"),
            meals_summary=quote_data.get("meals_summary"),
            difference_notes=quote_data.get("difference_notes"),
        )
        self.db.add(counter)
        bench.status = "quote_received"
        self.db.add(bench)
        self.db.flush()
        return counter

    # ------------------------------------------------------------------
    def tracking_summary(self, cabinet: Cabinet) -> dict[str, Any]:
        benches = cabinet.benches
        return {
            "requests_sent": len(benches),
            "quotes_received": sum(1 for b in benches if b.status == "quote_received"),
            "awaiting_response": sum(1 for b in benches if b.status in ("request_sent", "operator_reviewing")),
            "benches": [
                {
                    "bench_id": str(b.id),
                    "tour_operator_id": str(b.tour_operator_id),
                    "operator_name": self._operator_name(b.tour_operator_id),
                    "status": b.status,
                    "quote": (
                        {"price_per_person": float(b.counters[0].price_per_person), "currency": b.counters[0].currency}
                        if b.counters else None
                    ),
                }
                for b in benches
            ],
        }

    # ------------------------------------------------------------------
    def compare(self, cabinet: Cabinet) -> dict[str, Any]:
        rows = []
        for b in cabinet.benches:
            if not b.counters:
                continue
            c = b.counters[0]
            operator_row = self.db.execute(
                text("""select cancellation_policy_summary, escrow_protected, escrow_notes
                       from tour_operators where id = :id"""),
                {"id": b.tour_operator_id},
            ).fetchone()
            rows.append({
                "bench_id": str(b.id),
                "counter_id": str(c.id),
                "tour_operator_id": str(b.tour_operator_id),
                "operator_name": self._operator_name(b.tour_operator_id),
                "price_per_person": float(c.price_per_person),
                "accommodation": c.accommodation_summary,
                "activities": c.activities_summary,
                "transport": c.transport_summary,
                "meals": c.meals_summary,
                "park_fees_included": c.park_fees_included,
                "transfers_included": c.transfers_included,
                "validity_date": c.validity_date.isoformat() if c.validity_date else None,
                "difference_notes": c.difference_notes,
                # F: Trust & Policy accordion additions.
                "cancellation_policy_summary": operator_row[0] if operator_row else None,
                "escrow_protected": bool(operator_row[1]) if operator_row else True,
                "escrow_notes": operator_row[2] if operator_row else (
                    "Funds are held securely and released to the operator per the agreed schedule."
                ),
            })

        best_value = min(rows, key=lambda r: r["price_per_person"], default=None)
        best_fit = rows[0] if rows else None

        return {"quotes": rows, "best_value_bench_id": best_value["bench_id"] if best_value else None,
                "best_fit_bench_id": best_fit["bench_id"] if best_fit else None}

