# ADR 0003 — Central webhook ingress + hash-chained audit ledger

Date: 2026-06-11
Status: accepted

## Context

Webhook handling was originally split across `apps/payments/views.py`
with one ad-hoc view per provider. Each reimplemented idempotency
differently, Stripe skipped signature verification, and Chapa had no
verification at all. Business logic (Payment + Escrow row mutations) ran
synchronously in the request path.

Two demands competed:

1. Replay safety + signature verification need to happen at the very
   edge, before any business logic.
2. The ledger of every state transition needs to be append-only and
   tamper-evident, since this is a financial system.

## Decision

**`apps/webhooks/` is the only entry point for inbound webhooks.**

Pipeline:

1. Read `request.body` (raw bytes).
2. Call the integration adapter's `verify_webhook(payload, signature)`
   — Stripe's `construct_event` or Chapa's HMAC-SHA256 with
   constant-time compare. Failure -> 400 `ProviderError`.
3. Insert a `WebhookEvent` row with `unique(provider, external_event_id)`
   inside a savepoint. Duplicate delivery hits the constraint, returns
   200 `{status: "duplicate"}`, no re-enqueue.
4. Enqueue `process_webhook_event.delay(id)` and return 200.

The Celery task — NOT the request path — runs the provider-specific
handler (`apps/webhooks/handlers/stripe.py`, `chapa.py`) which routes to
`EscrowService` methods. All DB mutations happen in the task.

**`apps/audit/` holds the hash-chained ledger.**

`TransactionLog` rows have `prev_hash` pointing to the previous row's
`current_hash`. `current_hash` is SHA-256 over (prev_hash, actor,
action, target_type, target_id, before, after, timestamp). Tampering
breaks the chain at the modified row — `audit.services.verify_chain()`
walks the ledger and returns the first break id.

Signals on `EscrowTransaction`, `Payment`, `Dispute` append a row
whenever `status`, `is_locked`, or `current_balance` changes.
`django-auditlog` is registered for the same models to capture row-level
field diffs.

## Consequences

- External providers configure ONE URL per environment
  (`/webhooks/<provider>/`). No version prefix — these are not part of
  the public API contract and a version bump on our side would break
  delivery.
- Webhook handlers run async; any 5xx in handler logic does not return
  to the provider, so providers do not retry on transient business
  errors. Celery retries handle that path internally.
- The audit ledger is append-only. Admin views are read-only (no add /
  change / delete). Migrations must never `RunSQL` against
  `audit_transactionlog`.
- Hash chain verification is O(n) — fine for periodic integrity sweeps,
  not for hot paths.
- Audit signal failures are swallowed in the receiver so a logging
  exception cannot break the originating financial save.
