"""
QuoteEngine — the marketplace transactional layer described in the
planning doc (section 11), backing the "Get your safari quotes",
"Your safari quotes" tracking screen, and "Compare your quotes" screen.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models_furniture import Bench, Cabinet, Counter, Mirror


class QuoteEngine:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    def request_quotes(self, cabinet: Cabinet, tour_operator_ids: list[str], note: str | None) -> list[Bench]:
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
    def record_quote(self, bench: Bench, quote_data: dict[str, Any]) -> Counter:
        """Called by whatever ingests an operator's reply (webhook, ops-team form, etc.)."""
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
                    "status": b.status,
                    "quote": (
                        {
                            "price_per_person": float(b.counters[0].price_per_person),
                            "currency": b.counters[0].currency,
                        } if b.counters else None
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
            rows.append({
                "bench_id": str(b.id),
                "tour_operator_id": str(b.tour_operator_id),
                "price_per_person": float(c.price_per_person),
                "accommodation": c.accommodation_summary,
                "activities": c.activities_summary,
                "transport": c.transport_summary,
                "meals": c.meals_summary,
                "park_fees_included": c.park_fees_included,
                "transfers_included": c.transfers_included,
                "validity_date": c.validity_date.isoformat() if c.validity_date else None,
                "difference_notes": c.difference_notes,
            })

        best_value = min(rows, key=lambda r: r["price_per_person"], default=None)
        best_fit = rows[0] if rows else None  # caller should re-sort by matching `stools.trip_match_pct`

        return {"quotes": rows, "best_value_bench_id": best_value["bench_id"] if best_value else None,
                "best_fit_bench_id": best_fit["bench_id"] if best_fit else None}
