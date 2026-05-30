# Freelancer Escrow Payment Backend

Django + DRF backend for an escrow-based freelancer payment platform. Handles user accounts, projects/milestones, escrow lifecycle, dispute resolution, and payment provider integrations (Stripe, Chapa).

> Restructure in progress — see [`MIGRATION_PLAN.md`](../FreelancerEscrowPaymentAPI/MIGRATION_PLAN.md) and [`MIGRATION_TODO.md`](./MIGRATION_TODO.md) for current state.

---

## Stack

| Concern              | Choice                              |
|----------------------|-------------------------------------|
| Language             | Python 3.12+                        |
| Framework            | Django 6.x, Django REST Framework   |
| Database             | PostgreSQL (dev + prod)             |
| Task queue           | Celery + RabbitMQ broker            |
| Cache / results      | Redis                               |
| Auth                 | JWT (`djangorestframework-simplejwt`) |
| Payments             | Stripe, Chapa                       |
| Storage (prod)       | AWS S3 via `django-storages`        |
| Dependency manager   | [`uv`](https://docs.astral.sh/uv/) + `pyproject.toml` |

---

## Requirements

- Python 3.12+
- `uv` (`pipx install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- PostgreSQL 14+
- Redis 6+
- RabbitMQ 3.12+ (only when running Celery workers locally)

---

## Setup

```bash
git clone <repo>
cd FreelancerEscrowPaymentBackend

cp .env.example .env          # fill in SECRET_KEY, DATABASE_URL, provider keys

uv sync --group development   # install base + dev deps into .venv

uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

---

## Dependencies — `pyproject.toml` dependency-groups

We do **not** use a `requirements/` directory. All dependencies live in `pyproject.toml`, organized into one base list plus named groups managed by `uv`.

### Layout

```toml
[project]
dependencies = [...]          # runtime deps required in EVERY environment

[dependency-groups]
development = [...]           # dev-only: pytest, ruff, mypy, ipython, factory-boy
production  = [...]           # prod-only: gunicorn/uvicorn, sentry-sdk, django-storages[s3]
```

### Group purpose

| Group         | When installed                       | Contains                                            |
|---------------|--------------------------------------|-----------------------------------------------------|
| _(base)_      | always — every env                   | django, drf, celery client, psycopg, redis, stripe, requests, environ, simplejwt, auditlog, corsheaders, drf-yasg |
| `development` | local dev, CI test job               | pytest, pytest-django, factory-boy, responses, ruff, mypy, ipython |
| `production`  | prod Docker image, staging deploy    | gunicorn / uvicorn, sentry-sdk, django-storages[s3] |

### Install commands

```bash
uv sync                                            # base only
uv sync --group development                        # local dev
uv sync --group production                         # prod image build
uv sync --group development --group production     # everything (rarely needed)
uv sync --frozen                                   # CI — fail if uv.lock drifts
```

### Adding a dependency

```bash
uv add <pkg>                          # base
uv add --group development <pkg>      # dev-only
uv add --group production <pkg>       # prod-only
```

Then **commit `pyproject.toml` AND `uv.lock`** in the same commit.

### Upgrading

```bash
uv lock --upgrade-package <pkg>       # one package
uv lock --upgrade                     # everything (review diff carefully)
```

### Why not `requirements/*.txt`?

- One source of truth — `pyproject.toml` already declares the project metadata.
- `uv.lock` is a deterministic, cross-platform lockfile.
- Groups give us the dev/prod split without a separate file tree.

If you need a plain `requirements.txt` for a tool that can't read `pyproject.toml` (legacy CI, Heroku buildpack):

```bash
uv export --group production --no-hashes -o requirements.prod.txt
```

— do **not** commit the export. Generate on demand in the build step.

---

## Common commands

```bash
uv run python manage.py runserver           # dev server
uv run python manage.py check               # static checks
uv run python manage.py migrate             # apply migrations
uv run python manage.py makemigrations
uv run python manage.py shell

uv run celery -A config worker -l info      # worker
uv run celery -A config beat -l info        # scheduler

uv run pytest                               # tests
uv run ruff check .                         # lint
uv run ruff format .                        # format
uv run mypy src/                            # type-check
```

---

## Settings modules

| Module                        | When                                |
|-------------------------------|-------------------------------------|
| `config.settings.development` | local dev (default in `manage.py`)  |
| `config.settings.production`  | prod (set in `wsgi.py` / `asgi.py`) |
| `config.settings.testing`     | `pytest` — eager Celery, locmem cache |

Override via `DJANGO_SETTINGS_MODULE=config.settings.<name>`.

Hardening flags (HSTS, secure cookies, SSL redirect) live in `config.settings.security` and are imported only from `production.py`.

---

## Environment variables

See [`.env.example`](./.env.example) for the full list. Loaded by `django-environ` from the project root `.env` file.

Required in every environment: `SECRET_KEY`, `DATABASE_URL`.
Required in production: `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `AWS_*`.

---

## Project layout

```
src/
├── apps/              # Django apps (accounts, escrow, payments, projects, disputes, api)
├── common/            # cross-cutting: money, state machine, decorators, resilience, ...
├── config/            # settings split, urls, wsgi/asgi/celery
├── integrations/      # external provider adapters (stripe, chapa)
└── services/          # (reserved)

tests/                 # unit / integration / e2e
infrastructure/        # docker, nginx
scripts/               # ops scripts
docs/                  # ADRs, runbooks
```

---

## License

TBD.
