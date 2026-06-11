# ADR 0001 — API versioning + view/serializer location

Date: 2026-06-11
Status: accepted

## Context

The project ships a REST API consumed by a web frontend and (eventually)
mobile clients. Three decisions had to be made together:

1. How to version the API.
2. Where view + serializer code lives — per-version under
   `interfaces/rest/v<N>/...`, or at the app root and referenced from
   the version's URL conf.
3. Which OpenAPI generator to standardize on.

## Decision

**1. URL-based versioning.** Every public endpoint mounts under `/api/v<N>/`.
`v1` is the current major. Breaking changes ship under a new `vN+1`
path; both run side-by-side during the deprecation window.

**2. Views + serializers stay at `apps/<x>/views.py` and
`apps/<x>/serializers.py`.** The version's url conf
(`interfaces/rest/v1/urls.py`) includes each app's existing url module.

  Rationale: most apps will not need to fork views across versions.
  Forking per-version creates dead branches that drift. When a breaking
  change is genuinely needed, copy the affected views into
  `interfaces/rest/v2/handlers/<app>.py` and point that version's url
  conf at the fork. Apps that never break stay shared.

**3. `drf-spectacular` is the OpenAPI generator.** Output is exposed at
`/api/v1/schema/`, `/api/v1/docs/` (Swagger UI), `/api/v1/redoc/`.

  Legacy `@swagger_auto_schema` decorators from `drf-yasg` remain in
  place — spectacular ignores them and auto-discovers from serializers
  and type hints. They are replaced with `@extend_schema` opportunistically
  during ordinary feature work, not as a coordinated sweep.

## Consequences

- `/api/v1/...` is the only public path. Old flat paths (`/escrow/...`,
  `/projects/...`, `/payments/...`, `/api/account/...`) 301-redirect for
  one release window, then are removed.
- Webhook endpoints stay at `/webhooks/<provider>/` and are NOT
  versioned. External providers configure those URLs in their dashboards
  and a version bump on our side would break delivery.
- Adding a new endpoint = edit the app's `urls.py`. It appears under
  `/api/v1/...` automatically via `interfaces.rest.v1.urls`.
- When a contract change requires `v2`: copy the affected views to a
  forked location, leave `v1` views untouched, add a row to this ADR's
  changelog noting the cutover date.
