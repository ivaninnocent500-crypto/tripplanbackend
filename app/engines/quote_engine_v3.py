"""
QuoteEngine (v3) — additive on top of quote_engine_v2.py:

  1. record_quote() now sets bench.responded_at = now(). Neither v1 nor
     v2 did this — the column has existed on `benches` since the
     original furniture schema, but nothing ever wrote to it, which
     made "operator replies within ~4 hours" (Operator tab) impossible
     to compute honestly from real data. This is the fix.
  2. notify_quote_received() — the customer-facing "a quote landed"
     email, sent once record_quote() commits. Mirrors the
     notify_quote_request() pattern from v2: wrapped in call_engine
     with db=None so an email hiccup never touches the already-
     committed Counter/Bench rows.

Only these two changes; everything else (request_quotes, compare,
tracking_summary) is unchanged from quote_engine_v2.py — merge by
adding these two methods and the one-line responded_at fix, not by
replacing the whole class.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.db.models_furniture import Bench, Counter
from app.engines.resilience import call_engine
from app.integrations.brevo_client import get_brevo_client


def record_quote_with_response_time(self, bench: Bench, quote_data: dict[str, Any]) -> Counter:
    """Replaces QuoteEngine.record_quote from v1/v2 — same signature."""
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
    bench.responded_at = datetime.now(timezone.utc) # <-- the actual fix
    self.db.add(bench)
    self.db.flush()
    return counter


def notify_quote_received(self, cabinet, bench: Bench, counter: Counter, user_email: str | None) -> dict[str, Any]:
    """
    Fires the "your quote is ready" customer email. Call this AFTER
    record_quote_with_response_time() has been committed (same
    commit-before-notify pattern as notify_quote_request in v2).
    """
    client = get_brevo_client()
    if not client.is_available() or not user_email:
        return {"user_notified": False, "email_configured": client.is_available()}

    operator_name = self._operator_name(bench.tour_operator_id) or "your selected operator"
    subject = f"Your quote from {operator_name} has arrived — {cabinet.title}"
    html = f"""
    <h3>Good news — a quote just landed!</h3>
    <p><b>{operator_name}</b> quoted <b>${counter.price_per_person:.2f} per person</b> for your trip.</p>
    <p>Open the app to review the full quote and compare it against your other requests.</p>
    """
    result = call_engine(
        "BrevoEmail.notify_quote_received",
        lambda: client._send(to=[{"email": user_email}], subject=subject, html_content=html),
        fallback=None, db=None,
    )
    return {"user_notified": not result.degraded, "email_configured": True}

