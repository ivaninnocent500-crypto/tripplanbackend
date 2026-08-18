-- =====================================================================
-- SAMPLE SEED — reproduces the "Tanzania, Wild & Unhurried" trip from
-- the app screenshots end-to-end: itinerary -> operator match ->
-- quotes -> booking confirmed.
--
-- FIX: all placeholder UUIDs below use only hex characters (0-9a-f).
-- The previous version used 's0000000...' / 'w0000000...' etc which
-- are NOT valid uuid literals (s, w, h are not hex digits) — that's
-- what threw the 22P02 error. Each entity type below gets its own
-- all-hex prefix instead (aaaaaaaa=cabinet, bbbbbbbb=shelf,
-- cccccccc=bench, dddddddd=wardrobe, eeeeeeee=tour_operators).
--
-- Destination UUIDs (...111/...112/...113) match the ids visible in
-- your production travel_places table for Serengeti / Ngorongoro /
-- Tarangire. GAP: "Arusha" (the Day 1 gateway city) is NOT in your
-- seeded travel_places — inserted below with destination_type 'city'.
-- =====================================================================

begin;

-- Gap-fill: Arusha as a proper travel_place (gateway city, day-1 anchor)
insert into travel_places (id, name, slug, destination_type, country, region, short_description, is_published, popularity_rank)
values (
  '11111111-1111-1111-1111-111111111199',
  'Arusha', 'arusha', 'city', 'TZ', 'Arusha Region',
  'Northern Tanzania safari gateway city.', true, 5
)
on conflict (slug) do nothing;

-- ---------------------------------------------------------------------
-- CABINET (the trip)
-- ---------------------------------------------------------------------
insert into cabinets (
  id, request_json, title, duration_days, travelers_adults, travelers_children,
  travel_style, budget_tier, status, start_date, end_date,
  estimated_budget_low, estimated_budget_high, currency,
  primary_destination_id, route_destination_ids, confidence_score
) values (
  'aaaaaaaa-0000-0000-0000-000000000001',
  '{"days":7,"travelers":2,"budget_tier":"luxury","destinations":["arusha","tarangire","ngorongoro","serengeti"],"focus":"wildlife"}',
  'Tanzania, Wild & Unhurried',
  7, 2, 0,
  ARRAY['wildlife','luxury','private','relaxed_pace'],
  'luxury', 'ready', '2026-09-14', '2026-09-21',
  4000, 5000, 'USD',
  '11111111-1111-1111-1111-111111111199',
  ARRAY[
    '11111111-1111-1111-1111-111111111199'::uuid, -- Arusha
    '11111111-1111-1111-1111-111111111113'::uuid, -- Tarangire
    '11111111-1111-1111-1111-111111111112'::uuid, -- Ngorongoro
    '11111111-1111-1111-1111-111111111111'::uuid  -- Serengeti
  ],
  94
);

-- ---------------------------------------------------------------------
-- SHELF: Day 1 - Arusha (matches image "Day 1 / Arusha / Arrival & slow start")
-- ---------------------------------------------------------------------
insert into shelves (id, cabinet_id, day_number, date, destination_id, theme)
values (
  'bbbbbbbb-0000-0000-0000-000000000001',
  'aaaaaaaa-0000-0000-0000-000000000001',
  1, '2026-09-14', '11111111-1111-1111-1111-111111111199',
  'Arrival & slow start'
);

insert into drawers (shelf_id, name, description, start_time, duration_minutes, sort_order, activity_type, location_name) values
('bbbbbbbb-0000-0000-0000-000000000001', 'Airport welcome', 'Met at Kilimanjaro International by your driver-guide.', '14:00', 60, 1, 'ARRIVAL', 'Arusha'),
('bbbbbbbb-0000-0000-0000-000000000001', 'Coffee farm walk', 'Gentle introduction to the highlands, no rush.', '16:00', 90, 2, 'EXPERIENCE', 'Arusha'),
('bbbbbbbb-0000-0000-0000-000000000001', 'Dinner at the lodge', 'Garden setting, early night before the parks.', '19:30', 90, 3, 'MEAL', 'Arusha');

insert into headboards (shelf_id, name, tier, check_in, check_out, nights) values
('bbbbbbbb-0000-0000-0000-000000000001', 'Boutique garden lodge · Arusha', 'luxury', '2026-09-14', '2026-09-15', 1);

insert into armrests (shelf_id, mode, description, duration_minutes, is_private) values
('bbbbbbbb-0000-0000-0000-000000000001', 'private_4x4', 'Private 4x4 · 55 min transfer', 55, true);

insert into trays (shelf_id, meal_type, included) values
('bbbbbbbb-0000-0000-0000-000000000001', 'dinner', true);

-- ---------------------------------------------------------------------
-- HINGES: route legs for the whole trip (backs routing + validation)
-- ---------------------------------------------------------------------
insert into hinges (cabinet_id, from_destination_id, to_destination_id, sequence_order, distance_km, duration_minutes, mode, source) values
('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111199', '11111111-1111-1111-1111-111111111113', 1, 118, 150, 'private_4x4', 'drive_times'),
('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111113', '11111111-1111-1111-1111-111111111112', 2, 145, 165, 'private_4x4', 'drive_times'),
('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111111', 3, 180, 210, 'private_4x4', 'drive_times');

-- ---------------------------------------------------------------------
-- FOOTSTOOLS: sample validation pass (all clean -> status can become 'ready')
-- ---------------------------------------------------------------------
insert into footstools (cabinet_id, severity, category, message, auto_repaired) values
('aaaaaaaa-0000-0000-0000-000000000001', 'info', 'transport', 'All transfers fit within available daylight hours.', false),
('aaaaaaaa-0000-0000-0000-000000000001', 'info', 'accommodation', 'Every overnight has a matching headboard record.', false);

-- ---------------------------------------------------------------------
-- TOUR OPERATORS (gap-fill sample — replace with your real verified operators)
-- ---------------------------------------------------------------------
insert into tour_operators (id, name, verification_status, headquarters_country, years_in_operation, rating, review_count)
values
  ('eeeeeeee-0000-0000-0000-0000000000a1', 'Safari Horizons', 'verified', 'TZ', 14, 4.8, 212),
  ('eeeeeeee-0000-0000-0000-0000000000a2', 'Wild Africa Journeys', 'verified', 'TZ', 11, 4.7, 145),
  ('eeeeeeee-0000-0000-0000-0000000000a3', 'SafariCo Tanzania', 'verified', 'TZ', 9, 4.6, 98)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- STOOLS: operator match results (matches "Choose your safari partner")
-- ---------------------------------------------------------------------
insert into stools (
  cabinet_id, tour_operator_id, trip_match_pct, itinerary_fit_pct, experience_fit_pct,
  accommodation_fit_pct, destination_coverage_pct, service_pct, trust_pct, value_pct,
  strengths, badge, estimated_price_pp
) values
('aaaaaaaa-0000-0000-0000-000000000001', 'eeeeeeee-0000-0000-0000-0000000000a1', 94, 96, 95, 93, 100, 91, 94, 87,
 ARRAY['Excellent fit for your wildlife itinerary','Strong luxury accommodation options','Private safari vehicle available','Relaxed itinerary structure','Verified operator','Strong response history'],
 'strongest_match', 4200),
('aaaaaaaa-0000-0000-0000-000000000001', 'eeeeeeee-0000-0000-0000-0000000000a2', 91, 90, 93, 92, 95, 90, 91, 82,
 ARRAY['Higher-end lodges and more personalized service'],
 'best_premium_experience', 4650),
('aaaaaaaa-0000-0000-0000-000000000001', 'eeeeeeee-0000-0000-0000-0000000000a3', 89, 87, 86, 85, 95, 88, 89, 93,
 ARRAY['Similar itinerary at a lower estimated cost'],
 'best_value', 3780);

-- ---------------------------------------------------------------------
-- BENCHES + COUNTERS: quote request / tracking / comparison
-- ---------------------------------------------------------------------
insert into benches (id, cabinet_id, tour_operator_id, status, note, requested_at, responded_at) values
('cccccccc-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001', 'eeeeeeee-0000-0000-0000-0000000000a1', 'quote_received', 'We are celebrating our anniversary and would prefer a quieter lodge.', now() - interval '2 hours', now()),
('cccccccc-0000-0000-0000-000000000002', 'aaaaaaaa-0000-0000-0000-000000000001', 'eeeeeeee-0000-0000-0000-0000000000a2', 'operator_reviewing', null, now() - interval '1 hour', null),
('cccccccc-0000-0000-0000-000000000003', 'aaaaaaaa-0000-0000-0000-000000000001', 'eeeeeeee-0000-0000-0000-0000000000a3', 'request_sent', null, now() - interval '30 minutes', null);

insert into counters (
  bench_id, price_per_person, currency, validity_date,
  accommodation_summary, activities_summary, transport_summary, meals_summary,
  park_fees_included, transfers_included, difference_notes, status
) values (
  'cccccccc-0000-0000-0000-000000000001', 4280, 'USD', '2026-08-24',
  'Luxury lodge · 6 nights', '9 game drives', 'Private 4x4', 'All meals',
  true, true, 'Closest to your original itinerary', 'received'
);

-- ---------------------------------------------------------------------
-- WARDROBE + CHEST: confirmed booking (matches "Booking confirmed")
-- ---------------------------------------------------------------------
insert into wardrobes (
  id, cabinet_id, counter_id, confirmation_code, tour_operator_id,
  price_per_person, total_price, deposit_amount, status
) values (
  'dddddddd-0000-0000-0000-000000000001',
  'aaaaaaaa-0000-0000-0000-000000000001',
  (select id from counters where bench_id = 'cccccccc-0000-0000-0000-000000000001'),
  'ATO-TZ-249381',
  'eeeeeeee-0000-0000-0000-0000000000a1',
  4280, 8560, 1712, 'confirmed'
);

insert into chests (wardrobe_id, amount, currency, payment_type, status, paid_at) values
('dddddddd-0000-0000-0000-000000000001', 1712, 'USD', 'deposit', 'completed', now());

update cabinets set status = 'confirmed' where id = 'aaaaaaaa-0000-0000-0000-000000000001';

commit;
