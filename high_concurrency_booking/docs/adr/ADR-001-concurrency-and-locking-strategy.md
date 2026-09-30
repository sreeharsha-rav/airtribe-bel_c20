# ADR 001: High-Concurrency Seat Locking and Hold Management Strategy

## Status
Accepted (Settled in Round 1)

## Context
In a BookMyShow-scale ticketing engine, thousands of users compete for high-demand seats simultaneously during burst events (e.g., ticket drops, blockbusters). The system must guarantee:
1. Zero double-booking of seats under any concurrency load.
2. Zero lost holds (abandoned or crashed user checkout flows must never lock seats indefinitely).
3. Fast seat availability and show listing lookups under read-heavy traffic.
4. Robust, idempotent payment confirmation via retried/duplicated webhooks.

## Decision Drivers
- ACID consistency and isolation guarantees at the database tier.
- Low contention and latency under bursts.
- Resilience against crashed workers or lost network requests.
- Portability and verifiability with load testing scripts.

## Considered Options
1. **Option 1: Distributed Lock via Redis TTL + Lazy Sync**
   - *Pros*: Fast in-memory operations, native TTL keys.
   - *Cons*: Two-phase state coordination between Redis and RDBMS risks dual-write inconsistency, split-brain, and ghost holds if Redis expires before DB confirms.
2. **Option 2: Pessimistic Row Locking (`SELECT ... FOR UPDATE`) in RDBMS**
   - *Pros*: Strict ACID semantics; prevents concurrent reads from reading uncommitted holds.
   - *Cons*: Long transaction holding times can cause lock contention or deadlock cascades under high concurrency.
3. **Option 3: Hybrid Atomic Conditional Update + Lazy Hold Expiration (Recommended)**
   - Atomic SQL conditional update:
     `UPDATE show_seats SET status = 'HELD', hold_expires_at = NOW() + INTERVAL '10 minutes', user_id = :user_id WHERE id = :seat_id AND (status = 'AVAILABLE' OR (status = 'HELD' AND hold_expires_at < NOW()))`
   - Paired with an explicit partial unique index on active bookings (`WHERE status = 'CONFIRMED'`) to make double-booking mathematically impossible at the database engine level.
   - Hold expiry is evaluated inline during read/hold queries (lazy evaluation), supplemented by a lightweight background cleanup daemon for state hygiene.

## Consequences
- Single source of truth in the relational database.
- Completely avoids distributed consensus overhead.
- Read operations (`P2` show listing and seat maps) do not lock rows.
- Full verification can be performed with concurrent SQL client threads.
