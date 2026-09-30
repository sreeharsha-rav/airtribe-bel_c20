-- ============================================================================
-- High-Concurrency Booking Engine: PostgreSQL Schema DDL (P1)
-- Normalization: Fully normalized to 1NF, 2NF, 3NF, and BCNF
-- Target Engine: PostgreSQL 14+ (Compatible with ANSI SQL standards)
-- ============================================================================

-- Drop existing tables in reverse dependency order
DROP TABLE IF EXISTS payment_webhook_events CASCADE;
DROP TABLE IF EXISTS booking_items CASCADE;
DROP TABLE IF EXISTS bookings CASCADE;
DROP TABLE IF EXISTS show_seats CASCADE;
DROP TABLE IF EXISTS seats CASCADE;
DROP TABLE IF EXISTS shows CASCADE;
DROP TABLE IF EXISTS movies CASCADE;
DROP TABLE IF EXISTS screens CASCADE;
DROP TABLE IF EXISTS theatres CASCADE;

-- ----------------------------------------------------------------------------
-- 1. Theatres Table
-- Represents a cinema venue or multiplex complex.
-- ----------------------------------------------------------------------------
CREATE TABLE theatres (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    address TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 2. Screens Table (Auditoriums)
-- Represents an individual screening hall within a theatre.
-- ----------------------------------------------------------------------------
CREATE TABLE screens (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    theatre_id BIGINT NOT NULL REFERENCES theatres(id) ON DELETE CASCADE,
    screen_number INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    total_seats INT NOT NULL DEFAULT 0 CHECK (total_seats >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_theatre_screen_number UNIQUE (theatre_id, screen_number)
);

-- ----------------------------------------------------------------------------
-- 3. Movies Table
-- Represents the film, event, or performance being screened.
-- ----------------------------------------------------------------------------
CREATE TABLE movies (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    duration_minutes INT NOT NULL CHECK (duration_minutes > 0),
    language VARCHAR(50) NOT NULL,
    genre VARCHAR(100) NOT NULL,
    release_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 4. Shows Table (Screenings)
-- Represents a specific screening instance of a movie at a screen on a date.
-- ----------------------------------------------------------------------------
CREATE TABLE shows (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    screen_id BIGINT NOT NULL REFERENCES screens(id) ON DELETE CASCADE,
    movie_id BIGINT NOT NULL REFERENCES movies(id) ON DELETE RESTRICT,
    show_date DATE NOT NULL,
    start_time TIME WITHOUT TIME ZONE NOT NULL,
    end_time TIME WITHOUT TIME ZONE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_screen_show_schedule UNIQUE (screen_id, show_date, start_time),
    CONSTRAINT chk_show_time_order CHECK (end_time > start_time)
);

-- ----------------------------------------------------------------------------
-- 5. Physical Seats Table
-- Represents physical, static seats in an auditorium layout.
-- ----------------------------------------------------------------------------
CREATE TABLE seats (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    screen_id BIGINT NOT NULL REFERENCES screens(id) ON DELETE CASCADE,
    row_label VARCHAR(10) NOT NULL,
    seat_number INT NOT NULL CHECK (seat_number > 0),
    tier VARCHAR(20) NOT NULL CHECK (tier IN ('SILVER', 'GOLD', 'RECLINER')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_screen_row_seat UNIQUE (screen_id, row_label, seat_number)
);

-- ----------------------------------------------------------------------------
-- 6. Show Seats Table (Runtime Seat Inventory & Concurrency Locking)
-- Represents runtime state and price of a seat for a specific show.
-- Pre-materialized on show creation to support high-throughput row locking.
-- ----------------------------------------------------------------------------
CREATE TABLE show_seats (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    show_id BIGINT NOT NULL REFERENCES shows(id) ON DELETE CASCADE,
    seat_id BIGINT NOT NULL REFERENCES seats(id) ON DELETE CASCADE,
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE' CHECK (status IN ('AVAILABLE', 'HELD', 'BOOKED')),
    hold_expires_at TIMESTAMPTZ,
    held_by_user_id VARCHAR(64),
    booking_id BIGINT,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_show_seat UNIQUE (show_id, seat_id)
);

-- ----------------------------------------------------------------------------
-- 7. Bookings Table (Orders)
-- Represents confirmed or pending customer reservation orders.
-- ----------------------------------------------------------------------------
CREATE TABLE bookings (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    booking_reference VARCHAR(64) NOT NULL UNIQUE,
    user_id VARCHAR(64) NOT NULL,
    show_id BIGINT NOT NULL REFERENCES shows(id) ON DELETE RESTRICT,
    total_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (total_amount >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'EXPIRED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Add foreign key from show_seats back to bookings
ALTER TABLE show_seats
    ADD CONSTRAINT fk_show_seats_booking FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE SET NULL;

-- ----------------------------------------------------------------------------
-- 8. Booking Items Table (Junction Table)
-- Associates individual show seats to a confirmed booking.
-- Strict UNIQUE constraint on show_seat_id guarantees zero double bookings!
-- ----------------------------------------------------------------------------
CREATE TABLE booking_items (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    booking_id BIGINT NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    show_seat_id BIGINT NOT NULL REFERENCES show_seats(id) ON DELETE RESTRICT,
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_booking_show_seat UNIQUE (show_seat_id)
);

-- ----------------------------------------------------------------------------
-- 9. Payment Webhook Events Table (Idempotency Ledger)
-- Records asynchronous gateway webhooks for durable idempotent processing.
-- ----------------------------------------------------------------------------
CREATE TABLE payment_webhook_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    event_id VARCHAR(128) NOT NULL,
    booking_reference VARCHAR(64) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'RECEIVED' CHECK (status IN ('RECEIVED', 'PROCESSED', 'FAILED', 'IGNORED')),
    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMPTZ,
    CONSTRAINT uq_provider_event UNIQUE (provider, event_id)
);

-- ============================================================================
-- PERFORMANCE & CONCURRENCY INDEXES
-- ============================================================================

-- 1. Accelerates P2 listing query: filter shows by theatre and date
CREATE INDEX idx_screens_theatre ON screens(theatre_id, id);
CREATE INDEX idx_shows_screen_date ON shows(screen_id, show_date, start_time);
CREATE INDEX idx_shows_date ON shows(show_date);
CREATE INDEX idx_shows_movie ON shows(movie_id);

-- 2. Accelerates physical layout retrieval per screen
CREATE INDEX idx_seats_screen ON seats(screen_id, row_label, seat_number);

-- 3. Accelerates real-time seat availability maps and atomic hold locks
CREATE INDEX idx_show_seats_show_status ON show_seats(show_id, status);

-- 4. Partial index for background hold reaper daemon (scans only active holds)
CREATE INDEX idx_show_seats_active_holds ON show_seats(hold_expires_at)
    WHERE status = 'HELD';

-- 5. Accelerates booking lookups by user and public reference code
CREATE INDEX idx_bookings_user ON bookings(user_id, status);
CREATE INDEX idx_bookings_reference ON bookings(booking_reference);

-- 6. Accelerates webhook lookup by customer booking reference
CREATE INDEX idx_payment_webhooks_booking_ref ON payment_webhook_events(booking_reference);
