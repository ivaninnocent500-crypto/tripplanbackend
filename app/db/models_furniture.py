"""
ORM models for the trip-instance layer (schema/002_furniture_schema.sql).

Matches the conventions in your real app/db/models_v2.py:
  - Base is declared there (declarative_base()) — imported from there,
    not a separate app/db/base.py (that file doesn't exist in your repo).
  - Primary/foreign keys use UUID(as_uuid=False) — plain Python strings,
    not uuid.UUID objects — same as TravelPlace.id, Lodge.id, etc.
    Mixing the two conventions in the same metadata causes comparison/
    join mismatches, so every column below follows models_v2's pattern.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY, Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, Text, Time, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.models_v2 import Base  # Base lives in models_v2.py in this repo


def gen_uuid() -> str:
    return str(uuid.uuid4())


def _uuid_pk():
    return Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)


def _uuid_fk(target: str, **kw):
    return Column(UUID(as_uuid=False), ForeignKey(target), **kw)


class Cabinet(Base):
    """A generated trip. Formerly ephemeral — this is the persisted Trip ID."""
    __tablename__ = "cabinets"

    id = _uuid_pk()
    request_json = Column(JSONB, nullable=False)
    title = Column(Text, nullable=False)
    duration_days = Column(Integer, nullable=False)
    travelers_adults = Column(Integer, nullable=False, default=1)
    travelers_children = Column(Integer, nullable=False, default=0)
    travel_style = Column(ARRAY(Text), nullable=False, default=list)
    budget_tier = Column(Text)
    status = Column(Text, nullable=False, default="draft")
    start_date = Column(Date)
    end_date = Column(Date)
    estimated_budget_low = Column(Numeric(10, 2))
    estimated_budget_high = Column(Numeric(10, 2))
    currency = Column(Text, nullable=False, default="USD")
    primary_destination_id = _uuid_fk("travel_places.id")
    route_destination_ids = Column(ARRAY(UUID(as_uuid=False)), nullable=False, default=list)
    confidence_score = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    shelves = relationship("Shelf", backref="cabinet", cascade="all, delete-orphan", order_by="Shelf.day_number")
    hinges = relationship("Hinge", backref="cabinet", cascade="all, delete-orphan", order_by="Hinge.sequence_order")
    footstools = relationship("Footstool", backref="cabinet", cascade="all, delete-orphan")
    stools = relationship("Stool", backref="cabinet", cascade="all, delete-orphan")
    benches = relationship("Bench", backref="cabinet", cascade="all, delete-orphan")
    wardrobes = relationship("Wardrobe", backref="cabinet", cascade="all, delete-orphan")


class Shelf(Base):
    """One day of a trip."""
    __tablename__ = "shelves"
    __table_args__ = (UniqueConstraint("cabinet_id", "day_number"),)

    id = _uuid_pk()
    cabinet_id = _uuid_fk("cabinets.id", nullable=False)
    day_number = Column(Integer, nullable=False)
    date = Column(Date)
    destination_id = _uuid_fk("travel_places.id")
    theme = Column(Text)
    hero_image_url = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    drawers = relationship("Drawer", backref="shelf", cascade="all, delete-orphan", order_by="Drawer.sort_order")
    headboards = relationship("Headboard", backref="shelf", cascade="all, delete-orphan")
    armrests = relationship("Armrest", backref="shelf", cascade="all, delete-orphan")
    trays = relationship("Tray", backref="shelf", cascade="all, delete-orphan")


class Drawer(Base):
    """One scheduled activity within a day."""
    __tablename__ = "drawers"

    id = _uuid_pk()
    shelf_id = _uuid_fk("shelves.id", nullable=False)
    activity_id = _uuid_fk("activities.id")
    name = Column(Text, nullable=False)
    description = Column(Text)
    start_time = Column(Time)
    duration_minutes = Column(Integer)
    sort_order = Column(Integer, nullable=False, default=0)
    activity_type = Column(Text, nullable=False, default="EXPERIENCE")
    location_name = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class Headboard(Base):
    """Accommodation for a night."""
    __tablename__ = "headboards"

    id = _uuid_pk()
    shelf_id = _uuid_fk("shelves.id", nullable=False)
    lodge_id = _uuid_fk("lodges.id")
    name = Column(Text, nullable=False)
    tier = Column(Text)
    check_in = Column(Date)
    check_out = Column(Date)
    nights = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class Armrest(Base):
    """Transport used on a given day."""
    __tablename__ = "armrests"

    id = _uuid_pk()
    shelf_id = _uuid_fk("shelves.id", nullable=False)
    mode = Column(Text, nullable=False)
    description = Column(Text)
    duration_minutes = Column(Integer)
    is_private = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class Tray(Base):
    """Meals included on a given day."""
    __tablename__ = "trays"

    id = _uuid_pk()
    shelf_id = _uuid_fk("shelves.id", nullable=False)
    meal_type = Column(Text, nullable=False)
    included = Column(Boolean, nullable=False, default=True)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Hinge(Base):
    """Route leg between two destinations, trip-level."""
    __tablename__ = "hinges"

    id = _uuid_pk()
    cabinet_id = _uuid_fk("cabinets.id", nullable=False)
    from_destination_id = _uuid_fk("travel_places.id")
    to_destination_id = _uuid_fk("travel_places.id")
    sequence_order = Column(Integer, nullable=False)
    distance_km = Column(Numeric(8, 2))
    duration_minutes = Column(Integer)
    mode = Column(Text)
    source = Column(Text, nullable=False, default="drive_times")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Footstool(Base):
    """Validation engine output / repair log."""
    __tablename__ = "footstools"

    id = _uuid_pk()
    cabinet_id = _uuid_fk("cabinets.id", nullable=False)
    shelf_id = _uuid_fk("shelves.id")
    severity = Column(Text, nullable=False, default="info")
    category = Column(Text, nullable=False)
    message = Column(Text, nullable=False)
    auto_repaired = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Stool(Base):
    """Operator match score for a trip."""
    __tablename__ = "stools"
    __table_args__ = (UniqueConstraint("cabinet_id", "tour_operator_id"),)

    id = _uuid_pk()
    cabinet_id = _uuid_fk("cabinets.id", nullable=False)
    tour_operator_id = _uuid_fk("tour_operators.id", nullable=False)
    trip_match_pct = Column(Integer, nullable=False)
    itinerary_fit_pct = Column(Integer)
    experience_fit_pct = Column(Integer)
    accommodation_fit_pct = Column(Integer)
    destination_coverage_pct = Column(Integer)
    service_pct = Column(Integer)
    trust_pct = Column(Integer)
    value_pct = Column(Integer)
    strengths = Column(ARRAY(Text), nullable=False, default=list)
    badge = Column(Text)
    estimated_price_pp = Column(Numeric(10, 2))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class Bench(Base):
    """A quote request sent to one operator."""
    __tablename__ = "benches"

    id = _uuid_pk()
    cabinet_id = _uuid_fk("cabinets.id", nullable=False)
    tour_operator_id = _uuid_fk("tour_operators.id", nullable=False)
    status = Column(Text, nullable=False, default="request_sent")
    note = Column(Text)
    requested_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    responded_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    counters = relationship("Counter", backref="bench", cascade="all, delete-orphan")


class Counter(Base):
    """The quote an operator sends back for a bench (request)."""
    __tablename__ = "counters"

    id = _uuid_pk()
    bench_id = _uuid_fk("benches.id", nullable=False)
    price_per_person = Column(Numeric(10, 2), nullable=False)
    currency = Column(Text, nullable=False, default="USD")
    validity_date = Column(Date)
    accommodation_summary = Column(Text)
    activities_summary = Column(Text)
    transport_summary = Column(Text)
    meals_summary = Column(Text)
    park_fees_included = Column(Boolean, nullable=False, default=True)
    transfers_included = Column(Boolean, nullable=False, default=True)
    difference_notes = Column(Text)
    status = Column(Text, nullable=False, default="received")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class Wardrobe(Base):
    """A confirmed booking."""
    __tablename__ = "wardrobes"

    id = _uuid_pk()
    cabinet_id = _uuid_fk("cabinets.id", nullable=False)
    counter_id = _uuid_fk("counters.id")
    confirmation_code = Column(Text, nullable=False, unique=True)
    tour_operator_id = _uuid_fk("tour_operators.id", nullable=False)
    price_per_person = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)
    deposit_amount = Column(Numeric(10, 2))
    status = Column(Text, nullable=False, default="reserved")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    chests = relationship("Chest", backref="wardrobe", cascade="all, delete-orphan")


class Chest(Base):
    """A payment against a booking."""
    __tablename__ = "chests"

    id = _uuid_pk()
    wardrobe_id = _uuid_fk("wardrobes.id", nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(Text, nullable=False, default="USD")
    payment_type = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="pending")
    paid_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Mirror(Base):
    """A notification tied to a trip/quote-request/booking."""
    __tablename__ = "mirrors"

    id = _uuid_pk()
    cabinet_id = _uuid_fk("cabinets.id")
    bench_id = _uuid_fk("benches.id")
    wardrobe_id = _uuid_fk("wardrobes.id")
    channel = Column(Text, nullable=False, default="push")
    message = Column(Text, nullable=False)
    sent = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
