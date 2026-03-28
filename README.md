# Pharmacio Backend

Django REST backend for the Pharmacio Smart Pharmacy System — file intake, OCR integration, inventory, purchase proposals, approvals, and RBAC.

## Tech Stack

Python 3.11 · Django 5.2 · Django REST Framework · PostgreSQL 16 · Redis 7 · Celery · S3/MinIO · Docker Compose

## Quick Start (Docker)

```bash
cp .env.example .env          # adjust values as needed
docker compose up --build -d
```

Backend: http://localhost:8000 · Health: `/health/` · DB health: `/health/db/`

## Quick Start (Local)

Requires Python 3.10+, a running PostgreSQL and Redis instance, and `pipenv`.

```bash
cp .env.example .env          # point DB_HOST, REDIS_URL to local services
pipenv install
pipenv run python manage.py migrate
pipenv run python manage.py runserver
```

## Make Targets

Run `make help` for the full list. Key commands:

| Command                | Description                     |
| ---------------------- | ------------------------------- |
| `make up` / `down`     | Start / stop Docker stack       |
| `make build`           | Rebuild Docker images           |
| `make migrate`         | Run migrations (Docker)         |
| `make test`            | Run all tests (Docker)          |
| `make run`             | Start dev server (local pipenv) |
| `make createsuperuser` | Create admin user (Docker)      |

## Project Structure

```
config/            Django settings, URLs, WSGI/ASGI, Celery config
users/             User model, auth views (register, login, logout)
rbac/              Roles, permissions, audit logging
files/             File upload, storage adapter (local / S3)
ai_integration/    OCR job dispatch, callback, result storage
inventory/         Inventory tracking
sales/             Sales history
purchases/         Purchase proposals & approval workflow
notifications/     Stock alerts & notifications
```

## Environment

All config is via environment variables. Copy `.env.example` and adjust:

| Variable                  | Purpose                            |
| ------------------------- | ---------------------------------- |
| `DJANGO_SECRET_KEY`       | Django secret key (change in prod) |
| `DJANGO_DEBUG`            | `True` / `False`                   |
| `DB_NAME`, `DB_USER`, etc | PostgreSQL connection              |
| `CELERY_BROKER_URL`       | Redis URL for Celery               |
| `FILE_STORAGE_BACKEND`    | `local` or `s3`                    |
| `INTERNAL_SERVICE_TOKEN`  | Shared token for OCR callbacks     |
| `AI_ENGINE_API_KEY`       | API key for outbound OCR requests  |

See `.env.example` for the full list.

## File Storage

Set `FILE_STORAGE_BACKEND` in `.env`:

- **`local`** — saves to Django media directory (default for dev)
- **`s3`** — uploads to S3-compatible storage (set `AWS_*` vars)

## Production

See [PRODUCTION.md](PRODUCTION.md) for the deployment checklist.
