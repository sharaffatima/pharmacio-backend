# Pharmacio Backend

Backend service for the Pharmacio Smart Pharmacy System.
This repository contains the core business logic, APIs, and data management for pharmacy operations, including file intake, OCR result handling, proposal generation, approval workflows, inventory & capital updates, monitoring, and access control.

It acts as the **source of truth for business logic** and coordinates with:

- a shared AI/OCR Engine
- a separate Frontend application
- persistent storage (database + file storage)

## Responsibilities of the Backend

The backend is responsible for:

- Accepting and registering uploaded warehouse offer files (PDFs)
- Dispatching OCR requests to the AI/OCR Engine
- Receiving, validating, and storing structured OCR results
- Managing inventory and sales history
- Generating purchase proposals based on offers and internal data
- Enforcing approval workflows and business rules
- Updating inventory only after approval
- Monitoring stock levels and creating alerts
- Enforcing role-based access control (RBAC)

## System Context

- Each pharmacy runs its own backend instance and database
- The AI/OCR Engine is a shared external service
- Communication with AI is asynchronous and job-based
- The backend is the source of truth for business state

## Architecture Overview

- Architecture style: Modular Monolith
- Deployment scope: One backend per pharmacy
- Scalability model: Scale per pharmacy, not globally
- Async operations: Job-based dispatch for OCR integration

### Core internal modules include:

- Authentication & RBAC
- File intake & metadata
- OCR result handling
- Proposal & approval workflow
- Inventory management
- Monitoring & notifications

## Tech Stack

- Language: Python
- Framework: Django (REST-based)
- Database: PostgreSQL
- Containerization: Docker & Docker Compose
- CI: GitHub Actions

## Repository Structure

```text
pharmacio-backend/
├── config/            # Django project configuration (settings, URLs, WSGI/ASGI)
├── users/             # User management (extends Django auth)
├── rbac/              # Role-Based Access Control logic
├── files/             # File upload handling & metadata
├── ai_integration/    # AI / OCR engine integration
├── inventory/         # Inventory & stock management
├── sales/             # Sales history & demand tracking
├── purchases/         # Purchase proposals & approval workflow
├── notifications/     # Notification system & alerting
├── manage.py          # Django CLI entrypoint
├── requirements.txt   # Python dependencies
├── Dockerfile         # Container image definition
├── docker-compose.yml # Local dev stack (DB, Redis, worker, backend)
└── .env.example       # Example environment variables (no secrets)
```

---

## Getting Started

Choose one setup path:

- Docker (recommended): fastest way to run the full stack
- Local (advanced): run backend and dependencies directly on your machine

### Prerequisites

- Required for all workflows:
  - Git
- Required for Docker workflow:
  - Docker Desktop
  - Docker Compose v2 (`docker compose`)
- Required for local workflow:
  - Python 3.10+
  - PostgreSQL 14+ (reachable via `DATABASE_URL`)
  - Redis 6+ (Celery broker/result backend)
- Optional but recommended:
  - GNU Make (`make`) for command shortcuts
  - WSL2 on Windows for better Docker and shell compatibility
  - `pipenv` or `venv` for Python environment management

### 1) Clone the repo

```bash
git clone <repo-url>
cd pharmacio-backend
```

### 2) Environment

Create your environment file from the template:

Windows:

```bash
Copy-Item .env.example .env
```

Or (cross-platform):

```bash
cp .env.example .env
```

Set values required by your workflow (at minimum `SECRET_KEY`, and for local workflow `DATABASE_URL`, Redis/Celery settings, and storage-related settings if used).

### 3A) Run with Docker (recommended)

```bash
docker compose up --build -d
```

- The stack includes `backend`, `db`, `redis`, `celery`, and `minio` services.
- Default backend URL: `http://localhost:8000` (health: `/health/`).

Apply migrations and create an admin user:

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

### 3B) Run locally (non-Docker)

Create and activate a Python environment, install dependencies, then run migrations and server:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

If you run Celery locally, ensure Redis is running and start a worker:

```bash
celery -A config worker -l info
```

### Quick Commands with Makefile

For convenience, a `Makefile` is included with shortcuts for common tasks:

```bash
make help                  # View all available commands
make migrate              # Run database migrations
make makemigrations       # Create new migrations
make test                 # Run all tests
make test-ai              # Run OCR integration tests only
make shell                # Open Django shell
make createsuperuser      # Create admin user
make up                    # Start Docker containers
make down                  # Stop Docker containers
make logs                  # Follow container logs
make clean                 # Remove __pycache__ and .pyc files
```

Make requirements:

- **Linux/macOS**: `make` pre-installed
- **Windows**: Install via [Chocolatey](https://chocolatey.org/) (`choco install make`), [Scoop](https://scoop.sh/) (`scoop install make`), or use WSL2
- **Alternative**: Run docker commands directly if `make` not available (e.g., `docker compose exec backend python manage.py migrate`)

### Useful commands

| Command                               | Purpose                    |
| ------------------------------------- | -------------------------- |
| `python manage.py migrate`            | Apply DB migrations        |
| `python manage.py createsuperuser`    | Create admin user          |
| `python manage.py loaddata <fixture>` | Load fixture data          |
| `docker compose logs -f`              | Follow service logs        |
| `docker compose down`                 | Stop and remove containers |

### Troubleshooting & tips

- If DB connection fails in Docker mode, start only the DB: `docker compose up -d db`.
- If unsure which service name to use for `docker compose exec`, run `docker compose ps` to check service names.
- Prefer WSL2 on Windows for best compatibility with Docker and development tools.

## File Storage Backend

The file intake flow now uses a storage adapter interface in `files/storage.py`.
Business logic in `files/views.py` and `files/serializers.py` depends on this interface instead of talking directly to S3.

### Backends

- `local`: saves files to Django media storage (filesystem)
- `s3`: uploads files to S3-compatible object storage

### Config switch point

Set `FILE_STORAGE_BACKEND` in `.env`:

```bash
FILE_STORAGE_BACKEND=local
```

or:

```bash
FILE_STORAGE_BACKEND=s3
```

If `FILE_STORAGE_BACKEND` is not set, the app falls back to legacy behavior via `USE_S3` (`s3` when true, otherwise `local`).
