# Accounts App

## Overview
The `accounts` Django app powers user management for the Freelancer Escrow Payment API. It handles registration, authentication, profile management, password workflows, soft deletion, and reactivation. The app is built on Django REST Framework (DRF) and integrates with `djangorestframework-simplejwt` for JWT-based authentication, `drf-yasg` for OpenAPI documentation, and Django's standard authentication primitives.

## Key Responsibilities
- Issue and refresh JWT access tokens for verified users.
- Register new clients and freelancers while enforcing password policies.
- Allow authenticated users to view and update their profile information.
- Support password-change and password-reset flows with email notifications.
- Soft-delete accounts, blacklist refresh tokens, and allow reactivation via email links.
- Provide administrative listing endpoints with search, filter, and ordering capabilities.

## Application Structure

| Module | Purpose |
| ------ | ------- |
| `models.py` | Defines the `CustomUser` model with email-based authentication, user types, audit logging, and soft-delete tracking. Includes `CustomUserManager` and `ActiveUserManager`. |
| `serializers.py` | Validates request payloads for authentication, profile, password, deletion, and reactivation workflows, including Django password validator integration and detailed error messaging. |
| `views.py` | Exposes DRF generic views for the account endpoints, including Swagger documentation, throttling, and header-based token handling. |
| `permissions.py` | Contains custom permission classes, such as `CanReactivate`, to gate sensitive actions. |
| `throttles.py` | Provides throttling classes (e.g., email rate limiting) to mitigate abuse of email-driven workflows. |
| `pagination.py` | Implements `UserListPagination` for paginated admin listings. |
| `utils.py` | Houses helpers for generating password reset and reactivation links and sending the corresponding emails. |

## HTTP Endpoints

| Endpoint | Method | Purpose | Serializer |
| -------- | ------ | ------- | ---------- |
| `/auth/token/` | POST | Obtain access and refresh JWT tokens for a user. | `CustomTokenObtainPairSerializer` |
| `/auth/register/` | POST | Create a new user account and return JWT credentials. | `RegistrationSerializer` |
| `/auth/profile/` | GET/PUT/PATCH | Retrieve or update the authenticated user's profile. | `UserProfileSerializer` |
| `/auth/change-password/` | POST | Change the authenticated user's password. | `ChangePasswordSerializer` |
| `/auth/logout/` | POST | Blacklist the provided refresh token and end the session. | — |
| `/auth/password-reset/` | POST | Send a password reset email. | `PasswordResetRequestSerializer` |
| `/auth/password-reset/confirm/` | POST | Confirm a password reset using UID and token. | `PasswordResetConfirmSerializer` |
| `/users/` | GET | List users with admin-only access, including filtering, search, and ordering. | `UserListSerializer` |
| `/users/delete/` | PATCH | Soft-delete the authenticated user's account and optionally blacklist the refresh token. | `UserDeleteSerializer` |
| `/reactivation/` | POST | Request a reactivation email for a soft-deleted account (subject to throttling). | `ReactivationRequestSerializer` |
| `/reactivation/confirm/` | POST | Reactivate a soft-deleted account using UID and token, returning fresh JWTs. | `AccountReactivationConfirmSerializer` |

Swagger/OpenAPI metadata is provided through `drf_yasg`, giving consumers interactive documentation with explicit request/response schemas and header requirements.

## Authentication & Security Highlights
- Email is the unique identifier; usernames are not used.
- All password entry points run through Django's password validators to ensure strong credentials.
- Sensitive workflows (change password, delete account) require optional refresh-token headers for additional session security.
- Throttles (anonymous and user-specific) protect password-reset and reactivation endpoints.
- Audit logging via `django-auditlog` tracks user model changes.

## Email Workflows
Password reset and account reactivation flows rely on helpers in `utils.py` to:
1. Generate time-bound, signed URLs using Django's token mechanisms.
2. Send transactional emails with context-specific templates.
3. Enforce one-time tokens by storing state in JWT blacklists or user timestamps.

## Testing
The endpoints were tested manually.
Tests live in `accounts/tests.py` and should cover:
- Serializer validation (positive and negative cases).
- Authentication and authorization checks across views.
- Token handling (refresh, blacklist, reissue).
- Email triggers and throttling.

Run the current suite with
```bash
python manage.py test accounts
```

## Future Improvements
- Move token blacklisting and outbound email side effects in `views.py` into dedicated services or Celery tasks so views remain thin and behaviour can be reused across apps.
- Add comprehensive tests in `accounts/tests.py` that cover password reset/reactivation happy paths, throttling behavior, and negative scenarios to reduce reliance on manual testing.
- Enhance admin tooling by exposing `active_objects` via custom manager helpers or Django admin actions for fast restores, and define pagination defaults (page size and max) in `UserListPagination` to guard against large query responses.

## Related Configuration
Key configuration entries for the app are located in `escrow_api/settings.py`:
- JWT settings for `rest_framework_simplejwt`.
- Email backend configuration for sending reset/reactivation links.
- Throttling rates and pagination defaults.
- Installed apps and middleware entries for DRF, Swagger, audit logging, and custom middleware.

## Contribution Notes
When extending the app:
- Prefer DRF generic views and serializers to keep logic declarative and testable.
- Ensure Swagger decorators accurately reflect headers, query params, and request bodies.
- Log unexpected conditions with the module-level logger instead of swallowing exceptions.
- Update tests alongside code changes to keep coverage accurate and prevent regressions.
