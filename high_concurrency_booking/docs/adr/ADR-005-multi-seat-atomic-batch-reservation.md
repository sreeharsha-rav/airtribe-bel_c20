# ADR 005: Multi-Seat Atomic Batch Reservation Semantics

## Status
Accepted (Settled in Round 2)

## Context
Cinema tickets are rarely bought individually; users typically reserve 2–6 contiguous seats simultaneously. If some seats in the selected batch are available but one is claimed concurrently by another user, the reservation could either fail completely or partially succeed.

## Decision
We enforce **All-or-Nothing Atomic Batch Holds**:
- Seat reservation queries execute an atomic update targeting the entire set of requested seat IDs:
  ```sql
  UPDATE show_seats
  SET status = 'HELD', hold_expires_at = NOW() + INTERVAL '10 minutes', held_by_user_id = :uid
  WHERE id IN (:seat_ids)
    AND (status = 'AVAILABLE' OR (status = 'HELD' AND hold_expires_at < NOW()));
  ```
- Application/transaction layer checks the number of affected rows.
- If `affected_rows != requested_seat_count`, the transaction immediately aborts/rolls back, releasing all held seats in the batch and returning a conflict error to the client.

## Consequences
- Guaranteed fair booking mechanics without orphaned or fragmented seat islands.
- Clean transactional rollback without dangling locks.
- Better user experience: users do not end up paying for half a party's seats.
