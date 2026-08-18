"""
BookingEngine — final step of the lifecycle: MATCH -> QUOTE -> COMPARE ->
BOOK -> PAY. Produces the "Your safari is ready" / "Booking confirmed"
screens.
"""
from __future__ import annotations

import random
import string

from sqlalchemy.orm import Session

from app.db.models_furniture import Cabinet, Chest, Counter, Wardrobe


class BookingEngine:
    def __init__(self, db: Session):
        self.db = db

    def create_booking(self, cabinet: Cabinet, counter: Counter, deposit_pct: float = 0.20) -> Wardrobe:
        travelers = cabinet.travelers_adults + cabinet.travelers_children
        total_price = float(counter.price_per_person) * travelers
        deposit = round(total_price * deposit_pct, 2)

        wardrobe = Wardrobe(
            cabinet_id=cabinet.id,
            counter_id=counter.id,
            confirmation_code=self._generate_code(cabinet),
            tour_operator_id=counter.bench.tour_operator_id,
            price_per_person=counter.price_per_person,
            total_price=total_price,
            deposit_amount=deposit,
            status="reserved",
        )
        self.db.add(wardrobe)
        cabinet.status = "booked"
        self.db.add(cabinet)
        self.db.flush()
        return wardrobe

    def confirm_booking(self, wardrobe: Wardrobe) -> Wardrobe:
        wardrobe.status = "confirmed"
        self.db.add(wardrobe)
        self.db.add(Chest(
            wardrobe_id=wardrobe.id, amount=wardrobe.deposit_amount, currency="USD",
            payment_type="deposit", status="completed",
        ))
        wardrobe.cabinet.status = "confirmed"
        self.db.add(wardrobe.cabinet)
        self.db.flush()
        return wardrobe

    @staticmethod
    def _generate_code(cabinet: Cabinet) -> str:
        country_hint = "TZ"  # derive from cabinet.primary_destination_id -> travel_places.country in production
        suffix = "".join(random.choices(string.digits, k=6))
        return f"ATO-{country_hint}-{suffix}"
