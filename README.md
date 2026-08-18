# Africa Travel OS Backend (v2 — deterministic architecture)

Every trip is a persisted database record (a `Cabinet`), not a one-off
computed response. `/api/trips/*` is the entire backend contract — one
endpoint per app screen, in the order the screens appear.

## What changed from v1

The old `TripOrchestrator` + 9 engines (`ItineraryEngine`, `OperatorEngine`,
`WeatherEngine`, `WildlifeEngine`, `RoutingEngine`, `BudgetEngine`,
`PackingEngine`, `ConfidenceEngine`, `AIInsightEngine`) computed a trip in
memory per-request and discarded it. That's gone. In its place:

- **`cabinets`** and friends (`shelves`, `drawers`, `headboards`,
  `armrests`, `trays`, `hinges`) — a persisted trip, day-by-day, with a
  permanent Trip ID. See `schema/002_furniture_schema.sql` for the full
  table map.
- **`ItineraryPlanningEngine`** builds it deterministically from
  `travel_places` / `activities` / `lodges` / `drive_times` — no AI in
  the critical path.
- **`ValidationEngine`** checks it's physically possible (no time
  overlaps, transfers that fit, every night has a bed) before it's
  marked `ready`.
- **`ExplanationEngine`** produces "Why this itinerary?" from the
  persisted facts only.
- **`OperatorMatchEngine`**, **`QuoteEngine`**, **`BookingEngine`** carry
  the trip through matching → quotes → booking, each step persisted
  (`stools`, `benches`/`counters`, `wardrobes`/`chests`).

`RulesEngine` and `call_engine()` (resilience wrapping) are kept from v1
and used the same way — each engine call degrades gracefully instead of
crashing the request.

## Setup

1. **Database** — run against Supabase in order:
   ```
   schema/001_knowledge_base_schema.sql
   schema/002_furniture_schema.sql
   schema/002_furniture_seed.sql   # optional — demo data only, staging/dev
   ```
2. **Environment** — copy `.env.example` to `.env` and fill in
   `SUPABASE_DATABASE_URL` and `ATI_API_KEY`.
3. **Install & run locally**:
   ```
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```
4. **Deploy** — push this repo to GitHub, connect to Render. `render.yaml`
   is included; Render will pick up the build/start commands automatically,
   or set them manually in the dashboard:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

   Set `SUPABASE_DATABASE_URL` and `ATI_API_KEY` as Render environment
   variables (never commit them).

## Endpoint contract (one per screen)

| Screen | Endpoint |
|---|---|
| Generate itinerary | `POST /api/trips/generate` |
| Day-by-day view / Why this itinerary | `GET /api/trips/{cabinet_id}` |
| Choose your safari partner | `POST /api/trips/{cabinet_id}/match-operators` |
| Get your safari quotes | `POST /api/trips/{cabinet_id}/quotes/request` |
| Your safari quotes (tracking) | `GET /api/trips/{cabinet_id}/quotes` |
| Compare your quotes | `GET /api/trips/{cabinet_id}/quotes/compare` |
| Your safari is ready | `POST /api/trips/{cabinet_id}/book` |
| Booking confirmed | `POST /api/trips/bookings/{wardrobe_id}/confirm` |
| Render health check | `GET /api/health` (unauthenticated) |

All routes except `/api/health` require an `X-Api-Key` header matching
`ATI_API_KEY`.

## File provenance — read this before overwriting your repo

Every file in this zip falls into one of two categories:

**Verbatim — exact reproductions of what you pasted, safe to overwrite:**
`app/api/auth.py`, `app/db/session.py`, `app/db/destinations.py`,
`app/db/models_v2.py`, `app/engines/rules.py`, `app/engines/resilience.py`,
`app/ai/gateway.py`, `schema/001_knowledge_base_schema.sql`.

**New — the v2 architecture, safe to add (nothing to conflict with):**
`app/db/models_furniture.py`, `app/engines/itinerary_v2.py`,
`app/engines/validation.py`, `app/engines/explanation.py`,
`app/engines/operator_match_v2.py`, `app/engines/quote_engine.py`,
`app/engines/booking_engine.py`, `app/api/schemas_v2.py`,
`app/api/trip_v2.py`, `app/api/health.py`, `app/main.py`,
`schema/002_furniture_schema.sql`, `schema/002_furniture_seed.sql`.

**Removed, not reconstructed:** the old `app/core/orchestrator.py`,
`app/api/trip.py`, `app/api/schemas.py`, `app/db/models.py`
(`GenerationLog`), and the 9 engines the old orchestrator called
(`itinerary.py`, `operator.py`, `packing.py`, `budget.py`, `weather.py`,
`wildlife.py`, `routing.py`, `confidence.py`, `insights.py`). You
confirmed the new architecture doesn't need them — they're deleted here,
not stubbed. If your real repo still has them, delete them there too, or
keep them dormant (unimported) if you want to preserve the code for
reference.

## Known gaps (carried over from prior delivery)

1. **Gateway cities** (Arusha, Nairobi, Kigali, ...) aren't seeded in
   `travel_places` yet — only the demo Arusha row in the seed file exists.
   Add these per country before running real trips.
2. **Real pricing data** — `stools.value_pct` / `estimated_price_pp` in
   `OperatorMatchEngine` are placeholders; no lodge/activity rate-card
   feed exists yet to compute a real per-operator estimate.
3. **No network access from this environment** — these files were never
   pushed to GitHub or deployed to Render from here. You'll need to
   commit and push them yourself.
