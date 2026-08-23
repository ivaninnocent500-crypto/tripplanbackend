"""
Brevo (formerly Sendinblue) transactional email client.

This is the piece the brief calls out explicitly: when a customer taps
"Request quotes" on the checkout screen, the backend must -

  1. Email the internal admin/ops inbox with the request details, so a
     human can chase operators that don't have an automated API.
  2. Email the customer a confirmation that their request went out and
     operators are working on it.

Design notes:
  - Fails soft. An email failure must NEVER block or roll back the
    quote-request transaction - the benches/counters rows are the
    source of truth, email is a notification layer on top. See how
    quote_engine.py wraps both sends in call_engine() with db=None
    (email failures don't need a DB rollback, they just get logged and
    reported via EngineResult.degraded).
  - No API key at import time is a config problem, not a fatal one -
    is_available() lets callers skip sending gracefully instead of
    exploding on every quote request in local/dev environments.
  - Uses httpx (already a transitive dependency of most FastAPI stacks;
    swap for `requests` if that's what's pinned in your requirements.txt).
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

ADMIN_NOTIFICATION_EMAIL = os.environ.get("ATI_ADMIN_EMAIL", "ops@africatravelos.com")
SENDER_EMAIL = os.environ.get("ATI_SENDER_EMAIL", "trips@africatravelos.com")
SENDER_NAME = os.environ.get("ATI_SENDER_NAME", "Africa Travel OS")


class BrevoNotConfiguredError(RuntimeError):
    """Raised when BREVO_API_KEY is missing - callers should catch this
    via is_available() rather than let it bubble into a user-facing 500."""


class BrevoEmailClient:
    def __init__(self):
        self.api_key = os.environ.get("BREVO_API_KEY")

    def is_available(self) -> bool:
        return bool(self.api_key)

    # ------------------------------------------------------------------
    def _send(
        self,
        to: list[dict[str, str]],
        subject: str,
        html_content: str,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise BrevoNotConfiguredError("BREVO_API_KEY is not set.")

        payload: dict[str, Any] = {
            "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
            "to": to,
            "subject": subject,
            "htmlContent": html_content,
        }
        if reply_to:
            payload["replyTo"] = {"email": reply_to}

        headers = {
            "accept": "application/json",
            "api-key": self.api_key,
            "content-type": "application/json",
        }
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(BREVO_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    def send_admin_quote_alert(
        self,
        cabinet,
        benches: list[dict[str, Any]],
        note: str | None,
        user_email: str | None,
    ) -> dict[str, Any]:
        """
        `benches` is the plain-dict summary (op_id/operator_name pairs) -
        pass dicts, not ORM rows, so this module has zero DB coupling.
        """
        operator_names = (
            ", ".join(
                b.get("operator_name") or str(b.get("tour_operator_id"))
                for b in benches
            )
            or "(no operators resolved)"
        )

        subject = f"New quote request - {cabinet.title} ({cabinet.duration_days}d, {cabinet.travelers_adults} pax)"
        html = f"""
        <h3>New safari quote request</h3>
        <p><b>Trip:</b> {cabinet.title}</p>
        <p><b>Cabinet ID:</b> {cabinet.id}</p>
        <p><b>Dates:</b> {cabinet.start_date} &ndash; {cabinet.end_date}</p>
        <p><b>Travelers:</b> {cabinet.travelers_adults} adults, {cabinet.travelers_children} children</p>
        <p><b>Budget tier:</b> {cabinet.budget_tier}</p>
        <p><b>Route countries:</b> {", ".join(getattr(cabinet, "route_countries", None) or [])}</p>
        <p><b>Operators requested:</b> {operator_names}</p>
        <p><b>Visa add-on requested:</b> {"Yes" if getattr(cabinet, "visa_addon_selected", False) else "No"}</p>
        <p><b>Customer note:</b> {note or "(none)"}</p>
        <p><b>Customer email:</b> {user_email or "(not provided)"}</p>
        <p>Please follow up with the requested operators and log their response in the ops dashboard.</p>
        """
        return self._send(
            to=[{"email": ADMIN_NOTIFICATION_EMAIL}],
            subject=subject,
            html_content=html,
            reply_to=user_email,
        )

    def send_user_quote_confirmation(
        self,
        cabinet,
        user_email: str,
        benches: list[dict[str, Any]],
    ) -> dict[str, Any]:
        operator_names = (
            ", ".join(
                b.get("operator_name") or "your selected operator"
                for b in benches
            )
            or "your selected operator"
        )

        subject = f"Your safari quote request is on its way - {cabinet.title}"
        html = f"""
        <h3>Thanks &mdash; we're on it!</h3>
        <p>We've sent your trip details for <b>{cabinet.title}</b> to {operator_names}.</p>
        <p>They typically respond within 24&ndash;48 hours. We'll notify you the moment a quote lands.</p>
        <p><b>Trip summary:</b></p>
        <ul>
          <li>Dates: {cabinet.start_date} &ndash; {cabinet.end_date}</li>
          <li>Travelers: {cabinet.travelers_adults} adults, {cabinet.travelers_children} children</li>
          <li>Style: {", ".join(cabinet.travel_style or [])}</li>
        </ul>
        <p>You can track responses any time from the Booking tab in the app.</p>
        """
        return self._send(
            to=[{"email": user_email}], subject=subject, html_content=html
        )

    def send_user_quote_received(
        self,
        cabinet,
        user_email: str,
        operator_name: str,
        price_per_person: float,
    ) -> dict[str, Any]:
        """
        The "a quote just landed" email - sent once an operator's reply
        has been recorded (see quote_engine_v3.py::notify_quote_received).
        Public method (unlike reaching into _send directly from another
        module) so callers outside this file have a stable API surface.
        """
        subject = f"Your quote from {operator_name} has arrived - {cabinet.title}"
        html = f"""
        <h3>Good news &mdash; a quote just landed!</h3>
        <p><b>{operator_name}</b> quoted <b>${price_per_person:.2f} per person</b> for your trip.</p>
        <p>Open the app to review the full quote and compare it against your other requests.</p>
        """
        return self._send(
            to=[{"email": user_email}], subject=subject, html_content=html
        )


_brevo_client_instance = BrevoEmailClient()


def get_brevo_client() -> BrevoEmailClient:
    return _brevo_client_instance

