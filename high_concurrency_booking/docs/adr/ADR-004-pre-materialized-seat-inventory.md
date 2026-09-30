# ADR 004: Pre-Materialized Show Seat Inventory

## Status
Accepted (Settled in Round 2)

## Context
When a show screening is scheduled in an auditorium with 250 seats, the engine must manage seat availability under high-concurrency user traffic. Two primary patterns exist:
1. Pre-materialized inventory (`show_seats` table populated upon show creation).
2. Sparse dynamic holds (records created only when held, free seats derived via `LEFT JOIN`).

## Decision
We adopt **Pre-Materialized Show Seat Inventory** (`show_seats`):
- For each scheduled show, a batch insert creates one row per physical seat with `status = 'AVAILABLE'`.
- Row-level atomic conditional updates (`UPDATE show_seats SET status = 'HELD' ... WHERE id = :id AND ...`) allow zero phantom reads without table locks.
- Seat map queries are simple: `SELECT * FROM show_seats WHERE show_id = :show_id`.

## Consequences
- Eliminates phantom-read race conditions during concurrent holds.
- Enables direct row updates and localized locking.
- Increases storage by a predictable, small amount (e.g., 250 rows per screening).
