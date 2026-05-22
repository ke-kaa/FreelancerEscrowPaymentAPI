# Disputes App

## Overview
The `disputes` Django app manages project dispute lifecycles between clients, freelancers, and moderators. It exposes RESTful endpoints for filing disputes, viewing and moderating them, updating dispute details, and resolving or deleting disputes. The app integrates tightly with:

- `user_projects` for project ownership, status transitions, and permissions.
- `accounts` for user authentication and group-based moderation roles.
- `escrow` for locking and unlocking escrow transactions when disputes are opened, resolved, or deleted.

## Core Responsibilities
- Allow eligible users (clients or assigned freelancers) to open disputes against projects.
- Provide role-aware access to list, view, and moderate disputes.
- Update project and escrow state atomically when dispute statuses change.
- Support deletion of open disputes by their creator, restoring related project/escrow state.

## Application Structure

| Module | Purpose |
| ------ | ------- |
| `models.py` | Defines `Dispute` (one-to-one with `UserProject`) and `DisputeMessage` for threaded communication. |
| `serializers.py` | Houses serializers for creating, retrieving, moderator updates, and participant edits. Includes escrow lock/unlock logic during status transitions. |
| `views.py` | Provides DRF class-based views for dispute CRUD operations with authentication, authorization, and Swagger documentation. |
| `permissions.py` | Custom permission classes (`IsModerator`, `IsDisputeParticipantOrModerator`, `IsDisputeOwner`) enforce role-based access. |
| `tests.py` | Placeholder for unit/integration tests (needs implementation). |

## Endpoints
_All endpoints require JWT authentication and live under the API router that includes the disputes app._

| Endpoint | Method | Description | Serializer |
| -------- | ------ | ----------- | ---------- |
| `/projects/{project_id}/disputes/` | POST | Create a dispute for the specified project. | `DisputeCreateSerializer` |
| `/disputes/` | GET | List disputes; moderators/admins see all, participants see their own. Supports filtering (`status`, `dispute_type`) and ordering. | `DisputeDetailSerializer` |
| `/disputes/{id}/` | GET | Retrieve a single dispute. | `DisputeDetailSerializer` |
| `/disputes/{id}/moderator/` | PUT/PATCH | Moderator updates to status/resolution. | `ModeratorDisputeUpdateSerializer` |
| `/disputes/{id}/` | PUT/PATCH | Dispute owner updates type/reason while dispute is open. | `UpdateDisputeSerializer` |
| `/disputes/{id}/` | DELETE | Dispute owner deletes an open dispute; restores project and unlocks escrow. | — |

Swagger annotations (via `drf-yasg`) provide detailed OpenAPI documentation, including request bodies, query parameters, and response schemas.

## Escrow Integration
- Opening a dispute locks the related `EscrowTransaction` and sets its status to `disputed` to halt fund movement.
- Moderator resolutions or owner deletions unlock the escrow and restore a non-disputed status (`funded` or `pending_funding`, depending on balance).
- Project status transitions mirror dispute state (`active` ↔ `disputed`).

## Permissions & Throttling
- **Participants** (client or assigned freelancer) can file, view, and update their own disputes.
- **Moderators** (users in the `Moderators` group) can view and update all disputes.
- **Owners** (dispute creators) can edit/delete only while status is `open`.
- Throttling is not yet implemented and should follow platform guidelines (see Future Improvements).

## Testing
`disputes/tests.py` currently lacks coverage; tests should exercise:
- Permission enforcement across roles.
- Dispute creation edge cases (duplicate, invalid project state).
- Moderator status transitions and escrow unlocks.
- Deletion logic ensuring project/escrow state restoration.

Run tests (once implemented) with:
```bash
python manage.py test disputes
```

## Future Improvements
- Extract escrow lock/unlock and notification side effects into dedicated services (or Celery tasks) so serializers remain focused on validation.
- Implement dispute messaging endpoints leveraging `DisputeMessage` for threaded conversations, with pagination and permissions.
- Add structured logging and rate limiting around dispute creation/update endpoints to monitor and prevent abuse.
- Provide a robust test suite covering creation, moderation flows, status transitions, and escrow interactions.
- Enhance moderator/admin dashboards (e.g., Django admin actions) for bulk dispute handling and reporting.
- Consider adding WebSocket/notification hooks to keep participants informed in real time.

## Contribution Guidelines
- Maintain transactional integrity when modifying dispute, project, and escrow models together.
- Keep permissions explicit; add new roles via `permissions.py` where necessary.
- Ensure Swagger docs stay in sync with request/response payloads.
- Mirror changes in interfaces (serializers/views) with updates to tests and documentation.
