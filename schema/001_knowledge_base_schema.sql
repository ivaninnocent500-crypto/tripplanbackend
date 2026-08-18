
-- =====================================================================
-- AFRICA TRAVEL INTELLIGENCE PLATFORM
-- Production-Grade Supabase PostgreSQL Schema
-- =====================================================================
-- Purpose:
-- Permanent, AI-independent knowledge base powering non-AI-generated,
-- data-driven itinerary construction across 25+ African destinations
-- (national parks, islands, beaches, mountains, cities, cultural and
-- UNESCO sites).
--
-- Run this file top-to-bottom in the Supabase SQL Editor, BEFORE
-- 002_furniture_schema.sql. Reproduced verbatim from the original.
-- =====================================================================

create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";
create extension if not exists postgis;
create extension if not exists pg_trgm;

create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create type destination_type as enum (
  'national_park', 'game_reserve', 'island', 'beach', 'mountain',
  'city', 'cultural_site', 'unesco_site', 'lake', 'desert',
  'waterfall', 'marine_park', 'forest_reserve', 'wetland'
);

create type country_code as enum (
  'KE','TZ','UG','RW','ZA','NA','BW','ZW','ZM','MZ','MW','ET','MG',
  'SC','MU','TN','MA','EG','GH','SN','CI','NG','GA','CD','CM','BI',
  'SS','DJ','ER','SO','AO','LS','SZ','CV','ST','GM','GW','SL','LR',
  'BF','ML','NE','TD','CF','CG','GQ','TG','BJ','MR','DZ','LY','SD',
  'EH','KM'
);

create type season_type as enum ('dry', 'wet', 'shoulder', 'green', 'peak');
create type road_surface as enum ('tarmac','gravel','dirt','sand','seasonal_4x4_only','impassable_wet_season');
create type gate_status as enum ('open','closed','seasonal','permit_required');
create type airstrip_surface as enum ('tarmac','murram','grass','gravel');
create type flight_type as enum ('scheduled_commercial','charter','light_aircraft_shuttle');
create type ferry_frequency as enum ('daily','weekly','seasonal','on_demand');
create type border_status as enum ('open','closed','restricted','visa_on_arrival','e_visa_required');
create type wildlife_category as enum ('mammal','bird','reptile','amphibian','fish','insect','marine');

create type conservation_status as enum (
  'least_concern','near_threatened','vulnerable','endangered',
  'critically_endangered','extinct_in_wild','data_deficient','not_evaluated'
);

create type activity_category as enum (
  'game_drive','walking_safari','boat_safari','balloon_safari','birding',
  'photography','cultural_visit','hiking','diving','snorkeling',
  'fishing','beach_leisure','mountain_climbing','canoeing','horseback_safari',
  'night_drive','cycling','camping','shopping','spa_wellness'
);

create type difficulty_level as enum ('easy','moderate','challenging','strenuous','expert_only');
create type lodge_tier as enum ('ultra_luxury','luxury','mid_range','budget','camping');
create type meal_plan as enum ('all_inclusive','full_board','half_board','bed_breakfast','self_catering','no_meals');
create type accessibility_level as enum ('fully_accessible','partially_accessible','not_accessible','accessible_with_assistance');
create type suitability_rating as enum ('excellent','good','fair','not_recommended');
create type adventure_scale as enum ('low','moderate','high','extreme');
create type internet_quality as enum ('none','poor','moderate','good','excellent','wifi_available','starlink_available');
create type electricity_type as enum ('none','solar','generator','grid','generator_limited_hours','solar_and_generator');
create type water_source as enum ('none','borehole','piped_treated','bottled_only','river_untreated','rainwater_harvested');
create type fee_currency as enum ('USD','EUR','GBP','local_currency');
create type fee_payer_category as enum ('foreign_non_resident','foreign_resident','east_african_citizen','local_citizen','child','student','vehicle','conservation_fee');
create type guide_certification as enum ('bronze','silver','gold','platinum','uncertified','government_licensed');
create type operator_verification_status as enum ('verified','pending_verification','unverified','suspended');

create type month_enum as enum (
  'january','february','march','april','may','june',
  'july','august','september','october','november','december'
);

create type rainfall_intensity as enum ('none','light','moderate','heavy','torrential');

create type migration_phase as enum (
  'calving','rutting','river_crossing_north','river_crossing_south',
  'dispersal','congregation','resting','not_present'
);

create type faq_category as enum (
  'general','safety','packing','visa','health','budget','wildlife',
  'weather','transport','accommodation','activities','culture'
);

create table travel_places (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  destination_type destination_type not null,
  country country_code not null,
  region text,
  short_description text,
  long_description text,
  established_year integer,
  total_area_sq_km numeric(12,2),
  unesco_listed boolean not null default false,
  unesco_listing_year integer,
  timezone text not null default 'Africa/Nairobi',
  official_website text,
  is_published boolean not null default false,
  popularity_rank integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_travel_places_type on travel_places(destination_type);
create index idx_travel_places_country on travel_places(country);
create index idx_travel_places_slug on travel_places(slug);
create index idx_travel_places_unesco on travel_places(unesco_listed) where unesco_listed = true;
create index idx_travel_places_name_trgm on travel_places using gin (name gin_trgm_ops);

create trigger trg_travel_places_updated_at
  before update on travel_places
  for each row execute function set_updated_at();

create table physical_geography (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  centroid geography(Point, 4326),
  boundary geography(Polygon, 4326),
  min_altitude_m integer,
  max_altitude_m integer,
  avg_altitude_m integer,
  terrain_description text,
  ecosystem_type text,
  biome text,
  major_rivers text[],
  major_lakes text[],
  soil_type text,
  vegetation_type text,
  nearest_city text,
  distance_from_capital_km numeric(8,2),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (destination_id)
);

create index idx_physical_geography_destination on physical_geography(destination_id);
create index idx_physical_geography_centroid on physical_geography using gist (centroid);
create index idx_physical_geography_boundary on physical_geography using gist (boundary);

create trigger trg_physical_geography_updated_at
  before update on physical_geography
  for each row execute function set_updated_at();

create table park_gates (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  name text not null,
  location geography(Point, 4326),
  status gate_status not null default 'open',
  opening_time time,
  closing_time time,
  is_24_hour boolean not null default false,
  permit_required boolean not null default false,
  permit_details text,
  nearest_town text,
  distance_from_nearest_town_km numeric(8,2),
  gps_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_park_gates_destination on park_gates(destination_id);
create index idx_park_gates_location on park_gates using gist (location);

create trigger trg_park_gates_updated_at
  before update on park_gates
  for each row execute function set_updated_at();

create table internal_roads (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  name text not null,
  route_geom geography(LineString, 4326),
  surface road_surface not null default 'dirt',
  length_km numeric(8,2),
  four_wd_required boolean not null default false,
  seasonal_closure boolean not null default false,
  closure_months month_enum[],
  condition_notes text,
  connects_from text,
  connects_to text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_internal_roads_destination on internal_roads(destination_id);
create index idx_internal_roads_geom on internal_roads using gist (route_geom);

create trigger trg_internal_roads_updated_at
  before update on internal_roads
  for each row execute function set_updated_at();

create table drive_times (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  origin_name text not null,
  origin_location geography(Point, 4326),
  destination_name text not null,
  destination_location geography(Point, 4326),
  distance_km numeric(8,2) not null,
  duration_minutes_dry_season integer not null,
  duration_minutes_wet_season integer,
  four_wd_required boolean not null default false,
  route_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_drive_times_destination on drive_times(destination_id);
create index idx_drive_times_origin on drive_times using gist (origin_location);
create index idx_drive_times_destination_loc on drive_times using gist (destination_location);

create trigger trg_drive_times_updated_at
  before update on drive_times
  for each row execute function set_updated_at();

create table airports (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  iata_code text unique,
  icao_code text unique,
  country country_code not null,
  city text,
  location geography(Point, 4326),
  is_international boolean not null default false,
  elevation_m integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_airports_country on airports(country);
create index idx_airports_location on airports using gist (location);
create index idx_airports_iata on airports(iata_code);

create trigger trg_airports_updated_at
  before update on airports
  for each row execute function set_updated_at();

create table destination_airports (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  airport_id uuid not null references airports(id) on delete cascade,
  distance_km numeric(8,2),
  typical_transfer_minutes integer,
  is_primary_gateway boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (destination_id, airport_id)
);

create index idx_dest_airports_destination on destination_airports(destination_id);
create index idx_dest_airports_airport on destination_airports(airport_id);

create trigger trg_destination_airports_updated_at
  before update on destination_airports
  for each row execute function set_updated_at();

create table airstrips (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  name text not null,
  location geography(Point, 4326),
  surface airstrip_surface not null default 'murram',
  length_m integer,
  elevation_m integer,
  night_landing boolean not null default false,
  operating_hours text,
  serves_lodges text[],
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_airstrips_destination on airstrips(destination_id);
create index idx_airstrips_location on airstrips using gist (location);

create trigger trg_airstrips_updated_at
  before update on airstrips
  for each row execute function set_updated_at();

create table flights (
  id uuid primary key default gen_random_uuid(),
  flight_type flight_type not null,
  operator_name text not null,
  origin_airport_id uuid references airports(id) on delete set null,
  origin_airstrip_id uuid references airstrips(id) on delete set null,
  destination_airport_id uuid references airports(id) on delete set null,
  destination_airstrip_id uuid references airstrips(id) on delete set null,
  frequency text,
  duration_minutes integer,
  typical_price_usd numeric(10,2),
  seasonal boolean not null default false,
  operating_months month_enum[],
  booking_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint chk_flight_origin check (
    (origin_airport_id is not null)::int + (origin_airstrip_id is not null)::int = 1
  ),
  constraint chk_flight_destination check (
    (destination_airport_id is not null)::int + (destination_airstrip_id is not null)::int = 1
  )
);

create index idx_flights_origin_airport on flights(origin_airport_id);
create index idx_flights_origin_airstrip on flights(origin_airstrip_id);
create index idx_flights_dest_airport on flights(destination_airport_id);
create index idx_flights_dest_airstrip on flights(destination_airstrip_id);

create trigger trg_flights_updated_at
  before update on flights
  for each row execute function set_updated_at();

create table ferry_routes (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  operator_name text,
  origin_destination_id uuid references travel_places(id) on delete set null,
  destination_destination_id uuid references travel_places(id) on delete set null,
  origin_port_name text not null,
  destination_port_name text not null,
  origin_location geography(Point, 4326),
  destination_location geography(Point, 4326),
  frequency ferry_frequency not null default 'daily',
  duration_minutes integer,
  typical_price_usd numeric(10,2),
  carries_vehicles boolean not null default false,
  seasonal_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_ferry_origin_dest on ferry_routes(origin_destination_id);
create index idx_ferry_destination_dest on ferry_routes(destination_destination_id);
create index idx_ferry_origin_loc on ferry_routes using gist (origin_location);
create index idx_ferry_dest_loc on ferry_routes using gist (destination_location);

create trigger trg_ferry_routes_updated_at
  before update on ferry_routes
  for each row execute function set_updated_at();

create table border_crossings (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  country_a country_code not null,
  country_b country_code not null,
  location geography(Point, 4326),
  status border_status not null default 'open',
  opening_time time,
  closing_time time,
  is_24_hour boolean not null default false,
  visa_notes text,
  nearest_destination_id uuid references travel_places(id) on delete set null,
  distance_from_destination_km numeric(8,2),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_border_crossings_countries on border_crossings(country_a, country_b);
create index idx_border_crossings_location on border_crossings using gist (location);
create index idx_border_crossings_destination on border_crossings(nearest_destination_id);

create trigger trg_border_crossings_updated_at
  before update on border_crossings
  for each row execute function set_updated_at();

create table seasons (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  season_type season_type not null,
  name text not null,
  start_month month_enum not null,
  end_month month_enum not null,
  description text,
  crowd_level text,
  price_level text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_seasons_destination on seasons(destination_id);
create index idx_seasons_type on seasons(season_type);

create trigger trg_seasons_updated_at
  before update on seasons
  for each row execute function set_updated_at();

create table monthly_weather_patterns (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  month month_enum not null,
  avg_high_temp_c numeric(4,1),
  avg_low_temp_c numeric(4,1),
  avg_rainfall_mm numeric(6,1),
  rainfall_intensity rainfall_intensity not null default 'moderate',
  rainy_days_count integer,
  avg_humidity_pct integer,
  sunrise_time time,
  sunset_time time,
  daylight_hours numeric(4,2),
  wind_notes text,
  is_best_month boolean not null default false,
  is_worst_month boolean not null default false,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (destination_id, month)
);

create index idx_monthly_weather_destination on monthly_weather_patterns(destination_id);
create index idx_monthly_weather_month on monthly_weather_patterns(month);
create index idx_monthly_weather_best on monthly_weather_patterns(destination_id) where is_best_month = true;
create index idx_monthly_weather_worst on monthly_weather_patterns(destination_id) where is_worst_month = true;

create trigger trg_monthly_weather_updated_at
  before update on monthly_weather_patterns
  for each row execute function set_updated_at();

create table rainfall_patterns (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  month month_enum not null,
  avg_rainfall_mm numeric(6,1) not null,
  historical_min_mm numeric(6,1),
  historical_max_mm numeric(6,1),
  trend_notes text,
  flooding_risk boolean not null default false,
  road_impact_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (destination_id, month)
);

create index idx_rainfall_patterns_destination on rainfall_patterns(destination_id);

create trigger trg_rainfall_patterns_updated_at
  before update on rainfall_patterns
  for each row execute function set_updated_at();

create table wildlife (
  id uuid primary key default gen_random_uuid(),
  common_name text not null,
  scientific_name text not null,
  category wildlife_category not null,
  conservation_status conservation_status not null default 'not_evaluated',
  description text,
  average_size_notes text,
  diet text,
  behavior_notes text,
  is_big_five boolean not null default false,
  is_big_cat boolean not null default false,
  image_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (scientific_name)
);

create index idx_wildlife_category on wildlife(category);
create index idx_wildlife_conservation on wildlife(conservation_status);
create index idx_wildlife_big_five on wildlife(is_big_five) where is_big_five = true;
create index idx_wildlife_name_trgm on wildlife using gin (common_name gin_trgm_ops);

create trigger trg_wildlife_updated_at
  before update on wildlife
  for each row execute function set_updated_at();

create table destination_wildlife (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  wildlife_id uuid not null references wildlife(id) on delete cascade,
  population_estimate integer,
  density_rating text,
  best_viewing_areas text[],
  sighting_probability_pct integer check (sighting_probability_pct between 0 and 100),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (destination_id, wildlife_id)
);

create index idx_dest_wildlife_destination on destination_wildlife(destination_id);
create index idx_dest_wildlife_species on destination_wildlife(wildlife_id);
create index idx_dest_wildlife_density on destination_wildlife(density_rating);

create trigger trg_destination_wildlife_updated_at
  before update on destination_wildlife
  for each row execute function set_updated_at();

create table wildlife_calendar (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  wildlife_id uuid not null references wildlife(id) on delete cascade,
  month month_enum not null,
  sighting_probability_pct integer check (sighting_probability_pct between 0 and 100),
  behavior_notes text,
  best_time_of_day text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (destination_id, wildlife_id, month)
);

create index idx_wildlife_calendar_destination on wildlife_calendar(destination_id);
create index idx_wildlife_calendar_species on wildlife_calendar(wildlife_id);
create index idx_wildlife_calendar_month on wildlife_calendar(month);

create trigger trg_wildlife_calendar_updated_at
  before update on wildlife_calendar
  for each row execute function set_updated_at();

create table great_migration_calendar (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  month month_enum not null,
  phase migration_phase not null,
  approximate_location text not null,
  location_point geography(Point, 4326),
  herd_size_estimate text,
  river_crossing_likelihood_pct integer check (river_crossing_likelihood_pct between 0 and 100),
  predator_activity_notes text,
  recommended_camps text[],
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (destination_id, month, phase)
);

create index idx_migration_calendar_destination on great_migration_calendar(destination_id);
create index idx_migration_calendar_month on great_migration_calendar(month);
create index idx_migration_calendar_location on great_migration_calendar using gist (location_point);

create trigger trg_great_migration_calendar_updated_at
  before update on great_migration_calendar
  for each row execute function set_updated_at();

create table wildlife_density_zones (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  zone_name text not null,
  zone_boundary geography(Polygon, 4326),
  overall_density_rating text not null,
  peak_months month_enum[],
  dominant_species text[],
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_wildlife_density_zones_destination on wildlife_density_zones(destination_id);
create index idx_wildlife_density_zones_boundary on wildlife_density_zones using gist (zone_boundary);

create trigger trg_wildlife_density_zones_updated_at
  before update on wildlife_density_zones
  for each row execute function set_updated_at();

create table activities (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  name text not null,
  category activity_category not null,
  description text,
  difficulty difficulty_level not null default 'easy',
  min_age integer,
  max_participants integer,
  typical_price_usd numeric(10,2),
  price_notes text,
  booking_lead_time_days integer,
  available_months month_enum[],
  starts_at_location geography(Point, 4326),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_activities_destination on activities(destination_id);
create index idx_activities_category on activities(category);
create index idx_activities_difficulty on activities(difficulty);
create index idx_activities_location on activities using gist (starts_at_location);

create trigger trg_activities_updated_at
  before update on activities
  for each row execute function set_updated_at();

create table activity_requirements (
  id uuid primary key default gen_random_uuid(),
  activity_id uuid not null references activities(id) on delete cascade,
  requirement_type text not null,
  description text not null,
  is_mandatory boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_activity_requirements_activity on activity_requirements(activity_id);
create index idx_activity_requirements_type on activity_requirements(requirement_type);

create trigger trg_activity_requirements_updated_at
  before update on activity_requirements
  for each row execute function set_updated_at();

create table estimated_visit_durations (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  activity_id uuid references activities(id) on delete cascade,
  scope text not null,
  min_hours numeric(5,2),
  max_hours numeric(5,2),
  recommended_nights_min integer,
  recommended_nights_max integer,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_visit_durations_destination on estimated_visit_durations(destination_id);
create index idx_visit_durations_activity on estimated_visit_durations(activity_id);

create trigger trg_estimated_visit_durations_updated_at
  before update on estimated_visit_durations
  for each row execute function set_updated_at();

create table photography_locations (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  name text not null,
  location geography(Point, 4326),
  subject_matter text,
  best_months month_enum[],
  best_time_of_day text,
  difficulty_to_access difficulty_level not null default 'easy',
  gear_recommendations text,
  permit_required boolean not null default false,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_photo_locations_destination on photography_locations(destination_id);
create index idx_photo_locations_geo on photography_locations using gist (location);

create trigger trg_photography_locations_updated_at
  before update on photography_locations
  for each row execute function set_updated_at();

create table sunrise_locations (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  name text not null,
  location geography(Point, 4326),
  description text,
  best_months month_enum[],
  accessibility_notes text,
  requires_early_departure boolean not null default true,
  typical_departure_offset_minutes integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_sunrise_locations_destination on sunrise_locations(destination_id);
create index idx_sunrise_locations_geo on sunrise_locations using gist (location);

create trigger trg_sunrise_locations_updated_at
  before update on sunrise_locations
  for each row execute function set_updated_at();

create table sunset_locations (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  name text not null,
  location geography(Point, 4326),
  description text,
  best_months month_enum[],
  accessibility_notes text,
  has_sundowner_service boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_sunset_locations_destination on sunset_locations(destination_id);
create index idx_sunset_locations_geo on sunset_locations using gist (location);

create trigger trg_sunset_locations_updated_at
  before update on sunset_locations
  for each row execute function set_updated_at();

create table viewpoints (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  name text not null,
  location geography(Point, 4326),
  elevation_m integer,
  description text,
  panoramic_rating integer check (panoramic_rating between 1 and 5),
  accessible_by_vehicle boolean not null default true,
  walking_required_minutes integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_viewpoints_destination on viewpoints(destination_id);
create index idx_viewpoints_geo on viewpoints using gist (location);

create trigger trg_viewpoints_updated_at
  before update on viewpoints
  for each row execute function set_updated_at();

create table scenic_stops (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  name text not null,
  location geography(Point, 4326),
  description text,
  stop_duration_minutes integer,
  has_facilities boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_scenic_stops_destination on scenic_stops(destination_id);
create index idx_scenic_stops_geo on scenic_stops using gist (location);

create trigger trg_scenic_stops_updated_at
  before update on scenic_stops
  for each row execute function set_updated_at();

create table picnic_sites (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  name text not null,
  location geography(Point, 4326),
  has_toilets boolean not null default false,
  has_shade boolean not null default true,
  has_water boolean not null default false,
  security_rating text,
  predator_risk_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_picnic_sites_destination on picnic_sites(destination_id);
create index idx_picnic_sites_geo on picnic_sites using gist (location);

create trigger trg_picnic_sites_updated_at
  before update on picnic_sites
  for each row execute function set_updated_at();

create table lodges (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  name text not null,
  tier lodge_tier not null,
  location geography(Point, 4326),
  description text,
  number_of_rooms integer,
  number_of_beds integer,
  meal_plan meal_plan not null default 'full_board',
  price_per_night_usd_low numeric(10,2),
  price_per_night_usd_high numeric(10,2),
  currency fee_currency not null default 'USD',
  has_pool boolean not null default false,
  has_spa boolean not null default false,
  has_wifi boolean not null default false,
  has_electricity boolean not null default true,
  is_fenced boolean not null default false,
  is_family_friendly boolean not null default false,
  is_honeymoon_suitable boolean not null default false,
  wheelchair_accessible boolean not null default false,
  star_rating numeric(2,1) check (star_rating between 0 and 5),
  operator_name text,
  booking_website text,
  contact_email text,
  contact_phone text,
  check_in_time time,
  check_out_time time,
  cancellation_policy text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_lodges_destination on lodges(destination_id);
create index idx_lodges_tier on lodges(tier);
create index idx_lodges_geo on lodges using gist (location);
create index idx_lodges_family on lodges(is_family_friendly) where is_family_friendly = true;
create index idx_lodges_honeymoon on lodges(is_honeymoon_suitable) where is_honeymoon_suitable = true;
create index idx_lodges_name_trgm on lodges using gin (name gin_trgm_ops);

create trigger trg_lodges_updated_at
  before update on lodges
  for each row execute function set_updated_at();

create view luxury_lodges as
  select * from lodges where tier in ('luxury','ultra_luxury');

create view mid_range_lodges as
  select * from lodges where tier = 'mid_range';

create view budget_camps as
  select * from lodges where tier in ('budget','camping');

create table lodge_amenities (
  id uuid primary key default gen_random_uuid(),
  lodge_id uuid not null references lodges(id) on delete cascade,
  amenity_name text not null,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (lodge_id, amenity_name)
);

create index idx_lodge_amenities_lodge on lodge_amenities(lodge_id);

create trigger trg_lodge_amenities_updated_at
  before update on lodge_amenities
  for each row execute function set_updated_at();

create table restaurants (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  lodge_id uuid references lodges(id) on delete set null,
  name text not null,
  location geography(Point, 4326),
  cuisine_type text,
  price_range text,
  is_standalone boolean not null default true,
  dietary_options text[],
  opening_time time,
  closing_time time,
  reservation_required boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_restaurants_destination on restaurants(destination_id);
create index idx_restaurants_lodge on restaurants(lodge_id);
create index idx_restaurants_geo on restaurants using gist (location);

create trigger trg_restaurants_updated_at
  before update on restaurants
  for each row execute function set_updated_at();

create table family_suitability (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  rating suitability_rating not null,
  min_recommended_age integer,
  child_activity_notes text,
  safety_notes text,
  malaria_risk boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (destination_id)
);

create index idx_family_suitability_destination on family_suitability(destination_id);

create trigger trg_family_suitability_updated_at
  before update on family_suitability
  for each row execute function set_updated_at();

create table honeymoon_suitability (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  rating suitability_rating not null,
  romance_notes text,
  privacy_level text,
  recommended_lodge_ids uuid[],
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (destination_id)
);

create index idx_honeymoon_suitability_destination on honeymoon_suitability(destination_id);

create trigger trg_honeymoon_suitability_updated_at
  before update on honeymoon_suitability
  for each row execute function set_updated_at();

create table accessibility (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  overall_level accessibility_level not null,
  wheelchair_notes text,
  mobility_impaired_notes text,
  visually_impaired_notes text,
  hearing_impaired_notes text,
  accessible_vehicles_available boolean not null default false,
  accessible_accommodation_count integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (destination_id)
);

create index idx_accessibility_destination on accessibility(destination_id);

create trigger trg_accessibility_updated_at
  before update on accessibility
  for each row execute function set_updated_at();

create table child_friendliness (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  activity_id uuid references activities(id) on delete cascade,
  min_age integer not null default 0,
  rating suitability_rating not null,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_child_friendliness_destination on child_friendliness(destination_id);
create index idx_child_friendliness_activity on child_friendliness(activity_id);

create trigger trg_child_friendliness_updated_at
  before update on child_friendliness
  for each row execute function set_updated_at();

create table adventure_ratings (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  activity_id uuid references activities(id) on delete cascade,
  scale adventure_scale not null,
  fitness_required text,
  risk_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_adventure_ratings_destination on adventure_ratings(destination_id);
create index idx_adventure_ratings_activity on adventure_ratings(activity_id);

create trigger trg_adventure_ratings_updated_at
  before update on adventure_ratings
  for each row execute function set_updated_at();

create table safety_information (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  category text not null,
  risk_level text not null,
  description text not null,
  mitigation_advice text,
  emergency_procedure text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_safety_info_destination on safety_information(destination_id);
create index idx_safety_info_category on safety_information(category);

create trigger trg_safety_information_updated_at
  before update on safety_information
  for each row execute function set_updated_at();

create table medical_facilities (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  name text not null,
  facility_type text not null,
  location geography(Point, 4326),
  distance_from_destination_km numeric(8,2),
  has_emergency_evacuation boolean not null default false,
  evacuation_provider text,
  phone_number text,
  operating_hours text,
  is_24_hour boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_medical_facilities_destination on medical_facilities(destination_id);
create index idx_medical_facilities_geo on medical_facilities using gist (location);

create trigger trg_medical_facilities_updated_at
  before update on medical_facilities
  for each row execute function set_updated_at();

create table fuel_stations (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  name text not null,
  location geography(Point, 4326),
  brand text,
  fuel_types text[],
  is_24_hour boolean not null default false,
  accepts_card boolean not null default false,
  reliability_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_fuel_stations_destination on fuel_stations(destination_id);
create index idx_fuel_stations_geo on fuel_stations using gist (location);

create trigger trg_fuel_stations_updated_at
  before update on fuel_stations
  for each row execute function set_updated_at();

create table atm_locations (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  name text not null,
  location geography(Point, 4326),
  bank_name text,
  accepts_international_cards boolean not null default true,
  reliability_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_atm_locations_destination on atm_locations(destination_id);
create index idx_atm_locations_geo on atm_locations using gist (location);

create trigger trg_atm_locations_updated_at
  before update on atm_locations
  for each row execute function set_updated_at();

create table internet_coverage (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  quality internet_quality not null,
  mobile_data_providers text[],
  wifi_availability_notes text,
  starlink_available boolean not null default false,
  reliability_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (destination_id)
);

create index idx_internet_coverage_destination on internet_coverage(destination_id);

create trigger trg_internet_coverage_updated_at
  before update on internet_coverage
  for each row execute function set_updated_at();

create table electricity_availability (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  electricity_type electricity_type not null,
  hours_available_notes text,
  voltage text,
  plug_type text,
  charging_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (destination_id)
);

create index idx_electricity_availability_destination on electricity_availability(destination_id);

create trigger trg_electricity_availability_updated_at
  before update on electricity_availability
  for each row execute function set_updated_at();

create table water_availability (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  water_source water_source not null,
  drinkable_from_tap boolean not null default false,
  bottled_water_available boolean not null default true,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (destination_id)
);

create index idx_water_availability_destination on water_availability(destination_id);

create trigger trg_water_availability_updated_at
  before update on water_availability
  for each row execute function set_updated_at();

create table park_regulations (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  regulation_category text not null,
  description text not null,
  penalty_notes text,
  is_strictly_enforced boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_park_regulations_destination on park_regulations(destination_id);
create index idx_park_regulations_category on park_regulations(regulation_category);

create trigger trg_park_regulations_updated_at
  before update on park_regulations
  for each row execute function set_updated_at();

create table entry_fees (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  payer_category fee_payer_category not null,
  fee_amount numeric(10,2) not null,
  currency fee_currency not null default 'USD',
  validity_hours integer,
  season_type season_type,
  effective_from date,
  effective_to date,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_entry_fees_destination on entry_fees(destination_id);
create index idx_entry_fees_payer_category on entry_fees(payer_category);
create index idx_entry_fees_effective on entry_fees(effective_from, effective_to);

create trigger trg_entry_fees_updated_at
  before update on entry_fees
  for each row execute function set_updated_at();

create table operating_hours (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  applies_to text not null default 'destination',
  reference_id uuid,
  day_of_week integer check (day_of_week between 0 and 6),
  opening_time time not null,
  closing_time time not null,
  is_24_hour boolean not null default false,
  seasonal_variation_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_operating_hours_destination on operating_hours(destination_id);
create index idx_operating_hours_reference on operating_hours(reference_id);
create index idx_operating_hours_day on operating_hours(day_of_week);

create trigger trg_operating_hours_updated_at
  before update on operating_hours
  for each row execute function set_updated_at();

create table ranger_stations (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  name text not null,
  location geography(Point, 4326),
  phone_number text,
  radio_channel text,
  is_24_hour boolean not null default true,
  services text[],
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_ranger_stations_destination on ranger_stations(destination_id);
create index idx_ranger_stations_geo on ranger_stations using gist (location);

create trigger trg_ranger_stations_updated_at
  before update on ranger_stations
  for each row execute function set_updated_at();

create table emergency_contacts (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  contact_type text not null,
  name text not null,
  phone_number text not null,
  alternate_phone_number text,
  email text,
  is_24_hour boolean not null default true,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_emergency_contacts_destination on emergency_contacts(destination_id);
create index idx_emergency_contacts_type on emergency_contacts(contact_type);

create trigger trg_emergency_contacts_updated_at
  before update on emergency_contacts
  for each row execute function set_updated_at();

create table local_guides (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  full_name text not null,
  certification guide_certification not null default 'uncertified',
  years_experience integer,
  languages_spoken text[],
  specialties text[],
  phone_number text,
  email text,
  affiliated_operator_id uuid,
  rating numeric(2,1) check (rating between 0 and 5),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_local_guides_destination on local_guides(destination_id);
create index idx_local_guides_certification on local_guides(certification);

create trigger trg_local_guides_updated_at
  before update on local_guides
  for each row execute function set_updated_at();

create table tour_operators (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  verification_status operator_verification_status not null default 'unverified',
  verification_date date,
  license_number text,
  headquarters_country country_code,
  website text,
  contact_email text,
  contact_phone text,
  years_in_operation integer,
  fleet_size integer,
  specializes_in destination_type[],
  rating numeric(2,1) check (rating between 0 and 5),
  review_count integer default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_tour_operators_verification on tour_operators(verification_status);
create index idx_tour_operators_name_trgm on tour_operators using gin (name gin_trgm_ops);

create trigger trg_tour_operators_updated_at
  before update on tour_operators
  for each row execute function set_updated_at();

alter table local_guides
  add constraint fk_local_guides_operator
  foreign key (affiliated_operator_id) references tour_operators(id) on delete set null;

create index idx_local_guides_operator on local_guides(affiliated_operator_id);

create table destination_tour_operators (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  tour_operator_id uuid not null references tour_operators(id) on delete cascade,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (destination_id, tour_operator_id)
);

create index idx_dest_operators_destination on destination_tour_operators(destination_id);
create index idx_dest_operators_operator on destination_tour_operators(tour_operator_id);

create trigger trg_destination_tour_operators_updated_at
  before update on destination_tour_operators
  for each row execute function set_updated_at();

create table languages_spoken (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  language_name text not null,
  is_official boolean not null default false,
  prevalence text,
  useful_phrases jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (destination_id, language_name)
);

create index idx_languages_spoken_destination on languages_spoken(destination_id);

create trigger trg_languages_spoken_updated_at
  before update on languages_spoken
  for each row execute function set_updated_at();

create table local_culture (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  ethnic_groups text[],
  cultural_topic text not null,
  description text not null,
  dos text[],
  donts text[],
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_local_culture_destination on local_culture(destination_id);
create index idx_local_culture_topic on local_culture(cultural_topic);

create trigger trg_local_culture_updated_at
  before update on local_culture
  for each row execute function set_updated_at();

create table dress_recommendations (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  context text not null,
  recommendation text not null,
  color_advice text,
  cultural_sensitivity_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_dress_recommendations_destination on dress_recommendations(destination_id);
create index idx_dress_recommendations_context on dress_recommendations(context);

create trigger trg_dress_recommendations_updated_at
  before update on dress_recommendations
  for each row execute function set_updated_at();

create table packing_recommendations (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  item_category text not null,
  item_name text not null,
  is_essential boolean not null default true,
  season_type season_type,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_packing_recommendations_destination on packing_recommendations(destination_id);
create index idx_packing_recommendations_category on packing_recommendations(item_category);

create trigger trg_packing_recommendations_updated_at
  before update on packing_recommendations
  for each row execute function set_updated_at();

create table best_worst_months (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  month month_enum not null,
  classification text not null check (classification in ('best','good','fair','worst')),
  reasoning text not null,
  crowd_level text,
  value_for_money text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (destination_id, month)
);

create index idx_best_worst_months_destination on best_worst_months(destination_id);
create index idx_best_worst_months_classification on best_worst_months(classification);

create trigger trg_best_worst_months_updated_at
  before update on best_worst_months
  for each row execute function set_updated_at();

create table bird_species_details (
  id uuid primary key default gen_random_uuid(),
  wildlife_id uuid not null references wildlife(id) on delete cascade,
  destination_id uuid not null references travel_places(id) on delete cascade,
  is_endemic boolean not null default false,
  is_migratory boolean not null default false,
  migratory_months month_enum[],
  call_description text,
  habitat_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (wildlife_id, destination_id)
);

create index idx_bird_species_wildlife on bird_species_details(wildlife_id);
create index idx_bird_species_destination on bird_species_details(destination_id);

create trigger trg_bird_species_details_updated_at
  before update on bird_species_details
  for each row execute function set_updated_at();

create table mammal_species_details (
  id uuid primary key default gen_random_uuid(),
  wildlife_id uuid not null references wildlife(id) on delete cascade,
  destination_id uuid not null references travel_places(id) on delete cascade,
  typical_herd_size text,
  territorial_notes text,
  nocturnal boolean not null default false,
  predator_of text[],
  prey_of text[],
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (wildlife_id, destination_id)
);

create index idx_mammal_species_wildlife on mammal_species_details(wildlife_id);
create index idx_mammal_species_destination on mammal_species_details(destination_id);

create trigger trg_mammal_species_details_updated_at
  before update on mammal_species_details
  for each row execute function set_updated_at();

create table reptile_species_details (
  id uuid primary key default gen_random_uuid(),
  wildlife_id uuid not null references wildlife(id) on delete cascade,
  destination_id uuid not null references travel_places(id) on delete cascade,
  venomous boolean not null default false,
  danger_level text,
  basking_spots text,
  best_viewing_season season_type,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (wildlife_id, destination_id)
);

create index idx_reptile_species_wildlife on reptile_species_details(wildlife_id);
create index idx_reptile_species_destination on reptile_species_details(destination_id);

create trigger trg_reptile_species_details_updated_at
  before update on reptile_species_details
  for each row execute function set_updated_at();

create table photography_tips (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  photography_location_id uuid references photography_locations(id) on delete cascade,
  tip_category text not null,
  tip_text text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_photography_tips_destination on photography_tips(destination_id);
create index idx_photography_tips_location on photography_tips(photography_location_id);

create trigger trg_photography_tips_updated_at
  before update on photography_tips
  for each row execute function set_updated_at();

create table travel_tips (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  tip_category text not null,
  tip_text text not null,
  priority integer not null default 3,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_travel_tips_destination on travel_tips(destination_id);
create index idx_travel_tips_category on travel_tips(tip_category);
create index idx_travel_tips_priority on travel_tips(priority);

create trigger trg_travel_tips_updated_at
  before update on travel_tips
  for each row execute function set_updated_at();

create table hidden_gems (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid not null references travel_places(id) on delete cascade,
  name text not null,
  location geography(Point, 4326),
  description text not null,
  why_overlooked text,
  best_months month_enum[],
  insider_tip text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_hidden_gems_destination on hidden_gems(destination_id);
create index idx_hidden_gems_geo on hidden_gems using gist (location);

create trigger trg_hidden_gems_updated_at
  before update on hidden_gems
  for each row execute function set_updated_at();

create table frequently_asked_questions (
  id uuid primary key default gen_random_uuid(),
  destination_id uuid references travel_places(id) on delete cascade,
  category faq_category not null,
  question text not null,
  answer text not null,
  display_order integer not null default 0,
  is_published boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_faqs_destination on frequently_asked_questions(destination_id);
create index idx_faqs_category on frequently_asked_questions(category);
create index idx_faqs_published on frequently_asked_questions(is_published) where is_published = true;

create trigger trg_faqs_updated_at
  before update on frequently_asked_questions
  for each row execute function set_updated_at();
