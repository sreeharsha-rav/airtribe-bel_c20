# ADR 003: Payment Webhook Idempotency and State Transition Management

## Status
Accepted (Settled in Round 1)

## Context
Payment gateways deliver asynchronous webhook events to notify the booking engine of payment success, failure, or refund. Webhook deliveries frequently experience:
- Duplicate deliveries due to gateway retry policies.
- Out-of-order arrivals (e.g., refund webhook arriving before payment confirmation).
- Network timeouts where the gateway does not receive an ACK in time.

## Decision
1. **Durable Webhook Event Ledger**:
   - Create a dedicated table `payment_webhook_events`.
   - Enforce a strict compound unique constraint on `(provider, event_id)`.
2. **Idempotent Ingestion Protocol**:
   - Inbound webhook payloads are recorded atomically using `INSERT ... ON CONFLICT (provider, event_id) DO NOTHING`.
   - If an event is already marked `PROCESSED`, the handler returns HTTP 200 OK immediately without altering database state.
3. **Atomic Booking State Transition**:
   - Within an isolated transaction:
     - Verify booking status is `PENDING` / `HELD`.
     - Update booking status to `CONFIRMED`.
     - Update associated `show_seats` records from `HELD` to `BOOKED`.
     - Set webhook event status to `PROCESSED`.
   - If the booking hold has expired prior to payment confirmation, trigger an automated refund/reconciliation flow.

## Consequences
- Guaranteed idempotency regardless of gateway retry behavior.
- Complete audit trail of all financial event payloads.
- Financial integrity preserved against double-charge and double-booking race conditions.
