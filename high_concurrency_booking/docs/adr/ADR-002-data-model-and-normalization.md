# ADR 002: Relational Data Model and Normalization (1NF–BCNF)

## Status
Accepted (Settled in Round 1)

## Context
A high-concurrency booking engine requires a relational schema that enforces domain integrity, eliminates update/insertion/deletion anomalies, and ensures fast index-backed queries under heavy read/write concurrency.

## Decision
We adopt a fully normalized relational schema conforming to 1NF, 2NF, 3NF, and BCNF:

1. **Theatres (`theatres`)**: Primary venue entity (`id`, `name`, `city`, `address`, `created_at`).
2. **Screens (`screens`)**: Physical auditoriums within a theatre (`id`, `theatre_id`, `screen_number`, `name`, `total_seats`).
3. **Movies (`movies`)**: Metadata for films/events (`id`, `title`, `duration_minutes`, `language`, `genre`, `release_date`).
4. **Shows (`shows`)**: Specific screening instances (`id`, `screen_id`, `movie_id`, `show_date`, `start_time`, `end_time`).
   - *Normalization*: BCNF compliant. `theatre_id` is omitted because it is transitively dependent through `screen_id`.
5. **Physical Seats (`seats`)**: Static layout of an auditorium (`id`, `screen_id`, `row_label`, `seat_number`, `tier`).
6. **Show Seat Inventory (`show_seats`)**: Runtime state per show and seat (`id`, `show_id`, `seat_id`, `price`, `status`, `hold_expires_at`, `held_by_user_id`, `booking_id`).
   - Unique constraint on `(show_id, seat_id)`.
7. **Bookings (`bookings`)**: Order header for confirmed transactions (`id`, `booking_reference`, `user_id`, `show_id`, `total_amount`, `status`, `created_at`).
8. **Booking Items (`booking_items`)**: Line items mapping seats to bookings (`id`, `booking_id`, `show_seat_id`, `price`).
9. **Payment Webhook Events (`payment_webhook_events`)**: Durable idempotency log (`id`, `provider`, `event_id`, `booking_reference`, `event_type`, `payload`, `status`, `received_at`).

## Normalization Justifications
- **1NF**: All columns contain atomic, scalar values. No repeating groups or array attributes.
- **2NF**: All non-key attributes are fully functionally dependent on the primary key (no partial dependencies on composite keys).
- **3NF**: No transitive functional dependencies exist (e.g., theatre details are accessed via foreign key to `screens`, not duplicated on `shows`).
- **BCNF**: Every determinant is a superkey / candidate key across all tables.

## Consequences
- Clean separation between static venue/layout configuration and dynamic runtime show inventory.
- High indexing efficiency with composite foreign keys and covering indexes.
