# Domain Glossary: High-Concurrency Booking Engine

This document defines the core domain terms and entities used across the booking engine architecture, database schema, and concurrency control mechanisms.

---

### Core Entities & Concepts

#### 1. Theatre
A physical cinema complex or venue containing one or more auditoriums (screens).
- *Attributes*: `id`, `name`, `city`, `address`, `created_at`.

#### 2. Screen / Auditorium
A distinct projection hall within a theatre that has a fixed seating layout and capacity.
- *Attributes*: `id`, `theatre_id`, `screen_number`, `name`, `total_seats`.

#### 3. Movie / Event
The entertainment title or event being exhibited.
- *Attributes*: `id`, `title`, `duration_minutes`, `language`, `genre`, `rating`.

#### 4. Show (Screening)
A specific screening of a movie at a specific screen, on a specific date, starting at a specific time.
- *Attributes*: `id`, `screen_id`, `movie_id`, `show_date`, `start_time`, `end_time`.

#### 5. Seat
A physical seat within an auditorium, characterized by row, number, and seating tier/type.
- *Attributes*: `id`, `screen_id`, `row_label`, `seat_number`, `tier` (e.g., SILVER, GOLD, RECLINER).

#### 6. ShowSeat (Seat Inventory)
The materialization or status mapping of a specific physical seat for a specific show. Represents the runtime availability state of that seat.
- *Attributes*: `id`, `show_id`, `seat_id`, `price`, `status` (`AVAILABLE`, `HELD`, `BOOKED`), `version` (for optimistic locking / row tracking).

#### 7. SeatHold (Timed Hold / Lock)
A temporary reservation placed on one or more seats by a user initiating checkout.
- *Attributes*: `id`, `show_seat_id`, `user_id`, `held_at`, `expires_at`, `status` (`ACTIVE`, `RELEASED`, `CONVERTED`).
- *Invariants*: Automatically expires after a defined duration (e.g., 8–10 minutes) if not converted to a confirmed booking.

#### 8. Booking (Reservation)
A confirmed, paid ticket order comprising one or more seats for a show.
- *Attributes*: `id`, `booking_reference`, `user_id`, `show_id`, `total_amount`, `status` (`PENDING`, `CONFIRMED`, `CANCELLED`, `EXPIRED`), `created_at`, `updated_at`.

#### 9. BookingItem
The junction entity associating a confirmed booking with the individual `ShowSeat` records.
- *Attributes*: `id`, `booking_id`, `show_seat_id`, `price`.

#### 10. PaymentWebhookEvent (Idempotency Ledger)
An audit log of inbound asynchronous payment notifications received from payment gateways (e.g., Stripe, Razorpay).
- *Attributes*: `id`, `provider`, `event_id`, `booking_reference`, `event_type`, `payload`, `status` (`RECEIVED`, `PROCESSED`, `IGNORED`, `FAILED`), `received_at`.
- *Invariants*: Enforces idempotency via unique `(provider, event_id)` constraints to safely handle duplicates, retries, and out-of-order deliveries.

---

### Concurrency Concepts

- **Double-Booking**: An integrity failure where two distinct users are granted confirmed reservations for the same seat in the same show.
- **Lost Hold**: A failure mode where a seat remains in a locked/held state indefinitely due to client drop-off, network error, or missing expiration enforcement.
- **Pessimistic Row Lock (`FOR UPDATE`)**: Database engine lock acquired on candidate rows during a transaction, serializing competing booking requests.
- **Atomic Conditional Update**: A single SQL statement (`UPDATE ... WHERE status = 'AVAILABLE' OR (status = 'HELD' AND expires_at < NOW())`) that atomically claims a seat without application-level race conditions.
- **Idempotency Key**: A unique identifier sent by payment gateways that guarantees identical processing across repeated webhook transmissions.
