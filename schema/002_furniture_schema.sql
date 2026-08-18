-- =====================================================================
-- AFRICA TRAVEL OS — TRIP INSTANCE LAYER ("Furniture Schema")
-- =====================================================================
-- Why this exists:
-- Your Section 1-8 schema (travel_places, activities, lodges,
-- tour_operators, drive_times, wildlife_calendar, ...) is a KNOWLEDGE
-- BASE. It has no table that represents "a specific trip we built for
-- a specific user" — no Trip ID, no persisted Day 1 / Day 2 rows, no
-- record of which operators were matched, no quote history, no booking.
-- That is why the current backend can't back the screens in the app:
-- there is nowhere for a generated itinerary to live after the request
-- finishes. This file adds that layer.
--
-- Naming: every table below uses a furniture noun instead of the
-- obvious name (trips, trip_days, trip_activities, ...) per your
-- instruction, so nothing collides with the existing schema or with
-- whatever ORM models already reference `travel_places`/`activities`
-- by name in your current code.
--
--   Concept                        -> Table
--   -------                           -----
--   Trip                           -> cabinets
--   Trip day                       -> shelves
--   Day activity                   -> drawers
--   Night's accommodation          -> headboards
--   Day's transport                -> armrests
--   Day's meals                    -> trays
--   Route leg between destinations -> hinges
--   Validation issue / repair log  -> footstools
--   Operator match score           -> stools
--   Quote request                  -> benches
--   Received quote                 -> counters
--   Confirmed booking              -> wardrobes
--   Payment record                 -> chests
--   Notification                  -> mirrors
--
-- Every table hangs off `cabinets` (directly or via `shelves`/`benches`)
-- with ON DELETE CASCADE, same convention as your travel_places graph.
-- Run AFTER 001 (your existing schema) — this file only adds tables,
-- it does not modify anything in Sections 1-8.
-- =====================================================================

-- ---------------------------------------------------------------------
-- CABINETS = a generated trip
-- ---------------------------------------------------------------------
create table cabinets (
  id uuid primary key default gen_random_uuid(),
  request_json jsonb not null,                 -- original TripRequest, for audit/replay
  title text not null,                          -- "Tanzania, Wild & Unhurried"
  duration_days integer not null,
  travelers_adults integer not null default 1,
  travelers_children integer not null default 0,
  travel_style text[] not null default '{}',    -- e.g. {wildlife,luxury,private,relaxed_pace}
  budget_tier text,
  status text not null default 'draft'
    check (status in ('draft','ready','matching','quoting','booked','confirmed','cancelled')),
  start_date date,
  end_date date,
  estimated_budget_low numeric(10,2),
  estimated_budget_high numeric(10,2),
  currency text not null default 'USD',
  primary_destination_id uuid references travel_places(id),
  route_destination_ids uuid[] not null default '{}',   -- ordered route
  confidence_score integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_cabinets_status on cabinets(status);
create index idx_cabinets_primary_destination on cabinets(primary_destination_id);

create trigger trg_cabinets_updated_at
  before update on cabinets for each row execute function set_updated_at();

-- ---------------------------------------------------------------------
-- SHELVES = one day of a trip
-- ---------------------------------------------------------------------
create table shelves (
  id uuid primary key default gen_random_uuid(),
  cabinet_id uuid not null references cabinets(id) on delete cascade,
  day_number integer not null,
  date date,
  destination_id uuid references travel_places(id),
  theme text,                                    -- "Arrival & slow start"
  hero_image_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (cabinet_id, day_number)
);

create index idx_shelves_cabinet on shelves(cabinet_id);
create index idx_shelves_destination on shelves(destination_id);

create trigger trg_shelves_updated_at
  before update on shelves for each row execute function set_updated_at();

-- ---------------------------------------------------------------------
-- DRAWERS = one scheduled activity within a day
-- ---------------------------------------------------------------------
create table drawers (
  id uuid primary key default gen_random_uuid(),
  shelf_id uuid not null references shelves(id) on delete cascade,
  activity_id uuid references activities(id),    -- link back to knowledge base, nullable (e.g. "Airport welcome" has none)
  name text not null,
  description text,
  start_time time,
  duration_minutes integer,
  sort_order integer not null default 0,
  activity_type text not null default 'EXPERIENCE'
    check (activity_type in ('ARRIVAL','EXPERIENCE','MEAL','TRANSFER','DEPARTURE','FREE_TIME')),
  location_name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_drawers_shelf on drawers(shelf_id);
create index idx_drawers_activity on drawers(activity_id);
create index idx_drawers_sort on drawers(shelf_id, sort_order);

create trigger trg_drawers_updated_at
  before update on drawers for each row execute function set_updated_at();

-- ---------------------------------------------------------------------
-- HEADBOARDS = accommodation for a given night/day
-- ---------------------------------------------------------------------
create table headboards (
  id uuid primary key default gen_random_uuid(),
  shelf_id uuid not null references shelves(id) on delete cascade,
  lodge_id uuid references lodges(id),
  name text not null,
  tier text,
  check_in date,
  check_out date,
  nights integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_headboards_shelf on headboards(shelf_id);
create index idx_headboards_lodge on headboards(lodge_id);

create trigger trg_headboards_updated_at
  before update on headboards for each row execute function set_updated_at();

-- ---------------------------------------------------------------------
-- ARMRESTS = transport used on a given day
-- ---------------------------------------------------------------------
create table armrests (
  id uuid primary key default gen_random_uuid(),
  shelf_id uuid not null references shelves(id) on delete cascade,
  mode text not null,                            -- private_4x4, scheduled_flight, charter_flight, ferry, walking
  description text,                              -- "Private 4x4 · 55 min transfer"
  duration_minutes integer,
  is_private boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_armrests_shelf on armrests(shelf_id);

create trigger trg_armrests_updated_at
  before update on armrests for each row execute function set_updated_at();

-- ---------------------------------------------------------------------
-- TRAYS = meals included on a given day
-- ---------------------------------------------------------------------
create table trays (
  id uuid primary key default gen_random_uuid(),
  shelf_id uuid not null references shelves(id) on delete cascade,
  meal_type text not null check (meal_type in ('breakfast','lunch','dinner','snack')),
  included boolean not null default true,
  notes text,
  created_at timestamptz not null default now()
);

create index idx_trays_shelf on trays(shelf_id);

-- ---------------------------------------------------------------------
-- HINGES = route legs between destinations, trip-level (backs RoutingEngine)
-- ---------------------------------------------------------------------
create table hinges (
  id uuid primary key default gen_random_uuid(),
  cabinet_id uuid not null references cabinets(id) on delete cascade,
  from_destination_id uuid references travel_places(id),
  to_destination_id uuid references travel_places(id),
  sequence_order integer not null,
  distance_km numeric(8,2),
  duration_minutes integer,
  mode text,
  source text not null default 'drive_times',    -- 'drive_times' | 'fallback_estimate'
  created_at timestamptz not null default now()
);

create index idx_hinges_cabinet on hinges(cabinet_id, sequence_order);

-- ---------------------------------------------------------------------
-- FOOTSTOOLS = validation engine output/repair log for a cabinet
-- ---------------------------------------------------------------------
create table footstools (
  id uuid primary key default gen_random_uuid(),
  cabinet_id uuid not null references cabinets(id) on delete cascade,
  shelf_id uuid references shelves(id) on delete cascade,
  severity text not null default 'info' check (severity in ('info','warning','error')),
  category text not null,                        -- time | geography | duration | accommodation | transport | preferences
  message text not null,
  auto_repaired boolean not null default false,
  created_at timestamptz not null default now()
);

create index idx_footstools_cabinet on footstools(cabinet_id);
create index idx_footstools_severity on footstools(severity);

-- ---------------------------------------------------------------------
-- STOOLS = operator match scores for a cabinet ("Choose your safari partner")
-- ---------------------------------------------------------------------
create table stools (
  id uuid primary key default gen_random_uuid(),
  cabinet_id uuid not null references cabinets(id) on delete cascade,
  tour_operator_id uuid not null references tour_operators(id) on delete cascade,
  trip_match_pct integer not null check (trip_match_pct between 0 and 100),
  itinerary_fit_pct integer check (itinerary_fit_pct between 0 and 100),
  experience_fit_pct integer check (experience_fit_pct between 0 and 100),
  accommodation_fit_pct integer check (accommodation_fit_pct between 0 and 100),
  destination_coverage_pct integer check (destination_coverage_pct between 0 and 100),
  service_pct integer check (service_pct between 0 and 100),
  trust_pct integer check (trust_pct between 0 and 100),
  value_pct integer check (value_pct between 0 and 100),
  strengths text[] not null default '{}',
  badge text,                                     -- strongest_match | best_premium_experience | best_value
  estimated_price_pp numeric(10,2),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (cabinet_id, tour_operator_id)
);

create index idx_stools_cabinet on stools(cabinet_id, trip_match_pct desc);

create trigger trg_stools_updated_at
  before update on stools for each row execute function set_updated_at();

-- ---------------------------------------------------------------------
-- BENCHES = a quote request sent to one operator ("Get your safari quotes")
-- ---------------------------------------------------------------------
create table benches (
  id uuid primary key default gen_random_uuid(),
  cabinet_id uuid not null references cabinets(id) on delete cascade,
  tour_operator_id uuid not null references tour_operators(id) on delete cascade,
  status text not null default 'request_sent'
    check (status in ('request_sent','operator_reviewing','quote_received','expired','declined')),
  note text,
  requested_at timestamptz not null default now(),
  responded_at timestamptz,
  updated_at timestamptz not null default now()
);

create index idx_benches_cabinet on benches(cabinet_id);
create index idx_benches_status on benches(status);

create trigger trg_benches_updated_at
  before update on benches for each row execute function set_updated_at();

-- ---------------------------------------------------------------------
-- COUNTERS = the actual quote an operator sends back ("Compare your quotes")
-- ---------------------------------------------------------------------
create table counters (
  id uuid primary key default gen_random_uuid(),
  bench_id uuid not null references benches(id) on delete cascade,
  price_per_person numeric(10,2) not null,
  currency text not null default 'USD',
  validity_date date,
  accommodation_summary text,
  activities_summary text,
  transport_summary text,
  meals_summary text,
  park_fees_included boolean not null default true,
  transfers_included boolean not null default true,
  difference_notes text,                          -- "Two lodge upgrades" / "One night outside the park"
  status text not null default 'received' check (status in ('received','accepted','declined','expired')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_counters_bench on counters(bench_id);

create trigger trg_counters_updated_at
  before update on counters for each row execute function set_updated_at();

-- ---------------------------------------------------------------------
-- WARDROBES = a confirmed booking
-- ---------------------------------------------------------------------
create table wardrobes (
  id uuid primary key default gen_random_uuid(),
  cabinet_id uuid not null references cabinets(id) on delete cascade,
  counter_id uuid references counters(id),
  confirmation_code text not null unique,          -- "ATO-TZ-249381"
  tour_operator_id uuid not null references tour_operators(id),
  price_per_person numeric(10,2) not null,
  total_price numeric(10,2) not null,
  deposit_amount numeric(10,2),
  status text not null default 'reserved' check (status in ('reserved','confirmed','cancelled')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_wardrobes_cabinet on wardrobes(cabinet_id);
create index idx_wardrobes_code on wardrobes(confirmation_code);

create trigger trg_wardrobes_updated_at
  before update on wardrobes for each row execute function set_updated_at();

-- ---------------------------------------------------------------------
-- CHESTS = payments against a booking
-- ---------------------------------------------------------------------
create table chests (
  id uuid primary key default gen_random_uuid(),
  wardrobe_id uuid not null references wardrobes(id) on delete cascade,
  amount numeric(10,2) not null,
  currency text not null default 'USD',
  payment_type text not null check (payment_type in ('deposit','balance','full','refund')),
  status text not null default 'pending' check (status in ('pending','completed','failed','refunded')),
  paid_at timestamptz,
  created_at timestamptz not null default now()
);

create index idx_chests_wardrobe on chests(wardrobe_id);

-- ---------------------------------------------------------------------
-- MIRRORS = notifications ("we follow up with operators for you")
-- ---------------------------------------------------------------------
create table mirrors (
  id uuid primary key default gen_random_uuid(),
  cabinet_id uuid references cabinets(id) on delete cascade,
  bench_id uuid references benches(id) on delete cascade,
  wardrobe_id uuid references wardrobes(id) on delete cascade,
  channel text not null default 'push' check (channel in ('push','email','sms')),
  message text not null,
  sent boolean not null default false,
  created_at timestamptz not null default now()
);

create index idx_mirrors_cabinet on mirrors(cabinet_id);
