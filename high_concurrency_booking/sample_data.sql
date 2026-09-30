-- ============================================================================
-- High-Concurrency Booking Engine: Sample Data Seed Script (P1)
-- Provides realistic datasets for testing queries, joins, and concurrency
-- ============================================================================

-- Clean existing data
TRUNCATE TABLE payment_webhook_events, booking_items, show_seats, bookings, seats, shows, movies, screens, theatres RESTART IDENTITY CASCADE;

-- ----------------------------------------------------------------------------
-- 1. Insert Theatres
-- ----------------------------------------------------------------------------
INSERT INTO theatres (name, city, address) VALUES
('PVR Director''s Cut, Ambience Mall', 'New Delhi', 'Ambience Mall, Nelson Mandela Marg, Vasant Kunj, New Delhi 110070'),
('INOX Megaplex, Phoenix Marketcity', 'Mumbai', 'Phoenix Marketcity, LBS Marg, Kurla West, Mumbai 400070'),
('PVR Forum Mall, Koramangala', 'Bengaluru', 'The Forum Mall, Hosur Road, Koramangala, Bengaluru 560095');

-- ----------------------------------------------------------------------------
-- 2. Insert Screens (Auditoriums)
-- ----------------------------------------------------------------------------
INSERT INTO screens (theatre_id, screen_number, name, total_seats) VALUES
(1, 1, 'Audi 1 - Director''s Lounge', 12),
(1, 2, 'Audi 2 - IMAX with Laser', 18),
(2, 1, 'Screen 1 - Insignia', 15),
(2, 2, 'Screen 2 - Dolby Cinema', 20),
(3, 1, 'Audi 1 - Gold Class', 12);

-- ----------------------------------------------------------------------------
-- 3. Insert Movies
-- ----------------------------------------------------------------------------
INSERT INTO movies (title, duration_minutes, language, genre, release_date) VALUES
('Dune: Part Two', 166, 'English', 'Sci-Fi / Adventure', '2026-03-01'),
('Oppenheimer: Director''s Cut', 180, 'English', 'Biography / Drama', '2026-07-21'),
('Kalki 2898 AD', 181, 'Hindi', 'Sci-Fi / Action', '2026-06-27'),
('Interstellar: 12th Anniversary Re-Release', 169, 'English', 'Sci-Fi / Drama', '2026-09-15');

-- ----------------------------------------------------------------------------
-- 4. Insert Shows (Covering current and upcoming 7 calendar days)
-- Target Date: '2026-10-01' at Theatre 1 (PVR Director's Cut)
-- ----------------------------------------------------------------------------
INSERT INTO shows (screen_id, movie_id, show_date, start_time, end_time) VALUES
-- Theatre 1, Screen 1 (2026-10-01)
(1, 1, '2026-10-01', '10:00:00', '13:00:00'),
(1, 1, '2026-10-01', '14:30:00', '17:30:00'),
(1, 2, '2026-10-01', '19:00:00', '22:15:00'),

-- Theatre 1, Screen 2 (2026-10-01)
(2, 3, '2026-10-01', '11:15:00', '14:30:00'),
(2, 2, '2026-10-01', '16:00:00', '19:15:00'),
(2, 4, '2026-10-01', '20:30:00', '23:30:00'),

-- Theatre 1, Screen 1 (2026-10-02 - Next Day)
(1, 1, '2026-10-02', '10:00:00', '13:00:00'),
(1, 2, '2026-10-02', '18:00:00', '21:15:00'),

-- Theatre 2, Screen 1 (2026-10-01 - Different Theatre in Mumbai)
(3, 1, '2026-10-01', '12:00:00', '15:00:00'),
(3, 4, '2026-10-01', '18:00:00', '21:00:00');

-- ----------------------------------------------------------------------------
-- 5. Insert Physical Seats for Screen 1 & Screen 2 (Theatre 1)
-- ----------------------------------------------------------------------------
-- Screen 1: 12 seats (Row A: Recliner, Row B: Gold)
INSERT INTO seats (screen_id, row_label, seat_number, tier) VALUES
(1, 'A', 1, 'RECLINER'), (1, 'A', 2, 'RECLINER'), (1, 'A', 3, 'RECLINER'), (1, 'A', 4, 'RECLINER'),
(1, 'A', 5, 'RECLINER'), (1, 'A', 6, 'RECLINER'),
(1, 'B', 1, 'GOLD'),     (1, 'B', 2, 'GOLD'),     (1, 'B', 3, 'GOLD'),     (1, 'B', 4, 'GOLD'),
(1, 'B', 5, 'GOLD'),     (1, 'B', 6, 'GOLD');

-- Screen 2: 18 seats (Row A: Silver, Row B: Gold, Row C: Recliner)
INSERT INTO seats (screen_id, row_label, seat_number, tier) VALUES
(2, 'A', 1, 'SILVER'),   (2, 'A', 2, 'SILVER'),   (2, 'A', 3, 'SILVER'),   (2, 'A', 4, 'SILVER'),   (2, 'A', 5, 'SILVER'),   (2, 'A', 6, 'SILVER'),
(2, 'B', 1, 'GOLD'),     (2, 'B', 2, 'GOLD'),     (2, 'B', 3, 'GOLD'),     (2, 'B', 4, 'GOLD'),     (2, 'B', 5, 'GOLD'),     (2, 'B', 6, 'GOLD'),
(2, 'C', 1, 'RECLINER'), (2, 'C', 2, 'RECLINER'), (2, 'C', 3, 'RECLINER'), (2, 'C', 4, 'RECLINER'), (2, 'C', 5, 'RECLINER'), (2, 'C', 6, 'RECLINER');

-- ----------------------------------------------------------------------------
-- 6. Pre-Materialize Show Seats for Show 1 (Show 1: Dune at 10:00 AM on 2026-10-01)
-- Pricing: RECLINER = 800.00, GOLD = 500.00, SILVER = 300.00
-- ----------------------------------------------------------------------------
INSERT INTO show_seats (show_id, seat_id, price, status)
SELECT 
    1 AS show_id,
    s.id AS seat_id,
    CASE 
        WHEN s.tier = 'RECLINER' THEN 800.00
        WHEN s.tier = 'GOLD' THEN 500.00
        ELSE 300.00
    END AS price,
    'AVAILABLE' AS status
FROM seats s
WHERE s.screen_id = 1;

-- Pre-Materialize Show Seats for Show 2 (Show 2: Dune at 14:30 PM on 2026-10-01)
INSERT INTO show_seats (show_id, seat_id, price, status)
SELECT 
    2 AS show_id,
    s.id AS seat_id,
    CASE 
        WHEN s.tier = 'RECLINER' THEN 850.00
        WHEN s.tier = 'GOLD' THEN 550.00
        ELSE 350.00
    END AS price,
    'AVAILABLE' AS status
FROM seats s
WHERE s.screen_id = 1;

-- Pre-Materialize Show Seats for Show 4 (Screen 2: Kalki at 11:15 AM on 2026-10-01)
INSERT INTO show_seats (show_id, seat_id, price, status)
SELECT 
    4 AS show_id,
    s.id AS seat_id,
    CASE 
        WHEN s.tier = 'RECLINER' THEN 900.00
        WHEN s.tier = 'GOLD' THEN 600.00
        ELSE 350.00
    END AS price,
    'AVAILABLE' AS status
FROM seats s
WHERE s.screen_id = 2;

-- ----------------------------------------------------------------------------
-- 7. Seed One Confirmed Booking with Items & Payment Event (Demonstration)
-- Book seats A1 & A2 for Show 1 by User 'usr_alpha_99'
-- ----------------------------------------------------------------------------
INSERT INTO bookings (booking_reference, user_id, show_id, total_amount, status) VALUES
('BK-20261001-ALPHA1', 'usr_alpha_99', 1, 1600.00, 'CONFIRMED');

-- Link show_seats 1 and 2 to this confirmed booking
UPDATE show_seats 
SET status = 'BOOKED', booking_id = 1, held_by_user_id = 'usr_alpha_99' 
WHERE show_id = 1 AND seat_id IN (1, 2);

-- Insert Booking Items
INSERT INTO booking_items (booking_id, show_seat_id, price)
SELECT 1, id, price FROM show_seats WHERE show_id = 1 AND seat_id IN (1, 2);

-- ----------------------------------------------------------------------------
-- 8. Seed Payment Webhook Event for the Confirmed Booking (Demonstrating Idempotency)
-- ----------------------------------------------------------------------------
INSERT INTO payment_webhook_events (
    provider,
    event_id,
    booking_reference,
    event_type,
    payload,
    status,
    received_at,
    processed_at
) VALUES (
    'stripe',
    'evt_charge_succ_990141',
    'BK-20261001-ALPHA1',
    'payment_intent.succeeded',
    '{"amount": 160000, "currency": "inr", "charge_id": "ch_3PzXYZ", "customer_email": "alpha@example.com"}'::jsonb,
    'PROCESSED',
    CURRENT_TIMESTAMP - INTERVAL '15 minutes',
    CURRENT_TIMESTAMP - INTERVAL '14 minutes'
);
