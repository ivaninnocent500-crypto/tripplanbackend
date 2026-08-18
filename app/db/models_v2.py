"""
SQLAlchemy models reflecting the real Supabase PostgreSQL schema. Only
the tables the five migrated engines actually touch are modeled here.
See MIGRATION_NOTES.md for what's NOT yet modeled/populated.
"""
from __future__ import annotations

import uuid
from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, Text, ForeignKey,
    DateTime, ARRAY, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from geoalchemy2 import Geography

Base = declarative_base()


def gen_uuid():
    return str(uuid.uuid4())


destination_type_enum = ENUM(
    'national_park', 'game_reserve', 'island', 'beach', 'mountain',
    'city', 'cultural_site', 'unesco_site', 'lake', 'desert',
    'waterfall', 'marine_park', 'forest_reserve', 'wetland',
    name='destination_type', create_type=False
)

lodge_tier_enum = ENUM(
    'ultra_luxury', 'luxury', 'mid_range', 'budget', 'camping',
    name='lodge_tier', create_type=False
)

activity_category_enum = ENUM(
    'game_drive', 'walking_safari', 'boat_safari', 'balloon_safari', 'birding',
    'photography', 'cultural_visit', 'hiking', 'diving', 'snorkeling',
    'fishing', 'beach_leisure', 'mountain_climbing', 'canoeing', 'horseback_safari',
    'night_drive', 'cycling', 'camping', 'shopping', 'spa_wellness',
    name='activity_category', create_type=False
)

operator_verification_status_enum = ENUM(
    'verified', 'pending_verification', 'unverified', 'suspended',
    name='operator_verification_status', create_type=False
)

fee_payer_category_enum = ENUM(
    'foreign_non_resident', 'foreign_resident', 'east_african_citizen',
    'local_citizen', 'child', 'student', 'vehicle', 'conservation_fee',
    name='fee_payer_category', create_type=False
)

month_enum = ENUM(
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
    name='month_enum', create_type=False
)


class TravelPlace(Base):
    __tablename__ = "travel_places"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(Text, nullable=False)
    slug = Column(Text, nullable=False, unique=True)
    destination_type = Column(destination_type_enum, nullable=False)
    country = Column(Text, nullable=False)
    region = Column(Text)
    short_description = Column(Text)
    long_description = Column(Text)
    is_published = Column(Boolean, nullable=False, default=False)
    popularity_rank = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    geography = relationship("PhysicalGeography", back_populates="destination", uselist=False)
    lodges = relationship("Lodge", back_populates="destination")
    activities = relationship("Activity", back_populates="destination")


class PhysicalGeography(Base):
    __tablename__ = "physical_geography"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    destination_id = Column(UUID(as_uuid=False), ForeignKey("travel_places.id", ondelete="CASCADE"), nullable=False, unique=True)
    centroid = Column(Geography(geometry_type="POINT", srid=4326))
    nearest_city = Column(Text)
    distance_from_capital_km = Column(Numeric(8, 2))

    destination = relationship("TravelPlace", back_populates="geography")


class Lodge(Base):
    __tablename__ = "lodges"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    destination_id = Column(UUID(as_uuid=False), ForeignKey("travel_places.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    tier = Column(lodge_tier_enum, nullable=False)
    price_per_night_usd_low = Column(Numeric(10, 2))
    price_per_night_usd_high = Column(Numeric(10, 2))
    is_family_friendly = Column(Boolean, nullable=False, default=False)
    wheelchair_accessible = Column(Boolean, nullable=False, default=False)
    star_rating = Column(Numeric(2, 1))

    destination = relationship("TravelPlace", back_populates="lodges")


class Activity(Base):
    __tablename__ = "activities"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    destination_id = Column(UUID(as_uuid=False), ForeignKey("travel_places.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    category = Column(activity_category_enum, nullable=False)
    description = Column(Text)
    typical_price_usd = Column(Numeric(10, 2))
    available_months = Column(ARRAY(month_enum))

    destination = relationship("TravelPlace", back_populates="activities")


class EstimatedVisitDuration(Base):
    __tablename__ = "estimated_visit_durations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    destination_id = Column(UUID(as_uuid=False), ForeignKey("travel_places.id", ondelete="CASCADE"), nullable=False)
    scope = Column(Text, nullable=False)
    recommended_nights_min = Column(Integer)
    recommended_nights_max = Column(Integer)


class DriveTime(Base):
    __tablename__ = "drive_times"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    destination_id = Column(UUID(as_uuid=False), ForeignKey("travel_places.id", ondelete="CASCADE"), nullable=False)
    origin_name = Column(Text, nullable=False)
    destination_name = Column(Text, nullable=False)
    distance_km = Column(Numeric(8, 2), nullable=False)
    duration_minutes_dry_season = Column(Integer, nullable=False)
    duration_minutes_wet_season = Column(Integer)
    four_wd_required = Column(Boolean, nullable=False, default=False)


class Airport(Base):
    __tablename__ = "airports"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(Text, nullable=False)
    iata_code = Column(Text, unique=True)
    city = Column(Text)


class DestinationAirport(Base):
    __tablename__ = "destination_airports"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    destination_id = Column(UUID(as_uuid=False), ForeignKey("travel_places.id", ondelete="CASCADE"), nullable=False)
    airport_id = Column(UUID(as_uuid=False), ForeignKey("airports.id", ondelete="CASCADE"), nullable=False)
    distance_km = Column(Numeric(8, 2))
    typical_transfer_minutes = Column(Integer)
    is_primary_gateway = Column(Boolean, nullable=False, default=False)


class Wildlife(Base):
    __tablename__ = "wildlife"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    common_name = Column(Text, nullable=False)
    scientific_name = Column(Text, nullable=False, unique=True)
    is_big_five = Column(Boolean, nullable=False, default=False)


class DestinationWildlife(Base):
    __tablename__ = "destination_wildlife"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    destination_id = Column(UUID(as_uuid=False), ForeignKey("travel_places.id", ondelete="CASCADE"), nullable=False)
    wildlife_id = Column(UUID(as_uuid=False), ForeignKey("wildlife.id", ondelete="CASCADE"), nullable=False)
    sighting_probability_pct = Column(Integer, CheckConstraint("sighting_probability_pct between 0 and 100"))


class WildlifeCalendarEntry(Base):
    __tablename__ = "wildlife_calendar"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    destination_id = Column(UUID(as_uuid=False), ForeignKey("travel_places.id", ondelete="CASCADE"), nullable=False)
    wildlife_id = Column(UUID(as_uuid=False), ForeignKey("wildlife.id", ondelete="CASCADE"), nullable=False)
    month = Column(month_enum, nullable=False)
    sighting_probability_pct = Column(Integer, CheckConstraint("sighting_probability_pct between 0 and 100"))

    wildlife = relationship("Wildlife")


class TourOperator(Base):
    __tablename__ = "tour_operators"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(Text, nullable=False)
    verification_status = Column(operator_verification_status_enum, nullable=False, default="unverified")
    years_in_operation = Column(Integer)
    rating = Column(Numeric(2, 1))
    review_count = Column(Integer, default=0)
    contact_phone = Column(Text)
    contact_email = Column(Text)


class DestinationTourOperator(Base):
    __tablename__ = "destination_tour_operators"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    destination_id = Column(UUID(as_uuid=False), ForeignKey("travel_places.id", ondelete="CASCADE"), nullable=False)
    tour_operator_id = Column(UUID(as_uuid=False), ForeignKey("tour_operators.id", ondelete="CASCADE"), nullable=False)


class EntryFee(Base):
    __tablename__ = "entry_fees"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    destination_id = Column(UUID(as_uuid=False), ForeignKey("travel_places.id", ondelete="CASCADE"), nullable=False)
    payer_category = Column(fee_payer_category_enum, nullable=False)
    fee_amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(Text, nullable=False, default="USD")
