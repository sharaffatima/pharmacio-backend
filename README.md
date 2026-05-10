# Pharmacio Backend

Django REST backend for the Pharmacio Smart Pharmacy System — file intake, OCR integration, inventory, purchase proposals, approvals, and RBAC.

## Tech Stack

Python 3.11 · Django 5.2 · Django REST Framework · PostgreSQL 16 · Redis 7 · Celery · S3/MinIO · Docker Compose

## Quick Start (Docker)

> [!IMPORTANT]
> The backend and AI microservice communicate over an external Docker network. You **must** create this network manually once before starting the services, otherwise `docker compose` will throw an error:
> ```bash
> docker network create pharmacio-net
> ```

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
pos/               Point of sale checkout, transactions, receipts, and refunds
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

## Upload Intake

The shared upload endpoint is:

```http
POST /api/v1/offers/upload/
Content-Type: multipart/form-data
Authorization: Bearer <access-token>
```

Use the multipart field `file`. The endpoint routes by file extension:

| File type | Behavior |
| --------- | -------- |
| `.pdf`, `.jpg`, `.jpeg`, `.png` | Stored and dispatched to the OCR engine as an offer file |
| `.csv`, `.xlsx` | Stored and imported into inventory as an opening balance |

Opening balance imports are intended for first-time pharmacy migration from another inventory system. The uploaded file is treated as authoritative stock data:

- Existing inventory rows are matched by `product_name` + `strength`.
- Matching rows have `quantity_on_hand` and `min_threshold` replaced.
- New rows are created when no matching inventory item exists.
- The whole import is atomic. If any row is invalid, no inventory rows are changed.
- `.xlsx` support requires the `openpyxl` dependency from `requirements.txt`.

Supported opening balance columns:

| Inventory field | Accepted headers |
| --------------- | ---------------- |
| `product_name` | `product_name`, `product`, `medicine`, `drug_name`, `item_name`, `name` |
| `strength` | `strength`, `dosage`, `dose` |
| `quantity_on_hand` | `quantity_on_hand`, `quantity`, `qty`, `stock`, `opening_stock`, `current_stock` |
| `min_threshold` | `min_threshold`, `threshold`, `minimum_stock`, `reorder_level`, `min_stock` |

`product_name`, `strength`, and `quantity_on_hand` are required. `min_threshold` is optional and defaults to `0` when omitted.

Example CSV:

```csv
product,dosage,qty,reorder_level
Aspirin,100mg,50,10
Ibuprofen,400mg,20,5
```

Successful opening balance uploads return the normal upload status fields plus import metadata:

```json
{
  "upload_id": "2c28f1f7-4c4d-4a21-b8a7-77fb31d99e7d",
  "original_filename": "opening_balance.csv",
  "file_url": "/media/uploads/1/...",
  "status": "completed",
  "message": "Inventory import completed successfully",
  "created_at": "2026-05-10T12:00:00Z",
  "import_result": {
    "status": "completed",
    "total_rows": 2,
    "created_count": 2,
    "updated_count": 0
  }
}
```

## Production

See [PRODUCTION.md](PRODUCTION.md) for the deployment checklist.
