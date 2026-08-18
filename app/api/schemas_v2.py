"""Response models — one per screen shown in the screenshots."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    supabase_connected: bool
    legacy_db_connected: bool
    ai_gateway_enabled: bool


class DrawerOut(BaseModel):
    name: str
    description: Optional[str] = None
    start_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    activity_type: str


class DayOut(BaseModel):
    day_number: int
    destination: str
    date: Optional[date] = None
    theme: Optional[str] = None
    activities: list[DrawerOut]
    accommodation: Optional[str] = None
    transport: Optional[str] = None
    meals: list[str] = []


class WhyItineraryFact(BaseModel):
    heading: str
    detail: str


class TripSummaryOut(BaseModel):
    cabinet_id: str
    title: str
    duration_days: int
    travelers: int
    style: list[str]
    dates: dict
    route: list[str]
    estimated_budget: dict
    status: str


class TripDetailOut(BaseModel):
    summary: TripSummaryOut
    days: list[DayOut]
    why_itinerary: list[WhyItineraryFact]


class OperatorMatchOut(BaseModel):
    tour_operator_id: str
    name: str
    trip_match_pct: int
    badge: Optional[str] = None
    strengths: list[str]
    estimated_price_pp: Optional[float] = None


class QuoteTrackingOut(BaseModel):
    requests_sent: int
    quotes_received: int
    awaiting_response: int
    benches: list[dict]


class QuoteComparisonOut(BaseModel):
    quotes: list[dict]
    best_value_bench_id: Optional[str]
    best_fit_bench_id: Optional[str]


class BookingOut(BaseModel):
    confirmation_code: str
    trip_title: str
    operator_name: str
    dates: dict
    travelers: int
    price_per_person: float
    total_price: float
    deposit_amount: Optional[float]
    status: str
