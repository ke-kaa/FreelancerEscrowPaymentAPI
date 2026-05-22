# Escrow App

## Overview
The `escrow` Django app manages the lifecycle of project escrow transactions for the Freelancer Escrow Payment API. It provides REST endpoints and service utilities to fund, lock, release, refund, and audit escrow balances linked to `user_projects`. The app integrates with the `payments` domain for provider interactions and with the `disputes` app to lock funds whenever a dispute is opened.

## Core Responsibilities
- Maintain escrow transactions (`EscrowTransaction`) associated with projects and track funded amounts, balance, status, and locking state.
- Initiate funding flows and verify provider callbacks through `EscrowService`, delegating to payment providers via the `payments` app.
- Release funds to freelancers (full or partial, milestone-aware) while managing platform commissions.
- Handle refunds back to clients and react to dispute events by locking/unlocking escrows.
- Expose API endpoints for listing, retrieving, releasing, and administratively locking escrows.

## Application Structure

| Module | Purpose |
| ------ | ------- |
| `models.py` | Declares the `EscrowTransaction` model with project relation, monetary fields, status, and locking flag. |
| `serializers.py` | Serializers for escrow summaries, release requests, and lock toggles. Validates release amounts against current balances. |
| `services.py` | `EscrowService` encapsulates funding, verification, release, refund, and dispute orchestration, working with the `payments` and `disputes` apps. |
| `views.py` | DRF API views for listing/retrieving escrows, releasing funds, and toggling locks. Swagger docs describe request/response schemas. |
| `urls.py` | Route definitions for escrow endpoints. |
| `tests.py` | Placeholder for automated tests (requires implementation). |

## API Endpoints

| Endpoint | Method | Description | Serializer |
| -------- | ------ | ----------- | ---------- |
| `/escrows/` | GET | List escrows relevant to the authenticated user (staff see all). | `EscrowTransactionSerializer` |
| `/escrows/{id}/` | GET | Retrieve a specific escrow with project, participant, and payment details. | `EscrowTransactionSerializer` |
| `/escrows/{id}/release/` | POST | Release funds to the freelancer (amount optional, defaults to full balance). | `EscrowReleaseSerializer` |
| `/escrows/{id}/lock/` | PATCH | Admin-only lock/unlock toggle for the escrow. | `EscrowLockSerializer` |

> **Note:** Funding initiation, verification, refunds, and dispute resolution hooks are orchestrated via `EscrowService` and the `payments` webhook flows and are not directly exposed as REST endpoints here.

## Key Workflows
- **Funding:** `EscrowService.initiate_funding` provisions a new `EscrowTransaction`, calculates commissions, and defers checkout to `PaymentService`. `verify_funding` finalizes state after provider confirmation.
- **Releases:** `release_funds` handles milestone-aware payouts, commission deductions, provider transfers, and creates payment ledger entries. `verify_transfer_to_freelancer` reconciles asynchronous provider callbacks.
- **Refunds:** `refund` issues client refunds via the original provider transaction and updates escrow balance/state accordingly.
- **Dispute Integration:** `open_dispute` and `resolve_dispute` lock/unlock escrows and update project status, ensuring funds stay frozen while disputes are active.

## Security & Permissions
- API endpoints validate user roles (client/freelancer/staff) before exposing escrow data or releasing funds.
- Escrow locking prevents releases or refunds during disputes or manual reviews.
- Sensitive operations (release/lock) rely on JWT-authenticated requests and admin permissions where required.

## Testing
`escrow/tests.py` currently lacks coverage. Future tests should include:
- Funding, release, and refund service paths (happy and failure scenarios).
- Permission enforcement for list/detail/release endpoints.
- Concurrency edge cases (double release, double refund, locked escrow operations).
- Integration with disputes and payments (mock provider callbacks).

Run the suite once implemented with:
```bash
python manage.py test escrow
```

## Future Improvements
- Introduce a state machine or typed enum helpers for `EscrowTransaction.status` to enforce valid transitions and reduce string comparisons scattered across the service layer.
- Break down `EscrowService` into smaller domain services (funding, release, dispute, refund) or command handlers to improve maintainability and testability.
- Add asynchronous tasks (Celery) or webhooks listeners dedicated to provider callbacks to keep API responses fast and prevent blocking on external services.
- Expand automated tests across `EscrowService`, especially around partial releases, commission tracking, and failure rollbacks.
- Emit notifications/audit hooks (email, WebSocket, or logging) when escrow state changes, giving participants real-time insight.
- Implement optimistic locking or database-level constraints to guard against double releases when concurrent requests hit the same escrow.

## Contribution Guidelines
- Keep database operations involving payments, escrows, and projects wrapped in transactions to guarantee consistency.
- Update Swagger docs whenever request/response schemas change to maintain accurate public documentation.
- Mirror changes to service logic with corresponding tests and ensure error handling preserves atomicity.
- Coordinate with the `payments` and `disputes` teams when modifying shared workflows to avoid regressions across apps.
