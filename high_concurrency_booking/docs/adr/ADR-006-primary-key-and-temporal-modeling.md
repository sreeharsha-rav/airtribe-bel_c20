# ADR 006: Primary Key Strategy and Temporal Modeling

## Status
Accepted (Settled in Round 3)

## Context
High-concurrency database schemas require optimal primary key choices to minimize B-Tree index fragmentation and memory usage under intense write loads. Additionally, the temporal model must support rapid date-based filtering for requirement P2 while ensuring UTC precision for timed seat holds.

## Decision
1. **Identifier Strategy**:
   - Internal Primary Keys: Use `BIGINT GENERATED ALWAYS AS IDENTITY` (or `BIGSERIAL`) across all entity tables (`theatres`, `screens`, `movies`, `shows`, `seats`, `show_seats`, `bookings`, `booking_items`, `payment_webhook_events`).
     - *Advantage*: Compact 8-byte representation, sequential insertion pattern maximizes B-Tree page fill factor and buffer pool caching.
   - External Identifiers: The `bookings` table provides a distinct `booking_reference VARCHAR(64) UNIQUE` (e.g. `BK-20261001-9F3A`) used in customer-facing APIs and payment gateway metadata.
2. **Temporal Modeling**:
   - `shows.show_date`: Stored as `DATE` (`YYYY-MM-DD`). Allows direct equality filtering (`WHERE show_date = :selected_date`) leveraging standard B-Tree index scans without function-call index wrapping (`DATE(timestamp)`).
   - `shows.start_time` and `shows.end_time`: Stored as `TIME WITHOUT TIME ZONE` reflecting the auditorium's local schedule.
   - `show_seats.hold_expires_at`, `bookings.created_at`, `payment_webhook_events.received_at`: Stored as `TIMESTAMPTZ` (UTC) to guarantee timezone-agnostic timestamp comparisons across distributed application servers.

## Consequences
- Clean separation between internal performant integer keys and external secure booking identifiers.
- Optimal index scans for P2 show listing queries by date and theatre.
- Bulletproof lock expiration calculations using UTC microsecond timestamps.
