# ADR 0002 — Locking discipline + state machine for financial transitions

Date: 2026-06-11
Status: accepted

## Context

Concurrent requests can hit the same `EscrowTransaction` row through
multiple paths: user-initiated release, retry of an in-flight task, or a
re-delivered webhook. Two failure modes we cannot tolerate:

- Balance going negative or being released twice (lost-update race).
- Statuses changing in an order that's invalid (e.g. `pending_funding ->
  released` skipping `funded`).

The first phase of the codebase used `transaction.atomic()` ad-hoc with
no row-level locking and direct `escrow.status = '...'` assignments. The
discipline was implicit and easy to break.

## Decision

**Every state-mutating method on a financial model goes through
`@atomic_with_lock(model=..., lookup=..., inject_as=...)`** (defined in
`common/decorators/atomic_with_lock.py`). The decorator opens a
`transaction.atomic()` block, runs `select_for_update()` on the target
row keyed by the named lookup, and injects the locked instance into the
method.

**Every status change goes through `StateMachine.transition()`** (defined
in `common/patterns/state_machine.py`). Each app declares its own table:

- `apps/escrow/domain/state_machine.py::ESCROW_FSM`
- `apps/payments/domain/state_machine.py::PAYMENT_FSM`
- `apps/disputes/domain/state_machine.py::DISPUTE_FSM`

Disallowed transitions raise `InvalidTransition` with structured
`details` (from, to, allowed). Direct `obj.status = '...'` is a
regression.

**Pre-debit pattern for outbound flows.** For `release_funds` and `refund`:

1. Lock the escrow row.
2. Validate invariants (balance, lock flag, milestone state).
3. Debit `current_balance` and create the `Payment(pending)` row inside
   the lock.
4. Release the lock by exiting the atomic block.
5. Call the external provider with no lock held.
6. On `ProviderError`, a compensating method re-locks the row and
   restores the balance + walks the status back.

External HTTP NEVER happens inside the lock.

## Consequences

- The race-condition test (`tests/integration/test_race_release.py`)
  proves two concurrent `release_funds` calls serialize correctly.
- `select_for_update()` is a no-op on SQLite. `config.settings.testing`
  always reuses Postgres via `DATABASE_URL`; the rule is "no SQLite for
  anything that touches a financial table".
- New financial methods MUST follow the same pattern. PRs that skip
  `@atomic_with_lock` or set `status` directly should be rejected at
  review.
- `select_for_update().select_related("<nullable_fk>")` fails on Postgres
  (no FOR UPDATE on outer joins). Use `of=("self",)` to scope the lock to
  the primary table.
